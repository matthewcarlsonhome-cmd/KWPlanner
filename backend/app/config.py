"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    app_name: str = "MCC Keyword Research Platform"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"

    # Database
    database_url: str = "sqlite+aiosqlite:///./kwplanner.db"

    # Google Ads API
    google_ads_developer_token: str = ""
    google_ads_login_customer_id: str = ""  # MCC ID, no dashes

    # Google OAuth2
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/callback"

    # Research defaults
    default_lookback_days: int = 90
    default_min_seed_conversions: float = 2.0
    default_min_seed_clicks: int = 10
    default_max_seeds_per_account: int = 15
    default_min_monthly_searches: int = 50
    high_priority_threshold: int = 75
    medium_priority_threshold: int = 50
    low_priority_threshold: int = 25

    # Scoring weights (must sum to 100)
    volume_weight: int = 25
    competition_weight: int = 25
    cpc_weight: int = 25
    relevance_weight: int = 25

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
