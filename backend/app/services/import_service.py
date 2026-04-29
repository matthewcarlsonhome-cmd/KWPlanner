"""Import service for CSV/XLSX file parsing, column detection, and analysis."""

import csv
import io
import re
from typing import List, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Import, ImportedSearchTerm, Account
from app.services.scorer import score_relevance, NEGATIVE_TERMS, classify_priority, suggest_ad_group
from app.services.match_type_recommender import recommend_match_type

SEARCH_TERM_COLUMN_ALIASES = {
    "search_term": ["search term", "search terms", "search query", "query", "search term report"],
    "campaign": ["campaign", "campaign name"],
    "ad_group": ["ad group", "ad group name", "adgroup"],
    "matched_keyword": ["keyword", "matched keyword", "triggering keyword"],
    "match_type_triggered": ["match type", "match_type", "keyword match type"],
    "impressions": ["impressions", "impr", "impr."],
    "clicks": ["clicks"],
    "cost": ["cost", "cost (usd)", "spend", "total cost"],
    "conversions": ["conversions", "conv", "conv.", "total conversions"],
    "conv_rate": ["conv. rate", "conv rate", "conversion rate", "cvr"],
    "ctr": ["ctr", "click-through rate", "click through rate"],
}

KEYWORD_COLUMN_ALIASES = {
    "keyword": ["keyword", "keyword text"],
    "campaign": ["campaign", "campaign name"],
    "ad_group": ["ad group", "ad group name", "adgroup"],
    "match_type": ["match type", "match_type", "keyword match type"],
    "status": ["status", "keyword status"],
    "max_cpc": ["max cpc", "max. cpc", "max cpc bid", "bid"],
    "impressions": ["impressions", "impr", "impr."],
    "clicks": ["clicks"],
    "cost": ["cost", "cost (usd)", "spend", "total cost"],
    "conversions": ["conversions", "conv", "conv.", "total conversions"],
    "conv_rate": ["conv. rate", "conv rate", "conversion rate", "cvr"],
    "quality_score": ["quality score", "qs", "qual. score"],
    "avg_cpc": ["avg. cpc", "avg cpc", "average cpc"],
}


def _normalize_header(header: str) -> str:
    """Normalize a column header for fuzzy matching."""
    return re.sub(r'[^a-z0-9 ]', '', header.lower()).strip()


def detect_columns(headers: List[str], file_type: str) -> Dict[str, str]:
    """
    Auto-detect column mapping by fuzzy-matching header names.
    Returns {internal_field_name: original_header_name}
    """
    aliases = SEARCH_TERM_COLUMN_ALIASES if file_type == "search_terms" else KEYWORD_COLUMN_ALIASES
    mapping = {}

    normalized_headers = {_normalize_header(h): h for h in headers}

    for field, field_aliases in aliases.items():
        for alias in field_aliases:
            normalized_alias = _normalize_header(alias)
            if normalized_alias in normalized_headers:
                mapping[field] = normalized_headers[normalized_alias]
                break

    return mapping


def parse_csv_content(content: bytes) -> Tuple[List[str], List[Dict]]:
    """Parse CSV file content into headers and rows."""
    text = content.decode("utf-8-sig")
    # Skip Google Ads report header rows (lines starting with non-data content)
    lines = text.strip().split("\n")
    data_start = 0
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith("Total:") and not line.startswith("Totals:"):
            try:
                reader = csv.DictReader(io.StringIO("\n".join(lines[i:])))
                headers = reader.fieldnames
                if headers and len(headers) > 1:
                    data_start = i
                    break
            except Exception:
                continue

    reader = csv.DictReader(io.StringIO("\n".join(lines[data_start:])))
    headers = list(reader.fieldnames or [])
    rows = []
    for row in reader:
        # Skip summary/total rows
        first_val = list(row.values())[0] if row else ""
        if first_val and ("total" in str(first_val).lower()):
            continue
        rows.append(dict(row))

    return headers, rows


def parse_xlsx_content(content: bytes) -> Tuple[List[str], List[Dict]]:
    """Parse XLSX file content into headers and rows."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    headers = []

    # Find the header row (first row with multiple non-empty cells)
    for row_values in rows_iter:
        non_empty = [str(v).strip() for v in row_values if v is not None and str(v).strip()]
        if len(non_empty) >= 2:
            headers = [str(v).strip() if v else f"Column_{i}" for i, v in enumerate(row_values)]
            break

    if not headers:
        return [], []

    rows = []
    for row_values in rows_iter:
        row_dict = {}
        for i, val in enumerate(row_values):
            if i < len(headers):
                row_dict[headers[i]] = val
        # Skip empty or total rows
        first_val = str(list(row_dict.values())[0]) if row_dict else ""
        if first_val and "total" in first_val.lower():
            continue
        if any(v is not None and str(v).strip() for v in row_dict.values()):
            rows.append(row_dict)

    wb.close()
    return headers, rows


def _parse_numeric(val, default=0) -> float:
    """Parse a numeric value from potentially formatted strings like '$1,234.56' or '5.98%'."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s == "--":
        return default
    s = s.replace("$", "").replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def _parse_int(val, default=0) -> int:
    """Parse an integer value."""
    return int(_parse_numeric(val, default))


def extract_search_term_data(row: Dict, column_mapping: Dict) -> Dict:
    """Extract and normalize a search term row using column mapping."""
    def get(field):
        col = column_mapping.get(field)
        return row.get(col) if col else None

    impressions = _parse_int(get("impressions"))
    clicks = _parse_int(get("clicks"))
    cost = _parse_numeric(get("cost"))
    conversions = _parse_numeric(get("conversions"))

    ctr = 0.0
    raw_ctr = get("ctr")
    if raw_ctr is not None:
        ctr = _parse_numeric(raw_ctr) / 100.0 if _parse_numeric(raw_ctr) > 1 else _parse_numeric(raw_ctr)
    elif impressions > 0:
        ctr = clicks / impressions

    conv_rate = 0.0
    raw_cr = get("conv_rate")
    if raw_cr is not None:
        conv_rate = _parse_numeric(raw_cr) / 100.0 if _parse_numeric(raw_cr) > 1 else _parse_numeric(raw_cr)
    elif clicks > 0:
        conv_rate = conversions / clicks

    return {
        "search_term": str(get("search_term") or "").strip(),
        "campaign": str(get("campaign") or "").strip(),
        "ad_group": str(get("ad_group") or "").strip(),
        "matched_keyword": str(get("matched_keyword") or "").strip(),
        "match_type_triggered": str(get("match_type_triggered") or "").strip(),
        "impressions": impressions,
        "clicks": clicks,
        "cost": cost,
        "conversions": conversions,
        "conv_rate": conv_rate,
        "ctr": ctr,
    }


def analyze_search_term(
    data: Dict,
    existing_keywords: Optional[set] = None,
    ad_groups: Optional[Dict[str, List[str]]] = None,
) -> Dict:
    """Run match type recommendation and relevance scoring on a search term."""
    search_term = data["search_term"]
    if not search_term:
        return {**data, "recommended_match_type": "SKIP", "match_type_reason": "Empty search term"}

    # Match type recommendation
    rec_type, rec_reason = recommend_match_type(
        search_term=search_term,
        clicks=data.get("clicks", 0),
        conversions=data.get("conversions", 0),
        conv_rate=data.get("conv_rate", 0),
        ctr=data.get("ctr", 0),
        impressions=data.get("impressions", 0),
    )

    # Relevance scoring
    rel_score, rel_category = score_relevance(search_term)

    # Check for negative candidate
    is_negative = rel_category == "negative_candidate"
    if is_negative:
        rec_type = "NEGATIVE"
        rec_reason = "Matched negative keyword pattern"

    # Priority based on a simplified score
    if is_negative:
        priority = "SKIP"
    else:
        simple_score = rel_score + min(data.get("clicks", 0), 25) + (25 if data.get("conversions", 0) >= 1 else 0)
        priority = classify_priority(simple_score)

    # Duplicate detection
    is_duplicate = False
    if existing_keywords:
        is_duplicate = search_term.lower().strip() in existing_keywords

    # Ad group suggestion
    suggested_ag = suggest_ad_group(search_term, ad_groups or {})

    return {
        **data,
        "recommended_match_type": rec_type,
        "match_type_reason": rec_reason,
        "relevance_score": rel_score,
        "relevance_category": rel_category,
        "priority": priority,
        "suggested_ad_group": suggested_ag,
        "is_duplicate": is_duplicate,
        "is_negative_candidate": is_negative,
    }


async def create_import_record(
    db: AsyncSession,
    file_name: str,
    file_type: str,
    row_count: int,
    column_mapping: Dict,
    uploaded_by: Optional[str] = None,
) -> Import:
    """Create an import record in the database."""
    imp = Import(
        file_name=file_name,
        file_type=file_type,
        row_count=row_count,
        column_mapping=column_mapping,
        uploaded_by=uploaded_by,
        status="pending",
    )
    db.add(imp)
    await db.commit()
    await db.refresh(imp)
    return imp


async def confirm_import(
    db: AsyncSession,
    import_id: int,
    column_mapping: Dict,
    account_name: str,
) -> Import:
    """Confirm column mapping and assign account for an import."""
    result = await db.execute(select(Import).where(Import.id == import_id))
    imp = result.scalar_one_or_none()
    if not imp:
        raise ValueError(f"Import {import_id} not found")

    # Find or create account
    acct_result = await db.execute(select(Account).where(Account.name == account_name))
    account = acct_result.scalar_one_or_none()
    if not account:
        account = Account(
            google_ads_id=f"IMPORT-{import_id}",
            name=account_name,
            is_active=True,
        )
        db.add(account)
        await db.flush()

    imp.column_mapping = column_mapping
    imp.account_id = account.id
    imp.account_name = account_name
    imp.status = "confirmed"
    await db.commit()
    await db.refresh(imp)
    return imp


async def run_analysis(
    db: AsyncSession,
    import_id: int,
    rows: List[Dict],
) -> Import:
    """Run analysis on confirmed import data and save results."""
    result = await db.execute(select(Import).where(Import.id == import_id))
    imp = result.scalar_one_or_none()
    if not imp:
        raise ValueError(f"Import {import_id} not found")
    if not imp.column_mapping:
        raise ValueError("Import has no column mapping — confirm first")

    column_mapping = imp.column_mapping

    # Build existing keywords set for duplicate detection
    existing_keywords = set()
    ad_groups_map: Dict[str, List[str]] = {}

    # Extract and analyze each row
    analyzed = []
    for row in rows:
        data = extract_search_term_data(row, column_mapping)
        if not data["search_term"]:
            continue
        result_data = analyze_search_term(data, existing_keywords, ad_groups_map)
        analyzed.append(result_data)
        # Track keywords for cross-reference
        existing_keywords.add(data["search_term"].lower().strip())
        # Build ad group map
        ag = data.get("ad_group", "")
        if ag:
            if ag not in ad_groups_map:
                ad_groups_map[ag] = []
            ad_groups_map[ag].append(data["search_term"])

    # Save results
    for item in analyzed:
        ist = ImportedSearchTerm(
            import_id=imp.id,
            account_id=imp.account_id,
            search_term=item["search_term"],
            campaign=item.get("campaign"),
            ad_group=item.get("ad_group"),
            matched_keyword=item.get("matched_keyword"),
            match_type_triggered=item.get("match_type_triggered"),
            impressions=item.get("impressions"),
            clicks=item.get("clicks"),
            cost=item.get("cost"),
            conversions=item.get("conversions"),
            conv_rate=item.get("conv_rate"),
            ctr=item.get("ctr"),
            recommended_match_type=item.get("recommended_match_type"),
            match_type_reason=item.get("match_type_reason"),
            relevance_score=item.get("relevance_score"),
            relevance_category=item.get("relevance_category"),
            priority=item.get("priority"),
            suggested_ad_group=item.get("suggested_ad_group"),
            is_duplicate=item.get("is_duplicate", False),
            is_negative_candidate=item.get("is_negative_candidate", False),
        )
        db.add(ist)

    imp.status = "analyzed"
    await db.commit()
    await db.refresh(imp)
    return imp


def export_results_csv(results: List[Dict]) -> str:
    """Export analysis results as CSV string."""
    if not results:
        return ""

    output = io.StringIO()
    fieldnames = [
        "Search Term", "Campaign", "Ad Group", "Matched Keyword",
        "Impressions", "Clicks", "Cost", "Conversions", "Conv. Rate", "CTR",
        "Recommended Match Type", "Reason", "Relevance Score", "Priority",
        "Suggested Ad Group", "Is Duplicate", "Is Negative Candidate",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for r in results:
        writer.writerow({
            "Search Term": r.get("search_term", ""),
            "Campaign": r.get("campaign", ""),
            "Ad Group": r.get("ad_group", ""),
            "Matched Keyword": r.get("matched_keyword", ""),
            "Impressions": r.get("impressions", 0),
            "Clicks": r.get("clicks", 0),
            "Cost": f"{r.get('cost', 0):.2f}",
            "Conversions": f"{r.get('conversions', 0):.1f}",
            "Conv. Rate": f"{r.get('conv_rate', 0):.2%}",
            "CTR": f"{r.get('ctr', 0):.2%}",
            "Recommended Match Type": r.get("recommended_match_type", ""),
            "Reason": r.get("match_type_reason", ""),
            "Relevance Score": r.get("relevance_score", 0),
            "Priority": r.get("priority", ""),
            "Suggested Ad Group": r.get("suggested_ad_group", ""),
            "Is Duplicate": "Yes" if r.get("is_duplicate") else "No",
            "Is Negative Candidate": "Yes" if r.get("is_negative_candidate") else "No",
        })

    return output.getvalue()
