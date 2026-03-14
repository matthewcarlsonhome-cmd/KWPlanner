"""Results and keyword idea browsing routes."""

import math
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import KeywordIdea, Decision, SeedKeyword, NegativeFlag, ResearchRun
from app.models.schemas import (
    KeywordIdeaOut, KeywordIdeaPage, SeedKeywordOut, NegativeFlagOut, CompareResult,
)

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/{account_id}", response_model=KeywordIdeaPage)
async def get_results(
    account_id: int,
    priority: Optional[str] = None,
    sort: str = "score",
    page: int = 1,
    per_page: int = 50,
    run_id: Optional[int] = None,
    search: Optional[str] = None,
    show_existing: bool = False,
    show_decided: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """Fetch filtered and sorted keyword ideas for an account."""
    # If no run_id, use latest completed run
    if not run_id:
        latest_run = await db.execute(
            select(ResearchRun)
            .where(ResearchRun.account_id == account_id)
            .where(ResearchRun.status == "completed")
            .order_by(ResearchRun.completed_at.desc())
            .limit(1)
        )
        run = latest_run.scalar_one_or_none()
        if not run:
            return KeywordIdeaPage(items=[], total=0, page=1, per_page=per_page, pages=0)
        run_id = run.id

    # Build query
    query = select(KeywordIdea).where(
        and_(KeywordIdea.account_id == account_id, KeywordIdea.run_id == run_id)
    )

    if priority:
        priorities = [p.strip() for p in priority.split(",")]
        query = query.where(KeywordIdea.priority.in_(priorities))

    if search:
        query = query.where(KeywordIdea.keyword_text.ilike(f"%{search}%"))

    if not show_existing:
        query = query.where(KeywordIdea.already_exists == False)

    if not show_decided:
        decided_ids = await db.execute(
            select(Decision.keyword_idea_id).where(Decision.account_id == account_id)
        )
        decided_set = {r[0] for r in decided_ids.all()}
        if decided_set:
            query = query.where(KeywordIdea.id.notin_(decided_set))

    # Sort
    sort_map = {
        "score": KeywordIdea.total_score.desc(),
        "volume": KeywordIdea.avg_monthly_searches.desc(),
        "cpc": KeywordIdea.high_cpc_micros.asc(),
        "competition": KeywordIdea.competition_index.asc(),
        "keyword": KeywordIdea.keyword_text.asc(),
    }
    query = query.order_by(sort_map.get(sort, KeywordIdea.total_score.desc()))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    ideas = result.scalars().all()

    # Get decisions for these ideas
    idea_ids = [i.id for i in ideas]
    if idea_ids:
        dec_result = await db.execute(
            select(Decision)
            .where(Decision.keyword_idea_id.in_(idea_ids))
            .order_by(Decision.decided_at.desc())
        )
        decisions = {}
        for d in dec_result.scalars().all():
            if d.keyword_idea_id not in decisions:
                decisions[d.keyword_idea_id] = d
    else:
        decisions = {}

    items = []
    for idea in ideas:
        dec = decisions.get(idea.id)
        item = KeywordIdeaOut(
            id=idea.id,
            run_id=idea.run_id,
            account_id=idea.account_id,
            keyword_text=idea.keyword_text,
            avg_monthly_searches=idea.avg_monthly_searches,
            competition=idea.competition,
            competition_index=idea.competition_index,
            low_cpc_micros=idea.low_cpc_micros,
            high_cpc_micros=idea.high_cpc_micros,
            monthly_volumes=idea.monthly_volumes,
            volume_score=idea.volume_score,
            competition_score=idea.competition_score,
            cpc_score=idea.cpc_score,
            relevance_score=idea.relevance_score,
            total_score=idea.total_score,
            priority=idea.priority,
            relevance_category=idea.relevance_category,
            suggested_match_type=idea.suggested_match_type,
            suggested_ad_group=idea.suggested_ad_group,
            already_exists=idea.already_exists,
            already_negative=idea.already_negative,
            is_seasonal=idea.is_seasonal,
            peak_month=idea.peak_month,
            created_at=idea.created_at,
            decision_status=dec.decision if dec else None,
            decision_by=dec.decided_by if dec else None,
            decision_notes=dec.notes if dec else None,
        )
        items.append(item)

    return KeywordIdeaPage(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total > 0 else 0,
    )


@router.get("/{account_id}/seeds", response_model=List[SeedKeywordOut])
async def get_seeds(
    account_id: int,
    run_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get seed keywords used for the latest run."""
    if not run_id:
        latest = await db.execute(
            select(ResearchRun)
            .where(ResearchRun.account_id == account_id)
            .where(ResearchRun.status == "completed")
            .order_by(ResearchRun.completed_at.desc())
            .limit(1)
        )
        run = latest.scalar_one_or_none()
        if not run:
            return []
        run_id = run.id

    result = await db.execute(
        select(SeedKeyword).where(SeedKeyword.run_id == run_id)
    )
    seeds = result.scalars().all()
    return [SeedKeywordOut.model_validate(s) for s in seeds]


@router.get("/{account_id}/negatives", response_model=List[NegativeFlagOut])
async def get_negatives(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get negative keyword candidates."""
    result = await db.execute(
        select(NegativeFlag)
        .where(NegativeFlag.account_id == account_id)
        .order_by(NegativeFlag.decided_at.desc().nullsfirst())
    )
    flags = result.scalars().all()
    return [NegativeFlagOut.model_validate(f) for f in flags]


@router.get("/{account_id}/compare", response_model=CompareResult)
async def compare_runs(
    account_id: int,
    run_a: int = Query(..., description="First run ID (older)"),
    run_b: int = Query(..., description="Second run ID (newer)"),
    db: AsyncSession = Depends(get_db),
):
    """Compare two runs to find new, removed, and changed keywords."""
    # Get keywords from both runs
    result_a = await db.execute(
        select(KeywordIdea).where(
            and_(KeywordIdea.account_id == account_id, KeywordIdea.run_id == run_a)
        )
    )
    ideas_a = {i.keyword_text.lower(): i for i in result_a.scalars().all()}

    result_b = await db.execute(
        select(KeywordIdea).where(
            and_(KeywordIdea.account_id == account_id, KeywordIdea.run_id == run_b)
        )
    )
    ideas_b = {i.keyword_text.lower(): i for i in result_b.scalars().all()}

    keys_a = set(ideas_a.keys())
    keys_b = set(ideas_b.keys())

    def idea_to_out(idea):
        return KeywordIdeaOut(
            id=idea.id, run_id=idea.run_id, account_id=idea.account_id,
            keyword_text=idea.keyword_text, avg_monthly_searches=idea.avg_monthly_searches,
            competition=idea.competition, competition_index=idea.competition_index,
            low_cpc_micros=idea.low_cpc_micros, high_cpc_micros=idea.high_cpc_micros,
            monthly_volumes=idea.monthly_volumes, volume_score=idea.volume_score,
            competition_score=idea.competition_score, cpc_score=idea.cpc_score,
            relevance_score=idea.relevance_score, total_score=idea.total_score,
            priority=idea.priority, relevance_category=idea.relevance_category,
            suggested_match_type=idea.suggested_match_type,
            suggested_ad_group=idea.suggested_ad_group,
            already_exists=idea.already_exists, already_negative=idea.already_negative,
            is_seasonal=idea.is_seasonal, peak_month=idea.peak_month,
        )

    new_ideas = [idea_to_out(ideas_b[k]) for k in (keys_b - keys_a)]
    removed_ideas = [idea_to_out(ideas_a[k]) for k in (keys_a - keys_b)]

    score_changes = []
    for k in keys_a & keys_b:
        old_score = ideas_a[k].total_score or 0
        new_score = ideas_b[k].total_score or 0
        delta = new_score - old_score
        if abs(delta) >= 5:
            score_changes.append({
                "keyword": k,
                "old_score": old_score,
                "new_score": new_score,
                "delta": delta,
                "old_priority": ideas_a[k].priority,
                "new_priority": ideas_b[k].priority,
            })

    score_changes.sort(key=lambda x: abs(x["delta"]), reverse=True)

    return CompareResult(
        new_ideas=sorted(new_ideas, key=lambda x: x.total_score or 0, reverse=True),
        removed_ideas=sorted(removed_ideas, key=lambda x: x.total_score or 0, reverse=True),
        score_changes=score_changes,
    )
