# MCC Keyword Research Platform — Design Specification

## What We're Solving

SSP Digital manages ~40 pool/spa Google Ads accounts. Each account needs ongoing keyword expansion to capture search demand that existing keywords miss. Today, keyword research happens manually — someone opens Keyword Planner in each account, types seed keywords, reviews results, copies them into a spreadsheet. At 40 accounts, this takes a full day and rarely gets done.

The search term report (handled by a separate MCC script) shows what's already converting. This tool fills the other half: **what are people searching that our accounts aren't showing up for?** It uses the Google Ads API Keyword Planner programmatically, scores results for pool/spa relevance, and presents them in a web interface where the team can review, approve, and export keyword opportunities without touching a command line.

The team includes: Matthew (PPC lead, technical), Pam (CEO/Account Manager, non-technical), Lisa and Lauren (account managers, moderate technical ability), and contractors (variable skill level). The interface must be usable by all of them.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Browser (React + Tailwind)                         │
│  ├── Dashboard: account overview + stats             │
│  ├── Account Detail: keyword ideas + approval flow   │
│  ├── Compare: this run vs. last run (what's new)     │
│  ├── Export: Google Ads Editor CSV + Sheets output    │
│  └── Settings: config, thresholds, team access       │
└──────────────────┬──────────────────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────────────────┐
│  Backend (Node.js + Express or Python FastAPI)       │
│  ├── /api/auth        — OAuth2 flow for Google Ads   │
│  ├── /api/accounts    — List MCC child accounts      │
│  ├── /api/research    — Trigger keyword research run  │
│  ├── /api/results     — Fetch/filter/sort results     │
│  ├── /api/decisions   — Save approve/reject/watchlist │
│  ├── /api/export      — Generate CSV/Sheets output    │
│  └── /api/history     — Compare runs over time        │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│  Database (PostgreSQL via Supabase or SQLite)        │
│  ├── accounts         — MCC child account metadata   │
│  ├── research_runs    — Run history with settings     │
│  ├── keyword_ideas    — All generated ideas + scores  │
│  ├── decisions        — Approved/rejected/watchlist   │
│  ├── seed_keywords    — Seeds used per run            │
│  └── negative_flags   — Ideas flagged as negatives    │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│  Google Ads API                                      │
│  ├── KeywordPlanIdeaService — keyword suggestions    │
│  ├── GoogleAdsService       — seed keywords + metrics │
│  └── CustomerService        — MCC account listing     │
└─────────────────────────────────────────────────────┘
```

### Tech Stack

**Frontend:** React + Tailwind CSS + Vite. Simple SPA, no SSR needed. shadcn/ui for components.

**Backend:** Python (FastAPI) preferred — the `google-ads` Python client library is the most mature and best documented. Node.js with the google-ads-api npm package is an alternative if the team prefers JavaScript throughout.

**Database:** Supabase (PostgreSQL) for cloud deployment. SQLite as a simpler alternative for single-server deployment. The key requirement is persisting results across runs so the team can compare month-over-month and track what was implemented.

**Deployment:** Render, Railway, or Vercel (frontend) + Fly.io/Render (backend). Or a single VPS running both. The app is internal-use only (SSP team + contractors), so it doesn't need to scale beyond a handful of concurrent users.

**Auth:** Google OAuth2 handles both Google Ads API access and user login. The team signs in with their Google accounts. The MCC-level developer token is stored server-side and never exposed to the frontend.

---

## Prerequisites (One-Time Setup)

Before the app can be built and deployed, SSP needs:

### 1. Google Ads API Developer Token
- Apply at: https://developers.google.com/google-ads/api/docs/get-started/dev-token
- Applied for under the MCC manager account
- **Test access** is instant and sufficient for development (limited to test accounts)
- **Basic access** (needed for production) requires a brief application and takes 1-5 business days
- The token is a single string stored in the backend environment variables

### 2. Google Cloud Project with OAuth2 Credentials
- Go to: https://console.cloud.google.com
- Create a new project (e.g., "SSP Keyword Research")
- Enable the **Google Ads API**
- Go to APIs & Services > Credentials > Create Credentials > OAuth 2.0 Client ID
- Application type: **Web application**
- Authorized redirect URI: `https://your-app-domain.com/api/auth/callback` (and `http://localhost:3000/api/auth/callback` for dev)
- Download the client ID and client secret
- These go into backend environment variables

### 3. MCC Account ID
- The top-level manager account ID in XXX-XXX-XXXX format
- Found in Google Ads UI top-right corner when logged into the MCC
- Stored as `LOGIN_CUSTOMER_ID` in environment variables (no dashes: `1234567890`)

### 4. Google Ads API Scopes
- The OAuth2 consent screen needs the scope: `https://www.googleapis.com/auth/adwords`
- For Google Sheets export, also add: `https://www.googleapis.com/auth/spreadsheets`

---

## Database Schema

```sql
-- MCC child accounts
CREATE TABLE accounts (
  id SERIAL PRIMARY KEY,
  google_ads_id VARCHAR(20) NOT NULL UNIQUE,  -- e.g., '123-456-7890'
  name VARCHAR(255) NOT NULL,
  is_active BOOLEAN DEFAULT true,
  avg_cpc NUMERIC(10,2),           -- Current avg CPC for scoring
  avg_cpa NUMERIC(10,2),           -- Current avg CPA for context
  monthly_budget NUMERIC(10,2),
  geo_target_ids TEXT[],            -- Array of geo target constant IDs
  last_synced_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Each time keyword research is run
CREATE TABLE research_runs (
  id SERIAL PRIMARY KEY,
  account_id INTEGER REFERENCES accounts(id),
  started_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP,
  status VARCHAR(20) DEFAULT 'running',  -- running, completed, failed, rate_limited
  settings JSONB,                        -- lookback_days, thresholds, etc.
  seed_count INTEGER,
  ideas_generated INTEGER,
  ideas_high INTEGER,
  ideas_medium INTEGER,
  ideas_low INTEGER,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Seed keywords used for each run
CREATE TABLE seed_keywords (
  id SERIAL PRIMARY KEY,
  run_id INTEGER REFERENCES research_runs(id) ON DELETE CASCADE,
  keyword TEXT NOT NULL,
  match_type VARCHAR(20),
  conversions NUMERIC(10,2),
  clicks INTEGER,
  cost NUMERIC(10,2),
  quality_score INTEGER,
  campaign VARCHAR(255),
  ad_group VARCHAR(255)
);

-- Generated keyword ideas
CREATE TABLE keyword_ideas (
  id SERIAL PRIMARY KEY,
  run_id INTEGER REFERENCES research_runs(id) ON DELETE CASCADE,
  account_id INTEGER REFERENCES accounts(id),
  keyword_text TEXT NOT NULL,
  avg_monthly_searches INTEGER,
  competition VARCHAR(10),           -- LOW, MEDIUM, HIGH
  competition_index INTEGER,         -- 0-100
  low_cpc_micros BIGINT,
  high_cpc_micros BIGINT,
  monthly_volumes JSONB,             -- 12-month array [{month, year, searches}]
  -- Scoring
  volume_score INTEGER,
  competition_score INTEGER,
  cpc_score INTEGER,
  relevance_score INTEGER,
  total_score INTEGER,
  priority VARCHAR(10),              -- HIGH, MEDIUM, LOW, SKIP
  relevance_category VARCHAR(20),    -- high_relevance, medium_relevance, negative_candidate
  -- Context
  suggested_match_type VARCHAR(10),  -- EXACT, PHRASE
  suggested_ad_group VARCHAR(255),
  already_exists BOOLEAN DEFAULT false,
  already_negative BOOLEAN DEFAULT false,
  -- Seasonal flag
  is_seasonal BOOLEAN DEFAULT false,
  peak_month VARCHAR(20),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Team decisions on keyword ideas
CREATE TABLE decisions (
  id SERIAL PRIMARY KEY,
  keyword_idea_id INTEGER REFERENCES keyword_ideas(id),
  account_id INTEGER REFERENCES accounts(id),
  decision VARCHAR(20) NOT NULL,     -- approved, rejected, watchlist, implemented
  decided_by VARCHAR(100),           -- team member name/email
  notes TEXT,
  implemented_at TIMESTAMP,          -- when actually added to Google Ads
  decided_at TIMESTAMP DEFAULT NOW()
);

-- Negative keyword candidates from irrelevant ideas
CREATE TABLE negative_flags (
  id SERIAL PRIMARY KEY,
  keyword_idea_id INTEGER REFERENCES keyword_ideas(id),
  account_id INTEGER REFERENCES accounts(id),
  keyword_text TEXT NOT NULL,
  reason TEXT,                       -- "Matches pattern: pool table"
  suggested_scope VARCHAR(20),       -- CAMPAIGN, ACCOUNT
  decided VARCHAR(20),               -- pending, approved, rejected
  decided_by VARCHAR(100),
  decided_at TIMESTAMP
);

-- Index for fast lookups
CREATE INDEX idx_keyword_ideas_account ON keyword_ideas(account_id);
CREATE INDEX idx_keyword_ideas_priority ON keyword_ideas(priority);
CREATE INDEX idx_keyword_ideas_score ON keyword_ideas(total_score DESC);
CREATE INDEX idx_decisions_account ON decisions(account_id);
CREATE INDEX idx_research_runs_account ON research_runs(account_id);
```

---

## API Endpoints

### Auth
```
GET  /api/auth/login          — Redirect to Google OAuth2 consent
GET  /api/auth/callback       — Handle OAuth2 callback, store tokens
GET  /api/auth/me             — Return current user info
POST /api/auth/logout         — Clear session
```

### Accounts
```
GET  /api/accounts            — List all MCC child accounts with latest run stats
POST /api/accounts/sync       — Refresh account list from MCC + update geo/budget data
GET  /api/accounts/:id        — Single account detail with run history
```

### Research
```
POST /api/research/run        — Start keyword research for one or all accounts
     Body: { account_id: 123 } or { account_id: "all" }
     Returns: { run_id, status: "running" }

GET  /api/research/status/:run_id  — Poll run progress
     Returns: { status, accounts_completed, accounts_total, current_account }

GET  /api/research/runs       — List past runs with summary stats
GET  /api/research/runs/:id   — Single run detail
```

### Results
```
GET  /api/results/:account_id
     Query params: ?priority=HIGH&sort=score&page=1&per_page=50
                   ?run_id=latest (default) or specific run ID
                   ?search=pool+builder (text search within ideas)
                   ?show_existing=false (hide already-active keywords)
                   ?show_decided=false (hide already-approved/rejected)
     Returns: paginated keyword ideas with scores, decisions, context

GET  /api/results/:account_id/seeds
     Returns: seed keywords used for latest run

GET  /api/results/:account_id/negatives
     Returns: ideas flagged as negative keyword candidates

GET  /api/results/:account_id/compare
     Query: ?run_a=15&run_b=18
     Returns: { new_ideas: [...], removed_ideas: [...], score_changes: [...] }
```

### Decisions
```
POST /api/decisions
     Body: { keyword_idea_ids: [1,2,3], decision: "approved", notes: "..." }
     Bulk approve/reject/watchlist

PATCH /api/decisions/:id
      Body: { decision: "implemented", implemented_at: "2026-03-15" }

GET  /api/decisions/:account_id
     Returns: all decisions for an account grouped by status
```

### Export
```
POST /api/export/google-ads-editor
     Body: { account_id: 123, priority: "HIGH", format: "csv" }
     Returns: CSV formatted for Google Ads Editor import
     Columns: Campaign, Ad Group, Keyword, Match Type, Max CPC

POST /api/export/sheets
     Body: { account_id: 123, spreadsheet_url: "..." }
     Writes results to a Google Sheet tab (same format as existing Ad Build Export)

POST /api/export/all-accounts
     Body: { format: "xlsx", priority: ["HIGH", "MEDIUM"] }
     Returns: Multi-tab Excel workbook, one tab per account
```

---

## Frontend Pages

### 1. Dashboard (`/`)

**Purpose:** Portfolio-wide view of keyword research status and opportunities.

**Layout:**
- Top stats bar: Total accounts, accounts researched, total keyword opportunities, total HIGH priority, estimated monthly search volume captured vs. available
- Account table (sortable, filterable):
  | Account | Last Run | Ideas | HIGH | MED | Approved | Pending | Monthly Vol Opportunity | Action |
  - "Action" column: "Run Research" button or "View Results" link
  - Color-coded: red row if never researched, yellow if run > 30 days old, green if current
- "Run All Accounts" button (top right) — starts background research for all accounts
- Progress bar when a run is active, showing current account and ETA

### 2. Account Detail (`/accounts/:id`)

**Purpose:** Review and act on keyword ideas for one account.

**Layout:**

**Header:** Account name, CID, last run date, current avg CPC/CPA, monthly budget, geo targeting summary.

**Tab bar:** Opportunities | Seeds | Negatives | History | Export

**Opportunities tab (default):**
- Filter bar: Priority (HIGH/MED/LOW), Status (Pending/Approved/Rejected/Watchlist), Search text, Volume range, CPC range
- Sort options: Score (default), Volume, CPC, Competition
- Results as a data table:

  | ☐ | Score | Keyword | Monthly Vol | Competition | Est. CPC | Relevance | Trend | Suggested Group | Status | Actions |

  - Score: color-coded badge (green HIGH, yellow MED, gray LOW)
  - Trend: sparkline or mini bar chart showing 12-month seasonal pattern
  - Status: Pending / Approved ✓ / Rejected ✗ / Watchlist 👀 / Implemented ✓✓
  - Actions: Approve / Reject / Watchlist buttons. Approve opens a drawer with:
    - Confirm keyword text
    - Select match type (pre-filled with suggestion)
    - Select target ad group (dropdown of existing ad groups, pre-filled with suggestion)
    - Optional: set initial max CPC bid
    - Optional: notes field
  - Bulk actions: Select multiple → Approve All / Reject All / Export Selected

- Right sidebar (shows when a keyword is selected):
  - Full detail: all scores broken down, 12-month volume chart, similar existing keywords in the account, related search terms from the search term report if available

**Seeds tab:**
- Table of seed keywords used in the latest run with their performance metrics
- Shows why each seed was selected (conversions, clicks, QS)

**Negatives tab:**
- Ideas flagged as irrelevant by the scoring engine
- Each shows the matched negative pattern and suggested scope (campaign/account)
- Approve/reject for adding as actual negative keywords
- Export as negative keyword list

**History tab:**
- List of past runs with summary stats
- "Compare" button between any two runs → shows new ideas, removed ideas, score changes
- Tracks how the keyword landscape is evolving month over month

**Export tab:**
- Export approved keywords as:
  - Google Ads Editor CSV (ready for import — includes Campaign, Ad Group, Keyword, Match Type, Max CPC columns)
  - Google Sheets (writes to a specified sheet, matching the Ad Build Export format)
  - Excel workbook
- Export negative candidates separately
- Export the full idea list with scores for offline review

### 3. Settings (`/settings`)

**Purpose:** Configure thresholds, API credentials, team access.

**Sections:**

**Research Settings:**
- Lookback days (default 90)
- Min seed conversions (default 2)
- Min seed clicks (default 10)
- Max seeds per account (default 15)
- Min monthly searches filter (default 50)
- Keyword opportunity score thresholds (HIGH ≥ 75, MED ≥ 50, LOW ≥ 25)

**Scoring Weights:**
- Volume weight (default 25)
- Competition weight (default 25)
- CPC efficiency weight (default 25)
- Relevance weight (default 25)
- Allow customization of the relevance keyword lists (add/remove terms from HIGH_RELEVANCE, MEDIUM_RELEVANCE, LOW_RELEVANCE_NEGATIVE)

**API Configuration:**
- Developer token (masked)
- OAuth2 status (connected/disconnected with re-auth button)
- MCC Account ID
- API quota usage display (calls made today / daily limit)

**Team Access:**
- List of authorized Google accounts (email addresses)
- Role: Admin (can change settings + run research) / Reviewer (can view + approve/reject)

### 4. Run Progress (`/research/active`)

**Purpose:** Live progress view when research is running.

**Layout:**
- Overall progress bar: "12 / 40 accounts complete"
- Current account being processed with live status: "Pulling seeds... → Calling Keyword Planner... → Scoring... → Done"
- Estimated time remaining
- Running log of results: "Magnolia Custom Pools: 47 ideas (12 HIGH, 18 MED)"
- Cancel button
- Auto-redirects to Dashboard when complete

---

## Google Ads API Integration

### Seed Extraction (per account)

```python
# GAQL query for seed keywords
query = """
  SELECT
    campaign.name,
    ad_group.name,
    ad_group_criterion.keyword.text,
    ad_group_criterion.keyword.match_type,
    ad_group_criterion.quality_info.quality_score,
    metrics.conversions,
    metrics.clicks,
    metrics.impressions,
    metrics.cost_micros,
    metrics.conversions_from_interactions_rate
  FROM keyword_view
  WHERE ad_group_criterion.status = 'ENABLED'
    AND campaign.status = 'ENABLED'
    AND metrics.impressions > 0
    AND segments.date DURING LAST_90_DAYS
  ORDER BY metrics.conversions DESC, metrics.clicks DESC
  LIMIT 200
"""
```

Seed selection logic:
1. Keywords with `conversions >= min_seed_conversions` → top tier
2. Keywords with `clicks >= min_seed_clicks` and `quality_score >= 6` → secondary
3. Deduplicate by keyword text (keep highest-converting version)
4. Cap at `max_seeds_per_account`

### Geo Targeting Pull (per account)

```python
query = """
  SELECT
    campaign.name,
    campaign_criterion.location.geo_target_constant
  FROM campaign_criterion
  WHERE campaign_criterion.type = 'LOCATION'
    AND campaign.status = 'ENABLED'
"""
```

Map `geo_target_constant` resource names to location IDs for the Keyword Planner request. If no geo targeting found, fall back to US (geo target constant 2840).

### Existing Keywords Pull (per account, for deduplication)

```python
query = """
  SELECT
    ad_group_criterion.keyword.text,
    ad_group_criterion.keyword.match_type
  FROM keyword_view
  WHERE ad_group_criterion.status = 'ENABLED'
    AND campaign.status = 'ENABLED'
"""
```

Build a set of existing keyword texts to filter out from Keyword Planner results.

### Existing Negatives Pull (per account)

```python
query = """
  SELECT
    campaign_criterion.keyword.text
  FROM campaign_criterion
  WHERE campaign_criterion.type = 'KEYWORD'
    AND campaign_criterion.negative = TRUE
    AND campaign.status != 'REMOVED'
"""
```

Used to flag ideas that are already blocked.

### Keyword Planner Call

```python
request = client.get_type("GenerateKeywordIdeasRequest")
request.customer_id = account_id
request.language = client.get_service("GoogleAdsService").language_constant_path("1000")  # English
request.geo_target_constants = [
    client.get_service("GoogleAdsService").geo_target_constant_path(loc)
    for loc in location_ids
]
request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
request.keyword_seed.keywords.extend(seed_keywords)  # batch of 10-15 seeds
```

Response fields per idea:
- `text` — keyword suggestion
- `keyword_idea_metrics.avg_monthly_searches`
- `keyword_idea_metrics.competition` — LOW / MEDIUM / HIGH
- `keyword_idea_metrics.competition_index` — 0-100
- `keyword_idea_metrics.low_top_of_page_bid_micros`
- `keyword_idea_metrics.high_top_of_page_bid_micros`
- `keyword_idea_metrics.monthly_search_volumes` — 12-month history array

### Rate Limiting Strategy

- Google Ads API Basic access: 15,000 operations/day
- Each `GenerateKeywordIdeas` call = 1 operation
- Budget: batch seeds into groups of 10-15, so ~2-3 calls per account × 40 accounts = ~80-120 calls
- Add 1-second delay between Keyword Planner calls
- Add 2-second delay between accounts
- Total estimated runtime: 5-10 minutes for all 40 accounts
- If rate limited (HTTP 429): save progress to database, show "Rate limited — resume tomorrow" in UI
- Display remaining daily quota on the Settings page

---

## Scoring Engine

Each keyword idea receives a composite score (0-100) from four equally weighted dimensions.

### Volume Score (0-25)

| Monthly Searches | Score |
|---|---|
| 500+ | 25 |
| 200-499 | 20 |
| 100-199 | 15 |
| 50-99 | 10 |
| 10-49 | 5 |
| <10 | 0 |

### Competition Score (0-25)

| Competition | Score |
|---|---|
| LOW (index 0-33) | 25 |
| MEDIUM (index 34-66) | 15 |
| HIGH (index 67-100) | 10 |

Lower competition = higher score. High competition still scores 10 (not 0) because high competition validates demand.

### CPC Efficiency Score (0-25)

Compare the idea's estimated average CPC (midpoint of low and high estimates) against the account's current average CPC:

| CPC vs. Account Avg | Score |
|---|---|
| Idea CPC < 50% of account avg | 25 |
| Idea CPC < 80% of account avg | 20 |
| Idea CPC ≈ account avg (80-120%) | 15 |
| Idea CPC > 120% of account avg | 10 |
| Idea CPC > 200% of account avg | 5 |

### Relevance Score (0-25)

Pattern matching against pool/spa industry keyword lists:

```python
HIGH_RELEVANCE_TERMS = [
    # Pool construction & services
    "pool builder", "pool construction", "pool contractor", "pool company",
    "pool installation", "pool remodel", "pool renovation", "pool repair",
    "pool resurfacing", "pool plastering", "pool replastering", "pool service",
    "pool cleaning", "pool maintenance", "pool opening", "pool closing",
    # Pool types
    "inground pool", "gunite pool", "fiberglass pool", "vinyl pool",
    "custom pool", "concrete pool", "saltwater pool", "infinity pool",
    "plunge pool", "cocktail pool", "lap pool", "sport pool",
    # Pool features & materials
    "pool deck", "pool coping", "pool tile", "pool plaster",
    "pool enclosure", "pool cover", "pool heater", "pool pump",
    "pool filter", "pool light", "pool automation", "pool fence",
    "pebble tec", "pebble sheen", "diamond brite", "quartz finish",
    # Hot tubs & spas
    "hot tub", "spa", "swim spa", "jacuzzi", "hot tub dealer",
    "hot tub sale", "hot tub near me", "hot tub store", "hot tub service",
    "hot tub repair", "hot tub delivery", "hot tub installation",
    # Commercial intent
    "pool cost", "pool price", "pool quote", "pool estimate",
    "pool financing", "pool near me", "pool builders near me",
    "how much does a pool cost", "pool builder cost",
    # Outdoor living (closely related)
    "outdoor living", "backyard pool", "swimming pool", "pool design",
    "pool patio", "pool landscape"
]

MEDIUM_RELEVANCE_TERMS = [
    "backyard", "outdoor", "landscape", "hardscape", "paver",
    "concrete", "deck", "pergola", "gazebo", "fence",
    "water feature", "fountain", "fire pit", "outdoor kitchen",
    "screen enclosure", "lanai", "retaining wall", "travertine",
    "flagstone", "stamped concrete", "kool deck"
]

NEGATIVE_TERMS = [
    "pool table", "billiard", "car pool", "carpool", "gene pool",
    "pool party", "pool game", "pool noodle", "pool float", "pool toy",
    "inflatable", "intex", "bestway", "above ground",
    "walmart", "amazon", "home depot", "lowes", "craigslist",
    "diy", "how to", "youtube", "tutorial", "video",
    "jobs", "hiring", "career", "salary", "employment",
    "used", "free", "cheap", "wholesale", "coupon"
]
```

| Match | Score | Action |
|---|---|---|
| Contains HIGH_RELEVANCE term | 25 | Strong candidate |
| Contains MEDIUM_RELEVANCE term | 15 | Review carefully |
| No relevance signals | 8 | Likely tangential |
| Contains NEGATIVE term | 0 | Flag as negative keyword candidate |

### Priority Classification

| Total Score | Priority | UI Color | Meaning |
|---|---|---|---|
| 75-100 | HIGH | Green | Add immediately — high confidence |
| 50-74 | MEDIUM | Yellow | Review and likely add |
| 25-49 | LOW | Gray | Add if budget allows, lower priority |
| 0-24 | SKIP | Red | Irrelevant or too expensive — ignore or add as negative |

### Seasonality Detection

After scoring, check the 12-month volume array for seasonal patterns:
- Calculate the coefficient of variation (std dev / mean) of monthly volumes
- If CV > 0.5, flag `is_seasonal = true`
- Identify `peak_month` as the month with highest volume
- Display in UI: "Seasonal — peaks in March" or "Steady year-round"
- Pool construction keywords peak March-June. Hot tub keywords peak October-December. This data helps the team plan budget allocation.

### Ad Group Matching

For each keyword idea, suggest which existing ad group it should be added to:
1. Tokenize the idea and each ad group's keyword set
2. Calculate word overlap between the idea and each ad group's keywords
3. The ad group with the highest overlap is the suggested match
4. If no ad group has >30% word overlap, suggest "NEW AD GROUP: [primary theme]"
5. Store as `suggested_ad_group` on the keyword idea

---

## Export Formats

### Google Ads Editor CSV

For approved keywords, generate a CSV that imports directly into Google Ads Editor:

```csv
Campaign,Ad Group,Keyword,Criterion Type,Max CPC
Pool Builder - Search,Custom Pool Builder,[custom gunite pool builder],Exact,
Pool Builder - Search,Custom Pool Builder,"pool construction near me",Phrase,
```

- `Criterion Type`: "Exact" or "Phrase" based on `suggested_match_type`
- `Max CPC`: left blank (let Smart Bidding handle it) or filled if user sets a bid in the approval flow
- Contractor downloads this, opens Google Ads Editor, clicks "Make Multiple Changes" > "Use My Data", pastes, uploads

### Google Sheets Export

Write approved keywords to a Google Sheet tab matching the format of the existing MCC Ad Build Export:
- Tab name: "[Account Name] — KW Ideas"
- Same structure: seeds used, HIGH priority ideas, MEDIUM priority ideas, negatives
- This can be written to the same spreadsheet as the Ad Build Export so the contractor has keywords + ad builds in one workbook

### Excel Export

Multi-tab .xlsx workbook:
- Tab 1: Summary (all accounts, idea counts, top opportunities)
- Tab 2-N: One tab per account with full idea list, scores, decisions

### Negative Keyword Export

Separate CSV/list of ideas flagged as negative candidates:
```
"pool table"
"billiard room"
[carpool]
"diy pool repair"
```
Pre-formatted for paste into Google Ads > Keywords > Negative Keywords.

---

## Run Comparison (Month-over-Month)

When the team runs keyword research monthly, the History tab shows what changed:

**New Ideas:** Keywords that appeared in the latest run but not the previous run. These represent emerging search demand — new trends, seasonal shifts, or Google expanding its suggestion set. Sorted by score.

**Disappeared Ideas:** Keywords in the previous run but not the latest. These may indicate declining search interest or Google narrowing suggestions. Informational only.

**Score Changes:** Keywords present in both runs but with significantly different scores (volume changed, competition shifted, CPC moved). Sorted by score delta.

**Implementation Tracking:** Keywords marked as "Approved" in a previous run — did the team add them? The "Implemented" status tracks this. The comparison view shows: "23 keywords approved in February run → 18 implemented, 5 still pending."

---

## Error Handling

| Error | User Experience |
|---|---|
| OAuth2 expired | "Your Google session has expired. Click to re-authenticate." Button redirects to /api/auth/login |
| Rate limit (429) | Progress page shows "Daily API limit reached. Research will resume automatically tomorrow at 12:00 AM Pacific." Saves progress to database. Next run picks up where it left off. |
| Account access denied | Skip account, show warning on dashboard: "Cannot access [Account Name] — check MCC permissions" |
| No seeds found | Dashboard shows: "[Account Name]: No qualifying keywords found. Check if campaigns are active and have recent spend." |
| Keyword Planner returns empty | Show: "[Account Name]: Keyword Planner returned no suggestions. This usually means the account has very low spend or very niche keywords. Try increasing lookback_days or lowering min_seed_conversions." |
| Network timeout | Retry 3 times with exponential backoff. If still failing: "Unable to reach Google Ads API. Check your internet connection." |
| Invalid developer token | "Your Google Ads API developer token is invalid or expired. Contact Matthew to update it in Settings." |

---

## Key Constraints & Notes

1. **Google Ads API version:** Use the latest stable version (v18+ as of early 2026). The `google-ads` Python library manages version compatibility.

2. **Keyword Planner requires active spend:** Google returns limited or no data for accounts with $0 recent spend. The tool detects this and shows a clear warning rather than empty results.

3. **Volume data is ranges, not exact:** Unless the account is actively spending (which all SSP accounts are), Keyword Planner returns volume as ranges (100-1K). The tool uses the midpoint for scoring and displays the range in the UI. A tooltip explains this limitation.

4. **Location targeting matters:** Each account's actual geo targeting is pulled and used for the Keyword Planner request. "Pool builder" in Houston returns different volume and CPC than nationally. This gives locally accurate data.

5. **The tool is read-only with respect to Google Ads.** It queries data and generates reports. It never modifies account settings, keywords, or ads. All changes are made by the team through Google Ads Editor or the Google Ads UI using the exported data.

6. **Concurrency:** Only one research run at a time (enforced by the backend). The progress page shows the active run. If someone tries to start a second run, the UI shows "Research is already running for [Account Name]. Please wait."

7. **Data retention:** Keep all runs and ideas indefinitely. Storage is cheap. The comparison feature requires historical data. Add a "Purge runs older than X months" option in Settings for cleanup if needed.

8. **This tool complements existing scripts.** The search term report (handled by the MCC Negative Keyword Audit and Ad Build Export scripts) shows what's already converting. This tool discovers untapped demand. The two outputs together give a complete keyword expansion strategy: proven converters + new opportunities.

---

## Development Phases

### Phase 1: Core (MVP)
- OAuth2 auth flow
- Account listing from MCC
- Seed extraction from Google Ads API
- Keyword Planner integration
- Scoring engine
- Results page with filtering and sorting
- Excel export
- Estimated effort: 3-5 days

### Phase 2: Decision Workflow
- Approve/reject/watchlist UI
- Bulk actions
- Google Ads Editor CSV export
- Google Sheets export
- Estimated effort: 2-3 days

### Phase 3: Comparison & Tracking
- Run history storage and comparison
- "What's new" view
- Implementation tracking (approved → implemented)
- Seasonality charts
- Estimated effort: 2-3 days

### Phase 4: Polish
- Dashboard with portfolio-wide stats
- Settings page with editable thresholds and relevance lists
- Team access / role management
- API quota monitoring display
- Estimated effort: 1-2 days

### Total estimated build time: 8-13 days

---

## Testing Strategy

### Unit Tests
- **Scorer:** Feed known pool/spa keywords, verify HIGH scores. Feed "pool table", "carpool", verify SKIP/negative. Feed edge cases like "pool table repair near me" (contains both "pool" and "pool table") — negative should win.
- **Seed selector:** Mock GAQL responses, verify correct seed selection, deduplication, and capping.
- **Ad group matcher:** Given a keyword idea and a set of ad groups with keywords, verify correct matching and "NEW AD GROUP" fallback.

### Integration Tests
- **Auth flow:** Verify OAuth2 round-trip with test credentials
- **Single account research:** Run full pipeline on one account, verify data flows from seeds → Keyword Planner → scores → database → API response → UI
- **Export:** Generate Google Ads Editor CSV, open in Google Ads Editor, verify it imports cleanly

### Manual Testing
- Run against 3-5 accounts with real data
- Have a non-technical team member (Lisa or Lauren) attempt the full workflow: view results, approve keywords, export, import into Google Ads Editor
- Verify the scoring feels right: do HIGH-scored keywords actually look like good additions? Do SKIP-scored keywords look irrelevant?

---

## Future Enhancements (Out of Scope for v1)

- **Competitor keyword discovery** using Auction Insights data from the Google Ads API
- **AI-powered ad copy suggestions** — feed the approved keywords + LP content into an LLM to generate RSA headline/description suggestions
- **Automated implementation** — use the Google Ads API to directly add approved keywords to accounts (requires mutate access, separate review)
- **Slack notifications** — alert the team when a research run completes or when new HIGH-priority opportunities are found
- **Scheduled runs** — automatic weekly/monthly research via cron or task scheduler
- **Search trend integration** — pull Google Trends data for top ideas to show macro-level demand trends beyond 12-month Keyword Planner data
