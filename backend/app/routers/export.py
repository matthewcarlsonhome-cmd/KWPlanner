"""Export routes for CSV, Excel, and Sheets."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import io

from app.database import get_db
from app.models.models import Account
from app.models.schemas import ExportRequest, ExportAllRequest
from app.services.export import (
    export_google_ads_editor_csv,
    export_negatives_csv,
    export_excel_workbook,
)

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/google-ads-editor")
async def export_gads_editor(
    body: ExportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Export approved keywords as Google Ads Editor CSV."""
    account = await db.get(Account, body.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    csv_content = await export_google_ads_editor_csv(
        db, body.account_id, body.priority, approved_only=True
    )

    return StreamingResponse(
        io.BytesIO(csv_content.encode()),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{account.name}_keywords.csv"'
        },
    )


@router.post("/negatives")
async def export_negatives(
    account_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Export negative keyword candidates."""
    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    csv_content = await export_negatives_csv(db, account_id)

    return StreamingResponse(
        io.BytesIO(csv_content.encode()),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{account.name}_negatives.csv"'
        },
    )


@router.post("/all-accounts")
async def export_all(
    body: ExportAllRequest,
    db: AsyncSession = Depends(get_db),
):
    """Export multi-tab Excel workbook for all accounts."""
    xlsx_bytes = await export_excel_workbook(db, priorities=body.priority)

    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="keyword_research_all_accounts.xlsx"'
        },
    )


@router.post("/sheets")
async def export_to_sheets(
    account_id: int = Query(...),
    spreadsheet_url: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Export to Google Sheets (requires Sheets API auth)."""
    # Placeholder — requires additional Google Sheets API integration
    return {
        "status": "not_implemented",
        "message": "Google Sheets export requires additional OAuth scope setup. "
                   "Use CSV or Excel export for now.",
    }
