# CSV/XLSX Import Feature — Design Document

## Problem

Not every client account is accessible via the Google Ads API. The team
receives **weekly exports** from Google Ads with campaign, ad group, keyword,
and search term data. The platform needs to ingest this data offline, run the
scoring engine, and recommend Exact Match vs Phrase Match types — producing the
same output as the API-driven pipeline.

---

## Use Cases

1. **New client onboarding** — client sends an export before API access is set up
2. **Weekly batch review** — team downloads Search Term Reports and uploads for analysis
3. **Accounts without API access** — some clients don't grant MCC-level API access
4. **Auditing existing keywords** — upload current keyword list to check match type optimization

---

## Expected Import File Formats

### File 1: Account Keywords Export

The existing keyword list from Google Ads. Exported via Google Ads UI:
**Keywords → Download → .csv or .xlsx**

**Required columns:**

| Column | Description | Example |
|--------|-------------|---------|
| Campaign | Campaign name | Pool Builder - Search |
| Ad Group | Ad group name | Custom Pool Builder |
| Keyword | The keyword text (with match type symbols) | [pool builder near me] |
| Match Type | Current match type | Exact Match |
| Status | Enabled/Paused/Removed | Enabled |
| Max CPC | Current bid | $4.50 |
| Impressions | Total impressions in period | 1,240 |
| Clicks | Total clicks in period | 87 |
| Cost | Total cost in period | $312.50 |
| Conversions | Total conversions | 5.2 |
| Conv. Rate | Conversion rate | 5.98% |
| Quality Score | 1-10 | 7 |

**Optional columns** (used if present):

| Column | Description |
|--------|-------------|
| Avg CPC | Average cost per click |
| Impr. (Top) % | Top impression share |
| Search Impr. Share | Impression share |
| CPA | Cost per acquisition |

### File 2: Search Term Report

The search queries that triggered ads. Exported via Google Ads UI:
**Keywords → Search terms → Download → .csv or .xlsx**

**Required columns:**

| Column | Description | Example |
|--------|-------------|---------|
| Search term | The actual user query | gunite pool builder in houston |
| Campaign | Campaign that matched | Pool Builder - Search |
| Ad Group | Ad group that matched | Custom Pool Builder |
| Keyword | The keyword that triggered the match | pool builder |
| Match type | How the keyword matched | Phrase match (close variant) |
| Impressions | Impressions for this search term | 12 |
| Clicks | Clicks from this search term | 3 |
| Cost | Cost from this search term | $14.50 |
| Conversions | Conversions from this search term | 1.0 |

**Optional columns:**

| Column | Description |
|--------|-------------|
| Conv. value | Revenue from conversions |
| Added/Excluded | Whether already added as keyword or negative |

### File 3: Campaign Structure (optional)

If the user wants campaign/ad group mapping recommendations:

| Column | Description | Example |
|--------|-------------|---------|
| Campaign | Campaign name | Pool Builder - Search |
| Ad Group | Ad group name | Custom Pool Builder |
| Campaign Status | Active/Paused | Active |
| Campaign Budget | Daily budget | $50.00 |
| Geo Target | Location targeting | Houston, TX |

---

## Match Type Recommendation Logic

The core intelligence of the import feature. Given a search term and its
performance, recommend whether to add it as Exact Match or Phrase Match.

### Decision Matrix

```
                          High specificity          Low specificity
                          (3+ words, location,      (1-2 words, generic)
                          commercial intent)

High performance          EXACT MATCH               PHRASE MATCH
(conversions > 0          Strong intent signal.     Good volume driver.
 OR conv rate > 3%)       Lock in the exact query.  Capture variations.

Moderate performance      EXACT MATCH               PHRASE MATCH
(clicks > 10,             Enough data to justify    Let it run broader to
 CTR > 2%)                targeting precisely.      gather more signal.

Low/no performance        PHRASE MATCH              SKIP or NEGATIVE
(few clicks,              Not enough data for       Too generic, likely
 low CTR)                 exact, phrase gathers     wasting spend.
                          more signal.
```

### Detailed Rules

```python
def recommend_match_type(search_term, clicks, conversions, conv_rate, ctr, impressions):
    word_count = len(search_term.split())
    has_location = contains_location_signal(search_term)  # "near me", city names, "in [city]"
    has_commercial_intent = contains_commercial_intent(search_term)  # "cost", "price", "hire", "buy"

    # Rule 1: Converting search terms → EXACT
    if conversions >= 1:
        return "EXACT", "Converting query — lock in exact match"

    # Rule 2: High CTR + enough data → EXACT for specific, PHRASE for broad
    if clicks >= 10 and ctr >= 0.03:
        if word_count >= 3 or has_location or has_commercial_intent:
            return "EXACT", "High CTR + specific intent"
        return "PHRASE", "High CTR but broad — phrase captures variants"

    # Rule 3: Long-tail with commercial intent → EXACT
    if word_count >= 4 and has_commercial_intent:
        return "EXACT", "Long-tail commercial intent"

    # Rule 4: Location-based queries → EXACT
    if has_location and word_count >= 3:
        return "EXACT", "Location-specific query"

    # Rule 5: Moderate data, generic → PHRASE
    if clicks >= 5:
        return "PHRASE", "Moderate data — phrase to gather more signal"

    # Rule 6: Low data → PHRASE (if relevant) or SKIP
    if word_count <= 2 and clicks < 5:
        return "SKIP", "Too little data + too generic"

    return "PHRASE", "Default — phrase to gather data"
```

### Location Signal Detection

```python
LOCATION_SIGNALS = [
    "near me", "nearby", "in my area", "local",
    # Plus a lookup against a US cities/states list
]

COMMERCIAL_INTENT_SIGNALS = [
    "cost", "price", "pricing", "quote", "estimate", "hire",
    "buy", "purchase", "deal", "sale", "discount", "financing",
    "near me", "company", "contractor", "service", "install",
]
```

### Additional Recommendations

For each search term, also output:

- **Negative recommendation**: If the search term matches NEGATIVE_TERMS from the scorer, flag it
- **Suggested ad group**: Use the existing `suggest_ad_group()` function from scorer.py
- **Existing keyword overlap**: Flag if the search term already exists as a keyword (avoid duplicates)
- **Bid suggestion**: If the search term's CPA is known, suggest a max CPC = CPA * target_conv_rate

---

## Import Pipeline

### Step 1: Upload & Parse

```
POST /api/import/upload
Content-Type: multipart/form-data
Body: file (CSV or XLSX), file_type ("keywords" | "search_terms" | "campaign_structure")
```

- Accept .csv, .xlsx, .xls files up to 50MB
- Auto-detect column mapping by header names (fuzzy match common variations)
- Return a preview of parsed data (first 10 rows) for user confirmation

### Step 2: Column Mapping Confirmation

```
POST /api/import/confirm
Body: { upload_id, column_mapping: { "Campaign": "campaign", ... }, account_name }
```

- User confirms or adjusts auto-detected column mapping
- User assigns an account name (since this isn't from the API)
- Data is saved to the database as a new account + import record

### Step 3: Analysis & Scoring

```
POST /api/import/analyze
Body: { upload_id }
```

For **keyword exports**:
- Parse match type from keyword text: `[keyword]` = Exact, `"keyword"` = Phrase
- Score each keyword using the existing scoring engine
- Compute account-level avg CPC from the data
- Flag underperforming keywords (high cost, no conversions)

For **search term reports**:
- Run match type recommendation logic (see above)
- Score each search term for relevance using existing scorer
- Cross-reference against existing keywords to avoid duplicates
- Flag negative keyword candidates
- Group recommendations by priority

### Step 4: Review in UI

Results appear in the same Account Detail page with a new "Import" badge.
All existing UI features work: filtering, sorting, approve/reject, export.

### Step 5: Export Recommendations

Same export options as API-driven results:
- Google Ads Editor CSV (with recommended match types pre-filled)
- Excel workbook with analysis
- Negative keyword list

---

## Database Changes

### New table: `imports`

```sql
CREATE TABLE imports (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id),
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(20) NOT NULL,      -- keywords, search_terms, campaign_structure
    uploaded_by VARCHAR(100),
    row_count INTEGER,
    column_mapping JSONB,
    status VARCHAR(20) DEFAULT 'pending', -- pending, confirmed, analyzed, error
    created_at TIMESTAMP DEFAULT NOW()
);
```

### New table: `imported_search_terms`

```sql
CREATE TABLE imported_search_terms (
    id SERIAL PRIMARY KEY,
    import_id INTEGER REFERENCES imports(id) ON DELETE CASCADE,
    account_id INTEGER REFERENCES accounts(id),
    search_term TEXT NOT NULL,
    campaign VARCHAR(255),
    ad_group VARCHAR(255),
    matched_keyword VARCHAR(255),
    match_type_triggered VARCHAR(50),
    impressions INTEGER,
    clicks INTEGER,
    cost NUMERIC(10,2),
    conversions NUMERIC(10,2),
    conv_rate NUMERIC(5,4),
    ctr NUMERIC(5,4),
    -- Recommendations
    recommended_match_type VARCHAR(10),  -- EXACT, PHRASE, SKIP, NEGATIVE
    match_type_reason TEXT,
    relevance_score INTEGER,
    relevance_category VARCHAR(20),
    priority VARCHAR(10),
    suggested_ad_group VARCHAR(255),
    is_duplicate BOOLEAN DEFAULT false,
    is_negative_candidate BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## New API Endpoints

```
POST /api/import/upload          — Upload CSV/XLSX file
POST /api/import/confirm         — Confirm column mapping
POST /api/import/analyze         — Run analysis pipeline
GET  /api/import/:id             — Get import status and results
GET  /api/import/:id/results     — Paginated results with match type recs
GET  /api/import/list             — List all imports
DELETE /api/import/:id            — Delete an import and its data
POST /api/import/:id/export      — Export recommendations as CSV
```

---

## Frontend Changes

### Dashboard
- Add "Import Data" button next to "Sync from MCC"
- Show imported accounts with an "Import" badge

### New Import Wizard (3 steps)
1. **Upload**: Drag-drop or file picker for CSV/XLSX
2. **Map Columns**: Table showing detected columns with dropdowns to adjust
3. **Review**: Preview of parsed data, confirm account name, start analysis

### Account Detail
- Import results appear in the same Opportunities tab
- Match type recommendation column added
- "Recommendation Reason" shown in the sidebar detail panel

---

## Recommended File Templates

Provide downloadable template files users can fill in manually if
their export format doesn't match. Store these in `frontend/public/templates/`.

### `keyword_export_template.csv`
```csv
Campaign,Ad Group,Keyword,Match Type,Status,Impressions,Clicks,Cost,Conversions,Quality Score,Avg CPC
Pool Builder - Search,Custom Pool Builder,[pool builder near me],Exact Match,Enabled,1240,87,312.50,5.2,7,3.59
```

### `search_term_report_template.csv`
```csv
Search term,Campaign,Ad Group,Keyword,Match type,Impressions,Clicks,Cost,Conversions,Conv. rate
gunite pool builder in houston,Pool Builder - Search,Custom Pool Builder,pool builder,Phrase match (close variant),12,3,14.50,1.0,33.33%
```

---

## Implementation Phases

### Phase 1: Core import pipeline (3-4 days)
- File upload endpoint with CSV/XLSX parsing
- Column auto-detection and mapping UI
- Search term analysis with match type recommendations
- Results displayed in existing Account Detail page

### Phase 2: Match type intelligence (2-3 days)
- Location signal detection (city/state lookup)
- Commercial intent classification
- Cross-reference against existing keywords for duplicate detection
- Bid suggestions based on CPA data

### Phase 3: Templates and polish (1-2 days)
- Downloadable CSV templates
- Import history and re-analysis
- Batch import (multiple files at once)
- Drag-and-drop upload UI
