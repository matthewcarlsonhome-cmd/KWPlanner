"""Research orchestration service — runs the full keyword research pipeline."""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Account, ResearchRun, SeedKeyword, KeywordIdea, NegativeFlag,
)
from app.services.google_ads import GoogleAdsService
from app.services.scorer import score_keyword

logger = logging.getLogger(__name__)

# Global state for tracking active research
_active_run: Optional[Dict[str, Any]] = None


def get_active_run() -> Optional[Dict[str, Any]]:
    return _active_run


async def run_research_for_account(
    db: AsyncSession,
    account: Account,
    run: ResearchRun,
    google_ads: GoogleAdsService,
    settings_dict: dict,
) -> None:
    """Execute the full research pipeline for a single account."""
    global _active_run

    customer_id = account.google_ads_id.replace("-", "")

    try:
        if _active_run:
            _active_run["current_account"] = account.name

        # 1. Get seed keywords
        seeds = await google_ads.get_seed_keywords(
            customer_id,
            lookback_days=settings_dict.get("lookback_days", 90),
            min_conversions=settings_dict.get("min_seed_conversions", 2.0),
            min_clicks=settings_dict.get("min_seed_clicks", 10),
            max_seeds=settings_dict.get("max_seeds_per_account", 15),
        )

        if not seeds:
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            run.error_message = "No qualifying seed keywords found"
            run.seed_count = 0
            run.ideas_generated = 0
            run.ideas_high = 0
            run.ideas_medium = 0
            run.ideas_low = 0
            await db.commit()
            return

        # Save seeds to DB
        for s in seeds:
            db.add(SeedKeyword(run_id=run.id, **s))
        run.seed_count = len(seeds)
        await db.commit()

        # 2. Get geo targets, existing keywords, negatives, ad groups
        geo_targets = await google_ads.get_geo_targets(customer_id)
        existing_kws = await google_ads.get_existing_keywords(customer_id)
        existing_negatives = await google_ads.get_existing_negatives(customer_id)
        ad_groups = await google_ads.get_ad_groups_with_keywords(customer_id)

        # Update account geo targets
        account.geo_target_ids = geo_targets

        # Get account avg CPC for scoring
        avg_cpc = await google_ads.get_account_avg_cpc(customer_id)
        if avg_cpc:
            account.avg_cpc = avg_cpc
        account_avg_cpc = float(account.avg_cpc) if account.avg_cpc else 3.50

        # 3. Generate keyword ideas (batch seeds in groups of 10-15)
        seed_texts = [s["keyword"] for s in seeds]
        all_ideas = []

        batch_size = 10
        for i in range(0, len(seed_texts), batch_size):
            batch = seed_texts[i:i + batch_size]
            ideas = await google_ads.generate_keyword_ideas(
                customer_id, batch, geo_targets
            )
            all_ideas.extend(ideas)
            # Rate limiting: 1s delay between calls
            await asyncio.sleep(1)

        # 4. Score and save ideas
        ideas_high = 0
        ideas_medium = 0
        ideas_low = 0
        min_searches = settings_dict.get("min_monthly_searches", 50)

        seen_keywords = set()
        for idea_data in all_ideas:
            kw_text = idea_data["keyword_text"]
            kw_lower = kw_text.lower()

            # Deduplicate
            if kw_lower in seen_keywords:
                continue
            seen_keywords.add(kw_lower)

            # Filter by minimum volume
            avg_searches = idea_data.get("avg_monthly_searches", 0) or 0
            if avg_searches < min_searches:
                continue

            # Check if already exists
            already_exists = kw_lower in existing_kws
            already_negative = kw_lower in existing_negatives

            # Score
            scores = score_keyword(
                keyword_text=kw_text,
                avg_monthly_searches=avg_searches,
                competition_index=idea_data.get("competition_index"),
                low_cpc_micros=idea_data.get("low_cpc_micros"),
                high_cpc_micros=idea_data.get("high_cpc_micros"),
                account_avg_cpc=account_avg_cpc,
                monthly_volumes=idea_data.get("monthly_volumes"),
                ad_groups=ad_groups,
            )

            # Create keyword idea record
            keyword_idea = KeywordIdea(
                run_id=run.id,
                account_id=account.id,
                keyword_text=kw_text,
                avg_monthly_searches=avg_searches,
                competition=idea_data.get("competition"),
                competition_index=idea_data.get("competition_index"),
                low_cpc_micros=idea_data.get("low_cpc_micros"),
                high_cpc_micros=idea_data.get("high_cpc_micros"),
                monthly_volumes=idea_data.get("monthly_volumes"),
                already_exists=already_exists,
                already_negative=already_negative,
                **scores,
            )
            db.add(keyword_idea)

            # Track priority counts
            if scores["priority"] == "HIGH":
                ideas_high += 1
            elif scores["priority"] == "MEDIUM":
                ideas_medium += 1
            elif scores["priority"] == "LOW":
                ideas_low += 1

            # Flag negative candidates
            if scores["relevance_category"] == "negative_candidate":
                await db.flush()  # get the keyword_idea.id
                db.add(NegativeFlag(
                    keyword_idea_id=keyword_idea.id,
                    account_id=account.id,
                    keyword_text=kw_text,
                    reason=f"Matches negative pattern",
                    suggested_scope="CAMPAIGN",
                ))

        # 5. Update run stats
        total_ideas = ideas_high + ideas_medium + ideas_low
        run.ideas_generated = total_ideas
        run.ideas_high = ideas_high
        run.ideas_medium = ideas_medium
        run.ideas_low = ideas_low
        run.status = "completed"
        run.completed_at = datetime.utcnow()

        account.last_synced_at = datetime.utcnow()
        await db.commit()

        logger.info(
            f"Research complete for {account.name}: "
            f"{total_ideas} ideas ({ideas_high} HIGH, {ideas_medium} MED, {ideas_low} LOW)"
        )

    except Exception as e:
        logger.error(f"Research failed for {account.name}: {e}")
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.utcnow()
        await db.commit()


async def start_research(
    db: AsyncSession,
    account_id: Optional[int],
    refresh_token: str,
    settings_dict: dict,
) -> int:
    """Start research for one account or all accounts. Returns run_id for tracking."""
    global _active_run

    if _active_run:
        raise ValueError("Research is already running. Please wait for it to complete.")

    google_ads = GoogleAdsService(refresh_token)

    if account_id:
        accounts = [await db.get(Account, account_id)]
        if not accounts[0]:
            raise ValueError(f"Account {account_id} not found")
    else:
        result = await db.execute(select(Account).where(Account.is_active == True))
        accounts = list(result.scalars().all())

    if not accounts:
        raise ValueError("No active accounts found")

    # Create a run record (use first account for single, None for batch)
    first_run = ResearchRun(
        account_id=accounts[0].id if len(accounts) == 1 else None,
        started_at=datetime.utcnow(),
        status="running",
        settings=settings_dict,
    )
    db.add(first_run)
    await db.commit()
    await db.refresh(first_run)

    _active_run = {
        "run_id": first_run.id,
        "status": "running",
        "accounts_completed": 0,
        "accounts_total": len(accounts),
        "current_account": None,
    }

    try:
        for i, account in enumerate(accounts):
            # For multi-account runs, create per-account run records
            if len(accounts) > 1:
                run = ResearchRun(
                    account_id=account.id,
                    started_at=datetime.utcnow(),
                    status="running",
                    settings=settings_dict,
                )
                db.add(run)
                await db.commit()
                await db.refresh(run)
            else:
                run = first_run

            await run_research_for_account(db, account, run, google_ads, settings_dict)

            if _active_run:
                _active_run["accounts_completed"] = i + 1

            # Rate limiting: 2s delay between accounts
            if i < len(accounts) - 1:
                await asyncio.sleep(2)

        if len(accounts) > 1:
            first_run.status = "completed"
            first_run.completed_at = datetime.utcnow()
            await db.commit()

    except Exception as e:
        logger.error(f"Research batch failed: {e}")
        first_run.status = "failed"
        first_run.error_message = str(e)
        first_run.completed_at = datetime.utcnow()
        await db.commit()
    finally:
        _active_run = None

    return first_run.id
