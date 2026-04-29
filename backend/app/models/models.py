"""SQLAlchemy ORM models matching the database schema from the spec."""

from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Text, DateTime, BigInteger,
    ForeignKey, Index, JSON, Float
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    google_ads_id = Column(String(20), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    avg_cpc = Column(Numeric(10, 2))
    avg_cpa = Column(Numeric(10, 2))
    monthly_budget = Column(Numeric(10, 2))
    geo_target_ids = Column(JSON, default=list)  # stored as JSON array for SQLite
    last_synced_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    research_runs = relationship("ResearchRun", back_populates="account")
    keyword_ideas = relationship("KeywordIdea", back_populates="account")
    decisions = relationship("Decision", back_populates="account")
    negative_flags = relationship("NegativeFlag", back_populates="account")
    imports = relationship("Import", back_populates="account")
    imported_search_terms = relationship("ImportedSearchTerm", back_populates="account")


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    completed_at = Column(DateTime)
    status = Column(String(20), default="running")
    settings = Column(JSON)
    seed_count = Column(Integer)
    ideas_generated = Column(Integer)
    ideas_high = Column(Integer)
    ideas_medium = Column(Integer)
    ideas_low = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    account = relationship("Account", back_populates="research_runs")
    seed_keywords = relationship("SeedKeyword", back_populates="run", cascade="all, delete-orphan")
    keyword_ideas = relationship("KeywordIdea", back_populates="run", cascade="all, delete-orphan")


class SeedKeyword(Base):
    __tablename__ = "seed_keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("research_runs.id", ondelete="CASCADE"))
    keyword = Column(Text, nullable=False)
    match_type = Column(String(20))
    conversions = Column(Numeric(10, 2))
    clicks = Column(Integer)
    cost = Column(Numeric(10, 2))
    quality_score = Column(Integer)
    campaign = Column(String(255))
    ad_group = Column(String(255))

    run = relationship("ResearchRun", back_populates="seed_keywords")


class KeywordIdea(Base):
    __tablename__ = "keyword_ideas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("research_runs.id", ondelete="CASCADE"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    keyword_text = Column(Text, nullable=False)
    avg_monthly_searches = Column(Integer)
    competition = Column(String(10))
    competition_index = Column(Integer)
    low_cpc_micros = Column(BigInteger)
    high_cpc_micros = Column(BigInteger)
    monthly_volumes = Column(JSON)

    # Scoring
    volume_score = Column(Integer)
    competition_score = Column(Integer)
    cpc_score = Column(Integer)
    relevance_score = Column(Integer)
    total_score = Column(Integer)
    priority = Column(String(10))
    relevance_category = Column(String(20))

    # Context
    suggested_match_type = Column(String(10))
    suggested_ad_group = Column(String(255))
    already_exists = Column(Boolean, default=False)
    already_negative = Column(Boolean, default=False)

    # Seasonal
    is_seasonal = Column(Boolean, default=False)
    peak_month = Column(String(20))

    created_at = Column(DateTime, server_default=func.now())

    run = relationship("ResearchRun", back_populates="keyword_ideas")
    account = relationship("Account", back_populates="keyword_ideas")
    decisions = relationship("Decision", back_populates="keyword_idea")
    negative_flags = relationship("NegativeFlag", back_populates="keyword_idea")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword_idea_id = Column(Integer, ForeignKey("keyword_ideas.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    decision = Column(String(20), nullable=False)
    decided_by = Column(String(100))
    notes = Column(Text)
    implemented_at = Column(DateTime)
    decided_at = Column(DateTime, server_default=func.now())

    keyword_idea = relationship("KeywordIdea", back_populates="decisions")
    account = relationship("Account", back_populates="decisions")


class NegativeFlag(Base):
    __tablename__ = "negative_flags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword_idea_id = Column(Integer, ForeignKey("keyword_ideas.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    keyword_text = Column(Text, nullable=False)
    reason = Column(Text)
    suggested_scope = Column(String(20))
    decided = Column(String(20), default="pending")
    decided_by = Column(String(100))
    decided_at = Column(DateTime)

    keyword_idea = relationship("KeywordIdea", back_populates="negative_flags")
    account = relationship("Account", back_populates="negative_flags")


class Import(Base):
    __tablename__ = "imports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)  # keywords, search_terms, campaign_structure
    uploaded_by = Column(String(100))
    row_count = Column(Integer)
    column_mapping = Column(JSON)
    status = Column(String(20), default="pending")  # pending, confirmed, analyzed, error
    error_message = Column(Text)
    account_name = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())

    account = relationship("Account", back_populates="imports")
    imported_search_terms = relationship("ImportedSearchTerm", back_populates="import_record", cascade="all, delete-orphan")


class ImportedSearchTerm(Base):
    __tablename__ = "imported_search_terms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    import_id = Column(Integer, ForeignKey("imports.id", ondelete="CASCADE"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    search_term = Column(Text, nullable=False)
    campaign = Column(String(255))
    ad_group = Column(String(255))
    matched_keyword = Column(String(255))
    match_type_triggered = Column(String(50))
    impressions = Column(Integer)
    clicks = Column(Integer)
    cost = Column(Numeric(10, 2))
    conversions = Column(Numeric(10, 2))
    conv_rate = Column(Numeric(5, 4))
    ctr = Column(Numeric(5, 4))
    recommended_match_type = Column(String(10))  # EXACT, PHRASE, SKIP, NEGATIVE
    match_type_reason = Column(Text)
    relevance_score = Column(Integer)
    relevance_category = Column(String(20))
    priority = Column(String(10))
    suggested_ad_group = Column(String(255))
    is_duplicate = Column(Boolean, default=False)
    is_negative_candidate = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    import_record = relationship("Import", back_populates="imported_search_terms")
    account = relationship("Account", back_populates="imported_search_terms")


# Indexes
Index("idx_keyword_ideas_account", KeywordIdea.account_id)
Index("idx_keyword_ideas_priority", KeywordIdea.priority)
Index("idx_keyword_ideas_score", KeywordIdea.total_score.desc())
Index("idx_decisions_account", Decision.account_id)
Index("idx_research_runs_account", ResearchRun.account_id)
Index("idx_imports_account", Import.account_id)
Index("idx_imported_search_terms_import", ImportedSearchTerm.import_id)
Index("idx_imported_search_terms_account", ImportedSearchTerm.account_id)
