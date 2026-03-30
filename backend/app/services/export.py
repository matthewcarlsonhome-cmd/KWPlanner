"""Export services for Google Ads Editor CSV, Excel, and Sheets."""

import csv
import io
from typing import List, Optional

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import KeywordIdea, Decision, Account, NegativeFlag


async def export_google_ads_editor_csv(
    db: AsyncSession,
    account_id: int,
    priorities: Optional[List[str]] = None,
    approved_only: bool = True,
) -> str:
    """Generate a CSV formatted for Google Ads Editor import."""
    query = select(KeywordIdea).where(KeywordIdea.account_id == account_id)

    if priorities:
        query = query.where(KeywordIdea.priority.in_(priorities))

    if approved_only:
        # Join with decisions to get only approved
        approved_ids_q = (
            select(Decision.keyword_idea_id)
            .where(Decision.account_id == account_id)
            .where(Decision.decision == "approved")
        )
        result = await db.execute(approved_ids_q)
        approved_ids = [r[0] for r in result.all()]
        if not approved_ids:
            # If no approved keywords, return all matching priorities
            approved_only = False
        else:
            query = query.where(KeywordIdea.id.in_(approved_ids))

    query = query.order_by(KeywordIdea.total_score.desc())
    result = await db.execute(query)
    ideas = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Campaign", "Ad Group", "Keyword", "Criterion Type", "Max CPC"])

    for idea in ideas:
        match_type = idea.suggested_match_type or "PHRASE"
        if match_type == "EXACT":
            kw_formatted = f"[{idea.keyword_text}]"
            criterion_type = "Exact"
        else:
            kw_formatted = f'"{idea.keyword_text}"'
            criterion_type = "Phrase"

        campaign = ""
        ad_group = idea.suggested_ad_group or ""

        # Get decision for max CPC
        dec_result = await db.execute(
            select(Decision)
            .where(Decision.keyword_idea_id == idea.id)
            .order_by(Decision.decided_at.desc())
            .limit(1)
        )
        decision = dec_result.scalar_one_or_none()
        max_cpc = ""
        if decision and decision.notes and decision.notes.startswith("cpc:"):
            max_cpc = decision.notes.split("cpc:")[1].strip()

        writer.writerow([campaign, ad_group, kw_formatted, criterion_type, max_cpc])

    return output.getvalue()


async def export_negatives_csv(
    db: AsyncSession,
    account_id: int,
) -> str:
    """Export negative keyword candidates as a list."""
    result = await db.execute(
        select(NegativeFlag)
        .where(NegativeFlag.account_id == account_id)
        .where(NegativeFlag.decided.in_(["pending", "approved"]))
    )
    flags = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Keyword", "Scope", "Reason"])

    for flag in flags:
        writer.writerow([
            f'"{flag.keyword_text}"',
            flag.suggested_scope or "CAMPAIGN",
            flag.reason or "",
        ])

    return output.getvalue()


async def export_excel_workbook(
    db: AsyncSession,
    account_ids: Optional[List[int]] = None,
    priorities: Optional[List[str]] = None,
) -> bytes:
    """Generate a multi-tab Excel workbook."""
    wb = Workbook()

    # Summary sheet
    ws_summary = wb.active
    ws_summary.title = "Summary"
    ws_summary.append([
        "Account", "Total Ideas", "HIGH", "MEDIUM", "LOW",
        "Approved", "Pending", "Top Opportunity",
    ])

    if account_ids is None:
        result = await db.execute(select(Account).where(Account.is_active == True))
        accounts = result.scalars().all()
    else:
        result = await db.execute(select(Account).where(Account.id.in_(account_ids)))
        accounts = result.scalars().all()

    for account in accounts:
        query = select(KeywordIdea).where(KeywordIdea.account_id == account.id)
        if priorities:
            query = query.where(KeywordIdea.priority.in_(priorities))
        query = query.order_by(KeywordIdea.total_score.desc())

        result = await db.execute(query)
        ideas = result.scalars().all()

        # Count by priority
        high = sum(1 for i in ideas if i.priority == "HIGH")
        med = sum(1 for i in ideas if i.priority == "MEDIUM")
        low = sum(1 for i in ideas if i.priority == "LOW")

        # Count decisions
        dec_result = await db.execute(
            select(Decision).where(Decision.account_id == account.id)
        )
        decisions = {d.keyword_idea_id: d for d in dec_result.scalars().all()}
        approved = sum(1 for d in decisions.values() if d.decision == "approved")
        pending = len(ideas) - len(decisions)

        top_opp = ideas[0].keyword_text if ideas else "N/A"
        ws_summary.append([
            account.name, len(ideas), high, med, low, approved, pending, top_opp,
        ])

        # Per-account sheet
        ws = wb.create_sheet(title=account.name[:31])  # Excel 31-char tab name limit
        ws.append([
            "Keyword", "Score", "Priority", "Monthly Searches", "Competition",
            "Est. CPC Low", "Est. CPC High", "Relevance",
            "Suggested Match", "Suggested Ad Group", "Seasonal", "Status",
        ])

        for idea in ideas:
            cpc_low = f"${idea.low_cpc_micros / 1_000_000:.2f}" if idea.low_cpc_micros else ""
            cpc_high = f"${idea.high_cpc_micros / 1_000_000:.2f}" if idea.high_cpc_micros else ""
            decision = decisions.get(idea.id)
            status = decision.decision if decision else "Pending"
            seasonal = f"Peaks in {idea.peak_month}" if idea.is_seasonal else "Steady"

            ws.append([
                idea.keyword_text, idea.total_score, idea.priority,
                idea.avg_monthly_searches, idea.competition,
                cpc_low, cpc_high, idea.relevance_category,
                idea.suggested_match_type, idea.suggested_ad_group,
                seasonal, status,
            ])

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
