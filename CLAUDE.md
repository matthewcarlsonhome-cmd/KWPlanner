# CLAUDE.md — KWPlanner Development Guide

## Project Summary

MCC Keyword Research Platform for SSP Digital. Manages ~40 pool/spa Google Ads
accounts. Uses the Google Ads API KeywordPlanIdeaService to discover untapped
keyword opportunities, scores them for pool/spa relevance, and presents them in
a web UI where the team can approve, reject, and export keywords.

**Status**: Core application built and tested. Never reached production due to
Google Cloud OAuth2 project setup (parent resource / Workspace org permissions)
blocking API credential creation.

---

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy (async), SQLite (dev) / PostgreSQL via Supabase (prod)
- **Frontend**: React 18, Tailwind CSS, Vite, React Router
- **API**: Google Ads API v18+ via `google-ads` Python client library
- **Deployment**: Render (render.yaml blueprint), Supabase for database
- **Tests**: pytest + pytest-asyncio, 70 tests (46 scorer, 24 API integration)

---

## Running the Project

```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env   # edit with credentials or leave blank for mock data
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev            # http://localhost:5173

# Tests
cd backend
python -m pytest tests/ -v
```

Without Google Ads API credentials the app runs in **mock data mode** — all API
calls return realistic sample data.

---

## Key Architecture Decisions

### SQLite default with PostgreSQL upgrade path
SQLAlchemy ORM with async sessions works identically on both. Switch by changing
`DATABASE_URL` from `sqlite+aiosqlite:///...` to `postgresql+asyncpg://...`.
No model changes needed.

### Mock data fallback in GoogleAdsService
`backend/app/services/google_ads.py` — if no developer token is configured OR
the google-ads client fails to initialize, every method falls back to realistic
mock data. This lets the full UI work without API credentials during development.

### Scoring engine: negative terms take absolute priority
`backend/app/services/scorer.py` — a keyword matching ANY negative term
(pool table, carpool, diy, etc.) is classified as SKIP regardless of its volume,
competition, or CPC scores. This was a bug fix: without this rule, "pool table
felt replacement" scored 75 (HIGH) because 25+25+25+0=75 hit the threshold.

### Background research with global state tracking
`backend/app/services/research.py` — research runs execute as FastAPI
BackgroundTasks. A module-level `_active_run` dict tracks progress. Only one
run at a time is allowed (enforced by the endpoint returning 409 if active).

### Frontend proxies API calls through Vite
`frontend/vite.config.js` — `/api` requests proxy to `localhost:8000` in dev.
In production, Render routes `/api/*` to the backend service automatically via
the static site rewrite rules.

---

## Problems Solved During Development

### 1. Dependency conflict: pytest-httpx vs httpx
**Problem**: `pytest-httpx==0.34.0` required a specific httpx version incompatible
with `httpx==0.28.1`.
**Solution**: Removed pytest-httpx entirely. Tests use httpx's built-in
`ASGITransport` to call the FastAPI app directly — no HTTP mocking needed.

### 2. Google Ads client import crash in test environment
**Problem**: `from google.ads.googleads.client import GoogleAdsClient` triggered
a `pyo3_runtime.PanicException` because the `cryptography` library's Rust
bindings weren't available in the test container.
**Solution**: Added early-exit guard in `_get_client()`: if no developer token
is configured, return `None` immediately (triggers mock data) without attempting
the import.

### 3. Frontend-backend parameter mismatch on research endpoint
**Problem**: Frontend sent `account_id` in JSON body, but backend declared it as
a query parameter.
**Solution**: Added `RunRequest` Pydantic model to accept body JSON. Same fix
applied to export endpoints using `Query()` for query-string parameters.

### 4. Negative keywords scoring as HIGH priority
**Problem**: "pool table felt replacement" scored volume=25 + competition=25 +
cpc=25 + relevance=0 = 75 → classified as HIGH.
**Solution**: Added explicit rule: if `relevance_category == "negative_candidate"`,
force priority to SKIP regardless of total score.

### 5. Google Cloud parent resource blocking project creation
**Problem**: Google Workspace accounts require a parent organization or folder
when creating Cloud projects. If no org is visible in the Browse dialog, the
user can't create the project.
**Solution**: Documented two workarounds: (a) grant yourself Project Creator role
at the org level via IAM, (b) use a personal Gmail to create the Cloud project.

---

## Database Schema (6 tables)

Defined in `backend/app/models/models.py`:

- **accounts** — MCC child account metadata (CID, name, avg CPC, geo targets)
- **research_runs** — Run history with status, settings, summary stats
- **seed_keywords** — Seeds used per run with performance metrics
- **keyword_ideas** — Generated ideas with scores, priority, match type suggestion
- **decisions** — Team approve/reject/watchlist/implemented actions
- **negative_flags** — Ideas flagged as negative keyword candidates

Tables are auto-created on first backend startup via `Base.metadata.create_all()`.

---

## API Routes (28 endpoints)

| Group | Prefix | Key endpoints |
|-------|--------|---------------|
| Auth | `/api/auth` | login, callback, me, logout |
| Accounts | `/api/accounts` | list, sync from MCC, get detail |
| Research | `/api/research` | run, status, list runs, get run |
| Results | `/api/results` | get ideas (paginated), seeds, negatives, compare runs |
| Decisions | `/api/decisions` | bulk create, update, list by account |
| Export | `/api/export` | Google Ads Editor CSV, Excel workbook, negatives CSV |
| Settings | `/api/settings` | get/update research config |
| Health | `/api/health` | status check |

---

## Scoring Engine Details

File: `backend/app/services/scorer.py`

Four dimensions, 25 points each, total 0-100:

| Dimension | What it measures | Scoring bands |
|-----------|-----------------|---------------|
| Volume | avg_monthly_searches | 500+=25, 200+=20, 100+=15, 50+=10, 10+=5 |
| Competition | competition_index 0-100 | 0-33=25, 34-66=15, 67-100=10 |
| CPC Efficiency | idea CPC / account avg CPC | <50%=25, <80%=20, 80-120%=15, >120%=10, >200%=5 |
| Relevance | pool/spa keyword matching | HIGH_RELEVANCE=25, MEDIUM=15, none=8, NEGATIVE=0+SKIP |

Priority: HIGH (75+), MEDIUM (50-74), LOW (25-49), SKIP (0-24 or negative match)

---

## Test Coverage

```
tests/test_scorer.py   — 46 tests
  Volume scoring (7), Competition (4), CPC efficiency (6), Relevance (11),
  Priority classification (4), Seasonality detection (4), Match type (2),
  Ad group matching (4), Full scoring integration (4)

tests/test_api.py      — 24 tests
  Health (1), Accounts CRUD (5), Results & filtering (6), Decisions (4),
  Export CSV/Excel/negatives (3), Settings get/update (2), Research status/runs (3)
```

All 70 tests pass. Run with: `cd backend && python -m pytest tests/ -v`

---

## Deployment Checklist

1. Create Supabase project, get connection URI (port 6543 for pooling)
2. Create Google Cloud project with OAuth2 credentials (see GOOGLE_API_SETUP.md)
3. Apply for Google Ads API developer token under MCC account
4. Edit `render.yaml` — remove `databases` block, set DATABASE_URL to `sync: false`
5. Push to GitHub, deploy via Render Blueprint
6. Set all env vars in Render dashboard
7. Add Render backend URL to Google OAuth redirect URIs
8. Verify: `/api/health`, Sync from MCC, run research on one account

---

## File Map

```
backend/
  app/
    main.py                    — FastAPI app, lifespan, CORS, router registration
    config.py                  — Pydantic Settings from env vars
    database.py                — Async SQLAlchemy engine, session factory, init_db()
    models/models.py           — 6 ORM models matching spec schema
    models/schemas.py          — Pydantic request/response schemas
    routers/auth.py            — Google OAuth2 flow, session store
    routers/accounts.py        — Account CRUD with latest-run stats
    routers/research.py        — Research run trigger (background task)
    routers/results.py         — Paginated keyword ideas with filtering
    routers/decisions.py       — Bulk approve/reject/watchlist
    routers/export.py          — CSV, Excel, negatives export
    routers/settings_router.py — Config get/update
    services/scorer.py         — Scoring engine (volume, competition, CPC, relevance)
    services/google_ads.py     — Google Ads API client with mock fallback
    services/research.py       — Research orchestration pipeline
    services/export.py         — File generation (CSV, Excel workbook)
  tests/
    test_scorer.py             — 46 scoring engine tests
    test_api.py                — 24 API integration tests

frontend/
  src/
    main.jsx                   — React app with routes
    lib/api.js                 — Backend API client
    components/Layout.jsx      — App shell, nav, auth state
    pages/Dashboard.jsx        — Account table, stats, run-all
    pages/AccountDetail.jsx    — 5-tab keyword review (opportunities, seeds, negatives, history, export)
    pages/Settings.jsx         — Config editor
    pages/ResearchProgress.jsx — Live progress polling

render.yaml                    — Render Blueprint (backend + frontend + optional DB)
SETUP_AND_DEPLOY.md            — Full deployment guide
```

---

## Next Steps for Development

### Immediate: CSV/XLSX Import for Offline Accounts
Not all accounts are accessible via API. The team receives weekly exports with
campaign, ad group, keyword, and search term data. Build an import pipeline that:
- Accepts CSV/XLSX uploads with standardized column format
- Runs the scoring engine against imported data
- Recommends Exact vs Phrase match types based on search term analysis
- See `IMPORT_FEATURE_DESIGN.md` for full specification

### Blocker to resolve: Google Cloud OAuth2 setup
The project never reached production because of the Google Cloud parent resource
issue. See GOOGLE_API_SETUP.md for the complete step-by-step walkthrough.

### Future enhancements
- Competitor keyword discovery via Auction Insights
- AI-powered ad copy suggestions for approved keywords
- Automated keyword implementation via Google Ads API mutate
- Scheduled weekly research runs
- Slack notifications on run completion
