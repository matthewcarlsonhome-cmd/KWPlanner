"""Research run management routes."""

import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models.models import ResearchRun
from app.models.schemas import ResearchRunOut, RunStatusOut
from app.services.research import start_research, get_active_run
from app.routers.auth import get_refresh_token
from app.config import settings

router = APIRouter(prefix="/api/research", tags=["research"])


async def _run_research_background(account_id: Optional[int], refresh_token: str, settings_dict: dict):
    """Background task wrapper for research."""
    async with async_session() as db:
        try:
            await start_research(db, account_id, refresh_token, settings_dict)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Background research failed: {e}")


@router.post("/run")
async def run_research(
    request: Request,
    background_tasks: BackgroundTasks,
    account_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Start keyword research for one or all accounts."""
    active = get_active_run()
    if active:
        raise HTTPException(
            status_code=409,
            detail=f"Research is already running. Current account: {active.get('current_account', 'starting...')}"
        )

    refresh_token = get_refresh_token(request) or ""

    settings_dict = {
        "lookback_days": settings.default_lookback_days,
        "min_seed_conversions": settings.default_min_seed_conversions,
        "min_seed_clicks": settings.default_min_seed_clicks,
        "max_seeds_per_account": settings.default_max_seeds_per_account,
        "min_monthly_searches": settings.default_min_monthly_searches,
    }

    background_tasks.add_task(
        _run_research_background, account_id, refresh_token, settings_dict
    )

    return {"status": "started", "message": "Research is starting in the background"}


@router.get("/status", response_model=RunStatusOut)
async def get_research_status():
    """Get status of the currently running research."""
    active = get_active_run()
    if not active:
        return RunStatusOut(run_id=0, status="idle", accounts_completed=0, accounts_total=0)

    return RunStatusOut(
        run_id=active["run_id"],
        status=active["status"],
        accounts_completed=active["accounts_completed"],
        accounts_total=active["accounts_total"],
        current_account=active.get("current_account"),
    )


@router.get("/runs", response_model=List[ResearchRunOut])
async def list_runs(
    account_id: Optional[int] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List past research runs."""
    query = select(ResearchRun).order_by(ResearchRun.started_at.desc()).limit(limit)
    if account_id:
        query = query.where(ResearchRun.account_id == account_id)

    result = await db.execute(query)
    runs = result.scalars().all()
    return [ResearchRunOut.model_validate(r) for r in runs]


@router.get("/runs/{run_id}", response_model=ResearchRunOut)
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single run detail."""
    run = await db.get(ResearchRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return ResearchRunOut.model_validate(run)
