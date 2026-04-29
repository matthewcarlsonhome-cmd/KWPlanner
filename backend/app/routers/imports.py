"""Import router — CSV/XLSX upload, column mapping, analysis, and results."""

import math
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Import, ImportedSearchTerm
from app.models.schemas import (
    ImportOut, ImportUploadResponse, ImportConfirmRequest,
    ImportedSearchTermOut, ImportResultsPage,
)
from app.services.import_service import (
    parse_csv_content, parse_xlsx_content, detect_columns,
    create_import_record, confirm_import, run_analysis,
    export_results_csv,
)

router = APIRouter(prefix="/api/import", tags=["import"])

# In-memory cache of parsed rows keyed by import_id for the confirm→analyze flow
_parsed_rows_cache: dict[int, list[dict]] = {}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/upload", response_model=ImportUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    file_type: str = Form("search_terms"),
    db: AsyncSession = Depends(get_db),
):
    """Upload a CSV or XLSX file and get column auto-detection preview."""
    if not file.filename:
        raise HTTPException(400, "No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("csv", "xlsx", "xls"):
        raise HTTPException(400, f"Unsupported file type: .{ext}. Use .csv or .xlsx")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large (max {MAX_FILE_SIZE // (1024*1024)}MB)")

    if ext == "csv":
        headers, rows = parse_csv_content(content)
    else:
        try:
            headers, rows = parse_xlsx_content(content)
        except Exception as e:
            raise HTTPException(400, f"Error parsing XLSX: {str(e)}")

    if not headers or not rows:
        raise HTTPException(400, "Could not parse file — no data found")

    column_mapping = detect_columns(headers, file_type)

    imp = await create_import_record(
        db=db,
        file_name=file.filename,
        file_type=file_type,
        row_count=len(rows),
        column_mapping=column_mapping,
    )

    _parsed_rows_cache[imp.id] = rows

    preview = rows[:10]

    return ImportUploadResponse(
        upload_id=imp.id,
        file_name=file.filename,
        file_type=file_type,
        row_count=len(rows),
        detected_columns=headers,
        column_mapping=column_mapping,
        preview=preview,
    )


@router.post("/confirm", response_model=ImportOut)
async def confirm_mapping(
    req: ImportConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """Confirm column mapping and assign account name."""
    try:
        imp = await confirm_import(
            db=db,
            import_id=req.upload_id,
            column_mapping=req.column_mapping,
            account_name=req.account_name,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    return ImportOut.model_validate(imp)


@router.post("/analyze")
async def analyze_import(
    upload_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Run analysis pipeline on a confirmed import."""
    rows = _parsed_rows_cache.get(upload_id)
    if not rows:
        raise HTTPException(400, "No cached data for this import. Please re-upload the file.")

    try:
        imp = await run_analysis(db=db, import_id=upload_id, rows=rows)
    except ValueError as e:
        raise HTTPException(400, str(e))

    _parsed_rows_cache.pop(upload_id, None)

    return {"status": "analyzed", "import_id": imp.id, "account_id": imp.account_id}


@router.get("/list/all", response_model=list[ImportOut])
async def list_imports(db: AsyncSession = Depends(get_db)):
    """List all imports."""
    result = await db.execute(
        select(Import).order_by(Import.created_at.desc())
    )
    imports = result.scalars().all()
    return [ImportOut.model_validate(i) for i in imports]


@router.get("/{import_id}", response_model=ImportOut)
async def get_import(import_id: int, db: AsyncSession = Depends(get_db)):
    """Get import record details."""
    result = await db.execute(select(Import).where(Import.id == import_id))
    imp = result.scalar_one_or_none()
    if not imp:
        raise HTTPException(404, "Import not found")
    return ImportOut.model_validate(imp)


@router.get("/{import_id}/results", response_model=ImportResultsPage)
async def get_import_results(
    import_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    priority: Optional[str] = Query(None),
    match_type: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("clicks"),
    sort_dir: Optional[str] = Query("desc"),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated import analysis results."""
    query = select(ImportedSearchTerm).where(ImportedSearchTerm.import_id == import_id)
    count_query = select(func.count(ImportedSearchTerm.id)).where(ImportedSearchTerm.import_id == import_id)

    if priority:
        query = query.where(ImportedSearchTerm.priority == priority.upper())
        count_query = count_query.where(ImportedSearchTerm.priority == priority.upper())
    if match_type:
        query = query.where(ImportedSearchTerm.recommended_match_type == match_type.upper())
        count_query = count_query.where(ImportedSearchTerm.recommended_match_type == match_type.upper())

    sort_col = getattr(ImportedSearchTerm, sort_by, ImportedSearchTerm.clicks)
    if sort_dir == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    pages = max(1, math.ceil(total / per_page))

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return ImportResultsPage(
        items=[ImportedSearchTermOut.model_validate(i) for i in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.delete("/{import_id}")
async def delete_import(import_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an import and all its data."""
    result = await db.execute(select(Import).where(Import.id == import_id))
    imp = result.scalar_one_or_none()
    if not imp:
        raise HTTPException(404, "Import not found")

    await db.execute(
        delete(ImportedSearchTerm).where(ImportedSearchTerm.import_id == import_id)
    )
    await db.delete(imp)
    await db.commit()

    _parsed_rows_cache.pop(import_id, None)
    return {"status": "deleted", "import_id": import_id}


@router.post("/{import_id}/export")
async def export_import_results(import_id: int, db: AsyncSession = Depends(get_db)):
    """Export import analysis results as CSV."""
    result = await db.execute(
        select(ImportedSearchTerm)
        .where(ImportedSearchTerm.import_id == import_id)
        .order_by(ImportedSearchTerm.clicks.desc())
    )
    items = result.scalars().all()

    if not items:
        raise HTTPException(404, "No results found for this import")

    rows = []
    for item in items:
        rows.append({
            "search_term": item.search_term,
            "campaign": item.campaign,
            "ad_group": item.ad_group,
            "matched_keyword": item.matched_keyword,
            "impressions": item.impressions,
            "clicks": item.clicks,
            "cost": float(item.cost) if item.cost else 0,
            "conversions": float(item.conversions) if item.conversions else 0,
            "conv_rate": float(item.conv_rate) if item.conv_rate else 0,
            "ctr": float(item.ctr) if item.ctr else 0,
            "recommended_match_type": item.recommended_match_type,
            "match_type_reason": item.match_type_reason,
            "relevance_score": item.relevance_score,
            "priority": item.priority,
            "suggested_ad_group": item.suggested_ad_group,
            "is_duplicate": item.is_duplicate,
            "is_negative_candidate": item.is_negative_candidate,
        })

    csv_content = export_results_csv(rows)

    imp_result = await db.execute(select(Import).where(Import.id == import_id))
    imp = imp_result.scalar_one_or_none()
    filename = f"import_{import_id}_results.csv"
    if imp and imp.account_name:
        safe_name = imp.account_name.replace(" ", "_").replace("/", "_")
        filename = f"{safe_name}_import_results.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
