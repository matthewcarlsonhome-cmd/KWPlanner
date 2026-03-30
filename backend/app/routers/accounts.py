"""Account management routes."""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Account, ResearchRun, KeywordIdea, Decision
from app.models.schemas import AccountOut, AccountDetail, ResearchRunOut
from app.services.google_ads import GoogleAdsService
from app.routers.auth import get_refresh_token

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=List[AccountOut])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    """List all MCC child accounts with latest run stats."""
    result = await db.execute(select(Account).order_by(Account.name))
    accounts = result.scalars().all()

    account_list = []
    for acct in accounts:
        # Get latest run stats
        run_result = await db.execute(
            select(ResearchRun)
            .where(ResearchRun.account_id == acct.id)
            .where(ResearchRun.status == "completed")
            .order_by(ResearchRun.completed_at.desc())
            .limit(1)
        )
        latest_run = run_result.scalar_one_or_none()

        # Count decisions
        approved_count = 0
        pending_count = 0
        if latest_run:
            dec_result = await db.execute(
                select(func.count())
                .select_from(Decision)
                .where(Decision.account_id == acct.id)
                .where(Decision.decision == "approved")
            )
            approved_count = dec_result.scalar() or 0

            # Total ideas minus decided = pending
            total_ideas = (latest_run.ideas_generated or 0)
            dec_total_result = await db.execute(
                select(func.count())
                .select_from(Decision)
                .where(Decision.account_id == acct.id)
            )
            total_decided = dec_total_result.scalar() or 0
            pending_count = max(0, total_ideas - total_decided)

        out = AccountOut(
            id=acct.id,
            google_ads_id=acct.google_ads_id,
            name=acct.name,
            is_active=acct.is_active,
            avg_cpc=float(acct.avg_cpc) if acct.avg_cpc else None,
            avg_cpa=float(acct.avg_cpa) if acct.avg_cpa else None,
            monthly_budget=float(acct.monthly_budget) if acct.monthly_budget else None,
            geo_target_ids=acct.geo_target_ids,
            last_synced_at=acct.last_synced_at,
            created_at=acct.created_at,
            latest_run_date=latest_run.completed_at if latest_run else None,
            ideas_count=latest_run.ideas_generated if latest_run else None,
            ideas_high=latest_run.ideas_high if latest_run else None,
            ideas_medium=latest_run.ideas_medium if latest_run else None,
            approved_count=approved_count,
            pending_count=pending_count,
        )
        account_list.append(out)

    return account_list


@router.post("/sync")
async def sync_accounts(request: Request, db: AsyncSession = Depends(get_db)):
    """Refresh account list from MCC."""
    refresh_token = get_refresh_token(request)
    google_ads = GoogleAdsService(refresh_token or "")

    api_accounts = await google_ads.list_accessible_accounts()

    synced = 0
    for api_acct in api_accounts:
        existing = await db.execute(
            select(Account).where(Account.google_ads_id == api_acct["google_ads_id"])
        )
        account = existing.scalar_one_or_none()

        if account:
            account.name = api_acct["name"]
            account.last_synced_at = datetime.utcnow()
        else:
            account = Account(
                google_ads_id=api_acct["google_ads_id"],
                name=api_acct["name"],
                last_synced_at=datetime.utcnow(),
            )
            db.add(account)
        synced += 1

    await db.commit()
    return {"synced": synced, "total": len(api_accounts)}


@router.get("/{account_id}", response_model=AccountDetail)
async def get_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """Get single account detail with run history."""
    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Get runs
    runs_result = await db.execute(
        select(ResearchRun)
        .where(ResearchRun.account_id == account_id)
        .order_by(ResearchRun.started_at.desc())
    )
    runs = runs_result.scalars().all()

    # Get latest run stats
    latest_run = runs[0] if runs else None
    approved_result = await db.execute(
        select(func.count())
        .select_from(Decision)
        .where(Decision.account_id == account_id)
        .where(Decision.decision == "approved")
    )
    approved_count = approved_result.scalar() or 0

    total_decided_result = await db.execute(
        select(func.count())
        .select_from(Decision)
        .where(Decision.account_id == account_id)
    )
    total_decided = total_decided_result.scalar() or 0
    pending_count = max(0, (latest_run.ideas_generated or 0) - total_decided) if latest_run else 0

    return AccountDetail(
        id=account.id,
        google_ads_id=account.google_ads_id,
        name=account.name,
        is_active=account.is_active,
        avg_cpc=float(account.avg_cpc) if account.avg_cpc else None,
        avg_cpa=float(account.avg_cpa) if account.avg_cpa else None,
        monthly_budget=float(account.monthly_budget) if account.monthly_budget else None,
        geo_target_ids=account.geo_target_ids,
        last_synced_at=account.last_synced_at,
        created_at=account.created_at,
        latest_run_date=latest_run.completed_at if latest_run else None,
        ideas_count=latest_run.ideas_generated if latest_run else None,
        ideas_high=latest_run.ideas_high if latest_run else None,
        ideas_medium=latest_run.ideas_medium if latest_run else None,
        approved_count=approved_count,
        pending_count=pending_count,
        runs=[ResearchRunOut.model_validate(r) for r in runs],
    )
