"""Pydantic schemas for request/response validation."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# --- Account ---
class AccountBase(BaseModel):
    google_ads_id: str
    name: str
    is_active: bool = True
    avg_cpc: Optional[float] = None
    avg_cpa: Optional[float] = None
    monthly_budget: Optional[float] = None
    geo_target_ids: Optional[List[str]] = None


class AccountOut(AccountBase):
    id: int
    last_synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    # Derived stats from latest run
    latest_run_date: Optional[datetime] = None
    ideas_count: Optional[int] = None
    ideas_high: Optional[int] = None
    ideas_medium: Optional[int] = None
    approved_count: Optional[int] = None
    pending_count: Optional[int] = None

    model_config = {"from_attributes": True}


class AccountDetail(AccountOut):
    runs: List["ResearchRunOut"] = []

    model_config = {"from_attributes": True}


# --- Research Run ---
class ResearchRunCreate(BaseModel):
    account_id: Optional[int] = None  # None means "all"


class ResearchRunOut(BaseModel):
    id: int
    account_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "running"
    settings: Optional[dict] = None
    seed_count: Optional[int] = None
    ideas_generated: Optional[int] = None
    ideas_high: Optional[int] = None
    ideas_medium: Optional[int] = None
    ideas_low: Optional[int] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class RunStatusOut(BaseModel):
    run_id: int
    status: str
    accounts_completed: int = 0
    accounts_total: int = 0
    current_account: Optional[str] = None


# --- Seed Keyword ---
class SeedKeywordOut(BaseModel):
    id: int
    keyword: str
    match_type: Optional[str] = None
    conversions: Optional[float] = None
    clicks: Optional[int] = None
    cost: Optional[float] = None
    quality_score: Optional[int] = None
    campaign: Optional[str] = None
    ad_group: Optional[str] = None

    model_config = {"from_attributes": True}


# --- Keyword Idea ---
class KeywordIdeaOut(BaseModel):
    id: int
    run_id: int
    account_id: int
    keyword_text: str
    avg_monthly_searches: Optional[int] = None
    competition: Optional[str] = None
    competition_index: Optional[int] = None
    low_cpc_micros: Optional[int] = None
    high_cpc_micros: Optional[int] = None
    monthly_volumes: Optional[list] = None
    volume_score: Optional[int] = None
    competition_score: Optional[int] = None
    cpc_score: Optional[int] = None
    relevance_score: Optional[int] = None
    total_score: Optional[int] = None
    priority: Optional[str] = None
    relevance_category: Optional[str] = None
    suggested_match_type: Optional[str] = None
    suggested_ad_group: Optional[str] = None
    already_exists: bool = False
    already_negative: bool = False
    is_seasonal: bool = False
    peak_month: Optional[str] = None
    created_at: Optional[datetime] = None
    # Latest decision
    decision_status: Optional[str] = None
    decision_by: Optional[str] = None
    decision_notes: Optional[str] = None

    model_config = {"from_attributes": True}


class KeywordIdeaPage(BaseModel):
    items: List[KeywordIdeaOut]
    total: int
    page: int
    per_page: int
    pages: int


# --- Decision ---
class DecisionCreate(BaseModel):
    keyword_idea_ids: List[int]
    decision: str  # approved, rejected, watchlist
    decided_by: Optional[str] = None
    notes: Optional[str] = None


class DecisionUpdate(BaseModel):
    decision: Optional[str] = None
    implemented_at: Optional[datetime] = None
    notes: Optional[str] = None


class DecisionOut(BaseModel):
    id: int
    keyword_idea_id: int
    account_id: int
    decision: str
    decided_by: Optional[str] = None
    notes: Optional[str] = None
    implemented_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    keyword_text: Optional[str] = None

    model_config = {"from_attributes": True}


# --- Export ---
class ExportRequest(BaseModel):
    account_id: int
    priority: Optional[List[str]] = None
    format: str = "csv"


class ExportAllRequest(BaseModel):
    format: str = "xlsx"
    priority: Optional[List[str]] = None


class SheetsExportRequest(BaseModel):
    account_id: int
    spreadsheet_url: str


# --- Negative Flag ---
class NegativeFlagOut(BaseModel):
    id: int
    keyword_idea_id: int
    account_id: int
    keyword_text: str
    reason: Optional[str] = None
    suggested_scope: Optional[str] = None
    decided: str = "pending"
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Compare ---
class CompareResult(BaseModel):
    new_ideas: List[KeywordIdeaOut] = []
    removed_ideas: List[KeywordIdeaOut] = []
    score_changes: List[dict] = []


# --- Settings ---
class SettingsOut(BaseModel):
    lookback_days: int
    min_seed_conversions: float
    min_seed_clicks: int
    max_seeds_per_account: int
    min_monthly_searches: int
    high_priority_threshold: int
    medium_priority_threshold: int
    low_priority_threshold: int
    volume_weight: int
    competition_weight: int
    cpc_weight: int
    relevance_weight: int


class SettingsUpdate(BaseModel):
    lookback_days: Optional[int] = None
    min_seed_conversions: Optional[float] = None
    min_seed_clicks: Optional[int] = None
    max_seeds_per_account: Optional[int] = None
    min_monthly_searches: Optional[int] = None
    high_priority_threshold: Optional[int] = None
    medium_priority_threshold: Optional[int] = None
    low_priority_threshold: Optional[int] = None
    volume_weight: Optional[int] = None
    competition_weight: Optional[int] = None
    cpc_weight: Optional[int] = None
    relevance_weight: Optional[int] = None


# --- Import ---
class ImportOut(BaseModel):
    id: int
    account_id: Optional[int] = None
    file_name: str
    file_type: str
    uploaded_by: Optional[str] = None
    row_count: Optional[int] = None
    column_mapping: Optional[dict] = None
    status: str = "pending"
    error_message: Optional[str] = None
    account_name: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ImportUploadResponse(BaseModel):
    upload_id: int
    file_name: str
    file_type: str
    row_count: int
    detected_columns: List[str]
    column_mapping: dict
    preview: List[dict]


class ImportConfirmRequest(BaseModel):
    upload_id: int
    column_mapping: dict
    account_name: str


class ImportedSearchTermOut(BaseModel):
    id: int
    import_id: int
    account_id: Optional[int] = None
    search_term: str
    campaign: Optional[str] = None
    ad_group: Optional[str] = None
    matched_keyword: Optional[str] = None
    match_type_triggered: Optional[str] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    cost: Optional[float] = None
    conversions: Optional[float] = None
    conv_rate: Optional[float] = None
    ctr: Optional[float] = None
    recommended_match_type: Optional[str] = None
    match_type_reason: Optional[str] = None
    relevance_score: Optional[int] = None
    relevance_category: Optional[str] = None
    priority: Optional[str] = None
    suggested_ad_group: Optional[str] = None
    is_duplicate: bool = False
    is_negative_candidate: bool = False
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ImportResultsPage(BaseModel):
    items: List[ImportedSearchTermOut]
    total: int
    page: int
    per_page: int
    pages: int


# --- Auth ---
class UserInfo(BaseModel):
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    is_authenticated: bool = True
