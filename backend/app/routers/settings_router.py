"""Settings management routes."""

from fastapi import APIRouter

from app.config import settings
from app.models.schemas import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
async def get_settings():
    """Get current research and scoring settings."""
    return SettingsOut(
        lookback_days=settings.default_lookback_days,
        min_seed_conversions=settings.default_min_seed_conversions,
        min_seed_clicks=settings.default_min_seed_clicks,
        max_seeds_per_account=settings.default_max_seeds_per_account,
        min_monthly_searches=settings.default_min_monthly_searches,
        high_priority_threshold=settings.high_priority_threshold,
        medium_priority_threshold=settings.medium_priority_threshold,
        low_priority_threshold=settings.low_priority_threshold,
        volume_weight=settings.volume_weight,
        competition_weight=settings.competition_weight,
        cpc_weight=settings.cpc_weight,
        relevance_weight=settings.relevance_weight,
    )


@router.put("", response_model=SettingsOut)
async def update_settings(body: SettingsUpdate):
    """Update research and scoring settings."""
    # In production, persist these to database. For now, update in-memory.
    if body.lookback_days is not None:
        settings.default_lookback_days = body.lookback_days
    if body.min_seed_conversions is not None:
        settings.default_min_seed_conversions = body.min_seed_conversions
    if body.min_seed_clicks is not None:
        settings.default_min_seed_clicks = body.min_seed_clicks
    if body.max_seeds_per_account is not None:
        settings.default_max_seeds_per_account = body.max_seeds_per_account
    if body.min_monthly_searches is not None:
        settings.default_min_monthly_searches = body.min_monthly_searches
    if body.high_priority_threshold is not None:
        settings.high_priority_threshold = body.high_priority_threshold
    if body.medium_priority_threshold is not None:
        settings.medium_priority_threshold = body.medium_priority_threshold
    if body.low_priority_threshold is not None:
        settings.low_priority_threshold = body.low_priority_threshold
    if body.volume_weight is not None:
        settings.volume_weight = body.volume_weight
    if body.competition_weight is not None:
        settings.competition_weight = body.competition_weight
    if body.cpc_weight is not None:
        settings.cpc_weight = body.cpc_weight
    if body.relevance_weight is not None:
        settings.relevance_weight = body.relevance_weight

    return await get_settings()
