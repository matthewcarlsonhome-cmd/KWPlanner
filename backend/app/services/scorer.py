"""Keyword scoring engine for pool/spa industry relevance."""

import statistics
from typing import Optional, List, Dict

HIGH_RELEVANCE_TERMS = [
    "pool builder", "pool construction", "pool contractor", "pool company",
    "pool installation", "pool remodel", "pool renovation", "pool repair",
    "pool resurfacing", "pool plastering", "pool replastering", "pool service",
    "pool cleaning", "pool maintenance", "pool opening", "pool closing",
    "inground pool", "gunite pool", "fiberglass pool", "vinyl pool",
    "custom pool", "concrete pool", "saltwater pool", "infinity pool",
    "plunge pool", "cocktail pool", "lap pool", "sport pool",
    "pool deck", "pool coping", "pool tile", "pool plaster",
    "pool enclosure", "pool cover", "pool heater", "pool pump",
    "pool filter", "pool light", "pool automation", "pool fence",
    "pebble tec", "pebble sheen", "diamond brite", "quartz finish",
    "hot tub", "spa", "swim spa", "jacuzzi", "hot tub dealer",
    "hot tub sale", "hot tub near me", "hot tub store", "hot tub service",
    "hot tub repair", "hot tub delivery", "hot tub installation",
    "pool cost", "pool price", "pool quote", "pool estimate",
    "pool financing", "pool near me", "pool builders near me",
    "how much does a pool cost", "pool builder cost",
    "outdoor living", "backyard pool", "swimming pool", "pool design",
    "pool patio", "pool landscape",
]

MEDIUM_RELEVANCE_TERMS = [
    "backyard", "outdoor", "landscape", "hardscape", "paver",
    "concrete", "deck", "pergola", "gazebo", "fence",
    "water feature", "fountain", "fire pit", "outdoor kitchen",
    "screen enclosure", "lanai", "retaining wall", "travertine",
    "flagstone", "stamped concrete", "kool deck",
]

NEGATIVE_TERMS = [
    "pool table", "billiard", "car pool", "carpool", "gene pool",
    "pool party", "pool game", "pool noodle", "pool float", "pool toy",
    "inflatable", "intex", "bestway", "above ground",
    "walmart", "amazon", "home depot", "lowes", "craigslist",
    "diy", "how to", "youtube", "tutorial", "video",
    "jobs", "hiring", "career", "salary", "employment",
    "used", "free", "cheap", "wholesale", "coupon",
]


def score_volume(avg_monthly_searches: Optional[int]) -> int:
    """Score based on average monthly search volume. Returns 0-25."""
    if avg_monthly_searches is None:
        return 0
    if avg_monthly_searches >= 500:
        return 25
    if avg_monthly_searches >= 200:
        return 20
    if avg_monthly_searches >= 100:
        return 15
    if avg_monthly_searches >= 50:
        return 10
    if avg_monthly_searches >= 10:
        return 5
    return 0


def score_competition(competition_index: Optional[int]) -> int:
    """Score based on competition index (0-100). Lower = better. Returns 0-25."""
    if competition_index is None:
        return 15  # default to medium if unknown
    if competition_index <= 33:
        return 25
    if competition_index <= 66:
        return 15
    return 10


def score_cpc_efficiency(
    low_cpc_micros: Optional[int],
    high_cpc_micros: Optional[int],
    account_avg_cpc: Optional[float],
) -> int:
    """Score CPC relative to account average. Returns 0-25."""
    if low_cpc_micros is None or high_cpc_micros is None or not account_avg_cpc:
        return 15  # default to medium if unknown

    idea_cpc = ((low_cpc_micros + high_cpc_micros) / 2) / 1_000_000
    if account_avg_cpc <= 0:
        return 15

    ratio = idea_cpc / account_avg_cpc
    if ratio < 0.5:
        return 25
    if ratio < 0.8:
        return 20
    if ratio <= 1.2:
        return 15
    if ratio <= 2.0:
        return 10
    return 5


def score_relevance(keyword_text: str) -> tuple[int, str]:
    """
    Score relevance to pool/spa industry. Returns (score 0-25, category).
    Negative terms take priority over positive matches.
    """
    kw_lower = keyword_text.lower()

    # Check negatives first (they take priority)
    for term in NEGATIVE_TERMS:
        if term in kw_lower:
            return 0, "negative_candidate"

    # Check high relevance
    for term in HIGH_RELEVANCE_TERMS:
        if term in kw_lower:
            return 25, "high_relevance"

    # Check medium relevance
    for term in MEDIUM_RELEVANCE_TERMS:
        if term in kw_lower:
            return 15, "medium_relevance"

    return 8, "low_relevance"


def classify_priority(total_score: int) -> str:
    """Classify keyword idea priority based on total score."""
    if total_score >= 75:
        return "HIGH"
    if total_score >= 50:
        return "MEDIUM"
    if total_score >= 25:
        return "LOW"
    return "SKIP"


def detect_seasonality(monthly_volumes: Optional[List[Dict]]) -> tuple[bool, Optional[str]]:
    """
    Detect seasonal patterns from 12-month volume data.
    Returns (is_seasonal, peak_month_name).
    """
    if not monthly_volumes or len(monthly_volumes) < 3:
        return False, None

    volumes = []
    for mv in monthly_volumes:
        vol = mv.get("searches") or mv.get("monthly_searches", 0)
        volumes.append(vol if vol else 0)

    if not volumes or all(v == 0 for v in volumes):
        return False, None

    mean = statistics.mean(volumes)
    if mean == 0:
        return False, None

    std_dev = statistics.stdev(volumes) if len(volumes) > 1 else 0
    cv = std_dev / mean

    if cv > 0.5:
        peak_idx = volumes.index(max(volumes))
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        # monthly_volumes may contain month info
        if peak_idx < len(monthly_volumes) and "month" in monthly_volumes[peak_idx]:
            month_num = monthly_volumes[peak_idx]["month"]
            if isinstance(month_num, int) and 1 <= month_num <= 12:
                return True, month_names[month_num - 1]
        # fallback: use index
        if peak_idx < 12:
            return True, month_names[peak_idx]
        return True, None

    return False, None


def suggest_match_type(keyword_text: str) -> str:
    """Suggest match type based on keyword length."""
    word_count = len(keyword_text.split())
    if word_count >= 3:
        return "EXACT"
    return "PHRASE"


def suggest_ad_group(
    keyword_text: str,
    ad_groups: Dict[str, List[str]],
) -> str:
    """
    Suggest which ad group a keyword should go into.
    ad_groups: {ad_group_name: [keyword1, keyword2, ...]}
    """
    if not ad_groups:
        return f"NEW AD GROUP: {keyword_text.split()[0].title() if keyword_text else 'General'}"

    kw_tokens = set(keyword_text.lower().split())
    best_group = None
    best_overlap = 0.0

    for group_name, group_keywords in ad_groups.items():
        group_tokens = set()
        for gk in group_keywords:
            group_tokens.update(gk.lower().split())

        if not kw_tokens:
            continue
        overlap = len(kw_tokens & group_tokens) / len(kw_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_group = group_name

    if best_overlap > 0.3 and best_group:
        return best_group

    primary_theme = " ".join(keyword_text.split()[:2]).title()
    return f"NEW AD GROUP: {primary_theme}"


def score_keyword(
    keyword_text: str,
    avg_monthly_searches: Optional[int],
    competition_index: Optional[int],
    low_cpc_micros: Optional[int],
    high_cpc_micros: Optional[int],
    account_avg_cpc: Optional[float],
    monthly_volumes: Optional[List[Dict]] = None,
    ad_groups: Optional[Dict[str, List[str]]] = None,
) -> dict:
    """
    Score a single keyword idea across all dimensions.
    Returns a dict with all scoring fields.
    """
    vol_score = score_volume(avg_monthly_searches)
    comp_score = score_competition(competition_index)
    cpc_score = score_cpc_efficiency(low_cpc_micros, high_cpc_micros, account_avg_cpc)
    rel_score, rel_category = score_relevance(keyword_text)

    total = vol_score + comp_score + cpc_score + rel_score

    # Negative candidates are always SKIP regardless of other scores
    if rel_category == "negative_candidate":
        priority = "SKIP"
    else:
        priority = classify_priority(total)

    is_seasonal, peak_month = detect_seasonality(monthly_volumes)
    match_type = suggest_match_type(keyword_text)
    ad_group = suggest_ad_group(keyword_text, ad_groups or {})

    return {
        "volume_score": vol_score,
        "competition_score": comp_score,
        "cpc_score": cpc_score,
        "relevance_score": rel_score,
        "total_score": total,
        "priority": priority,
        "relevance_category": rel_category,
        "is_seasonal": is_seasonal,
        "peak_month": peak_month,
        "suggested_match_type": match_type,
        "suggested_ad_group": ad_group,
    }
