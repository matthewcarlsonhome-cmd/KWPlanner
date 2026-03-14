"""Decision management routes — approve/reject/watchlist keywords."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Decision, KeywordIdea
from app.models.schemas import DecisionCreate, DecisionUpdate, DecisionOut

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


@router.post("", response_model=List[DecisionOut])
async def create_decisions(
    body: DecisionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Bulk approve/reject/watchlist keyword ideas."""
    if body.decision not in ("approved", "rejected", "watchlist", "implemented"):
        raise HTTPException(status_code=400, detail="Invalid decision type")

    created = []
    for idea_id in body.keyword_idea_ids:
        idea = await db.get(KeywordIdea, idea_id)
        if not idea:
            continue

        # Check for existing decision and update it
        existing = await db.execute(
            select(Decision).where(Decision.keyword_idea_id == idea_id)
            .order_by(Decision.decided_at.desc())
            .limit(1)
        )
        old_decision = existing.scalar_one_or_none()

        if old_decision:
            old_decision.decision = body.decision
            old_decision.decided_by = body.decided_by
            old_decision.notes = body.notes
            old_decision.decided_at = datetime.utcnow()
            decision = old_decision
        else:
            decision = Decision(
                keyword_idea_id=idea_id,
                account_id=idea.account_id,
                decision=body.decision,
                decided_by=body.decided_by,
                notes=body.notes,
            )
            db.add(decision)

        await db.flush()
        created.append(DecisionOut(
            id=decision.id,
            keyword_idea_id=idea_id,
            account_id=idea.account_id,
            decision=body.decision,
            decided_by=body.decided_by,
            notes=body.notes,
            decided_at=decision.decided_at,
            keyword_text=idea.keyword_text,
        ))

    await db.commit()
    return created


@router.patch("/{decision_id}", response_model=DecisionOut)
async def update_decision(
    decision_id: int,
    body: DecisionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a decision (e.g., mark as implemented)."""
    decision = await db.get(Decision, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    if body.decision is not None:
        decision.decision = body.decision
    if body.implemented_at is not None:
        decision.implemented_at = body.implemented_at
    if body.notes is not None:
        decision.notes = body.notes

    decision.decided_at = datetime.utcnow()
    await db.commit()

    idea = await db.get(KeywordIdea, decision.keyword_idea_id)
    return DecisionOut(
        id=decision.id,
        keyword_idea_id=decision.keyword_idea_id,
        account_id=decision.account_id,
        decision=decision.decision,
        decided_by=decision.decided_by,
        notes=decision.notes,
        implemented_at=decision.implemented_at,
        decided_at=decision.decided_at,
        keyword_text=idea.keyword_text if idea else None,
    )


@router.get("/{account_id}", response_model=List[DecisionOut])
async def get_decisions(
    account_id: int,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get all decisions for an account."""
    query = select(Decision).where(Decision.account_id == account_id)
    if status:
        query = query.where(Decision.decision == status)
    query = query.order_by(Decision.decided_at.desc())

    result = await db.execute(query)
    decisions = result.scalars().all()

    out = []
    for d in decisions:
        idea = await db.get(KeywordIdea, d.keyword_idea_id)
        out.append(DecisionOut(
            id=d.id,
            keyword_idea_id=d.keyword_idea_id,
            account_id=d.account_id,
            decision=d.decision,
            decided_by=d.decided_by,
            notes=d.notes,
            implemented_at=d.implemented_at,
            decided_at=d.decided_at,
            keyword_text=idea.keyword_text if idea else None,
        ))

    return out
