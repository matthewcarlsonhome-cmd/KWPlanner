# MCC Keyword Research Platform — Setup & Deployment Guide

## Architecture Overview

```
Frontend (React + Tailwind + Vite)  →  Backend (Python FastAPI)  →  SQLite DB
                                            ↓
                                    Google Ads API
```

- **Frontend**: React SPA with Tailwind CSS, served by Vite (dev) or any static host
- **Backend**: Python FastAPI with async SQLAlchemy, SQLite database
- **API**: Google Ads API for keyword research (requires developer token + OAuth2)

---

## Prerequisites

### 1. System Requirements
- Python 3.10+
- Node.js 18+
- npm 9+

### 2. Google Ads API Access (Required for production)

**a. Developer Token**
- Apply at: https://developers.google.com/google-ads/api/docs/get-started/dev-token
- Apply under the MCC manager account
- Test access is instant; Basic access takes 1-5 business days

**b. Google Cloud OAuth2 Credentials**
- Go to https://console.cloud.google.com
- Create project "SSP Keyword Research"
- Enable the **Google Ads API**
- Go to APIs & Services > Credentials > Create OAuth 2.0 Client ID
- Type: Web application
- Authorized redirect URIs:
  - `http://localhost:8000/api/auth/callback` (development)
  - `https://your-domain.com/api/auth/callback` (production)
- Download client ID and secret

**c. MCC Account ID**
- Found in Google Ads UI, top-right corner when logged into MCC
- Format: XXX-XXX-XXXX (stored without dashes as `1234567890`)

**d. OAuth Scopes Required**
- `https://www.googleapis.com/auth/adwords`
- `https://www.googleapis.com/auth/spreadsheets` (for Google Sheets export)

---

## Development Setup

### 1. Clone and set up the backend

```bash
cd KWPlanner/backend

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials (see below)
```

### 2. Configure `.env`

```env
# App
DEBUG=true
SECRET_KEY=your-random-secret-key-here
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:8000

# Database
DATABASE_URL=sqlite+aiosqlite:///./kwplanner.db

# Google Ads API
GOOGLE_ADS_DEVELOPER_TOKEN=your-developer-token
GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890

# Google OAuth2
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/callback
```

**Note**: Without Google Ads API credentials, the app runs in **mock data mode** — all API calls return realistic sample data so you can test the UI and workflow.

### 3. Start the backend

```bash
cd KWPlanner/backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now at `http://localhost:8000`. Check health: `http://localhost:8000/api/health`

### 4. Set up and start the frontend

```bash
cd KWPlanner/frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

The frontend is now at `http://localhost:5173`.

### 5. Run tests

```bash
cd KWPlanner/backend

# Run all tests
python -m pytest tests/ -v

# Run just the scoring engine tests
python -m pytest tests/test_scorer.py -v

# Run just the API integration tests
python -m pytest tests/test_api.py -v
```

---

## Using the Application

### First-time Setup

1. Open `http://localhost:5173` in your browser
2. Click **"Sync from MCC"** on the Dashboard to load accounts
   - Without API credentials, mock accounts will be loaded
3. Click **"Run All Accounts"** or run research on individual accounts
4. Review keyword ideas on the Account Detail page
5. Approve/reject keywords and export as CSV for Google Ads Editor

### Workflow

1. **Dashboard** — See all accounts, run research, view status
2. **Account Detail** — Review keyword ideas with scores
   - **Opportunities tab**: Filter, sort, approve/reject keywords
   - **Seeds tab**: See which existing keywords drove the research
   - **Negatives tab**: Review irrelevant keywords to add as negatives
   - **History tab**: Compare runs over time
   - **Export tab**: Download CSV, Excel, or negative keyword lists
3. **Settings** — Configure research parameters and scoring weights
4. **Research Progress** — Live progress view during research runs

### Scoring System

Each keyword scores 0-100 across four dimensions (25 points each):
- **Volume**: Monthly search volume (500+ = 25pts)
- **Competition**: Lower = better (LOW = 25pts)
- **CPC Efficiency**: Idea CPC vs account average
- **Relevance**: Pool/spa industry keyword matching

Priorities: **HIGH** (75+), **MEDIUM** (50-74), **LOW** (25-49), **SKIP** (0-24)
Negative keyword candidates (pool table, carpool, etc.) are always SKIP.

---

## Production Deployment

### Option A: Single VPS (Simplest)

Deploy both frontend and backend on one server (DigitalOcean, Linode, etc.):

```bash
# 1. Set up the server
sudo apt update && sudo apt install python3-pip python3-venv nodejs npm nginx

# 2. Clone the repo
git clone <repo-url> /opt/kwplanner
cd /opt/kwplanner

# 3. Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with production values

# 4. Frontend build
cd ../frontend
npm install
npm run build

# 5. Configure nginx
```

**Nginx config** (`/etc/nginx/sites-available/kwplanner`):
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Frontend (static files)
    location / {
        root /opt/kwplanner/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable site and start
sudo ln -s /etc/nginx/sites-available/kwplanner /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**Systemd service** (`/etc/systemd/system/kwplanner.service`):
```ini
[Unit]
Description=MCC Keyword Research Platform
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/kwplanner/backend
Environment="PATH=/opt/kwplanner/backend/venv/bin"
ExecStart=/opt/kwplanner/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable kwplanner
sudo systemctl start kwplanner
```

### Option B: Render (Platform-as-a-Service)

**Backend (Render Web Service)**:
1. Create a new Web Service pointing to the repo
2. Build command: `cd backend && pip install -r requirements.txt`
3. Start command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables from `.env.example`

**Frontend (Render Static Site)**:
1. Create a new Static Site pointing to the repo
2. Build command: `cd frontend && npm install && npm run build`
3. Publish directory: `frontend/dist`
4. Add rewrite rule: `/* → /index.html` (for SPA routing)

### Option C: Railway

1. Create a new project from the repo
2. Add a service for the backend (Python)
3. Add a service for the frontend (Node.js static)
4. Configure environment variables
5. Railway auto-detects the stack and deploys

---

## Database

### Development: SQLite (default)
- Zero configuration — database file created automatically at `backend/kwplanner.db`
- Good for single-user / small team (SSP's ~5 users)
- All data persists across restarts

### Production: PostgreSQL (optional upgrade)
If you need multi-server deployment or more concurrent users:

1. Set up a PostgreSQL database (Supabase, Neon, or self-hosted)
2. Update `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/kwplanner
   ```
3. Add `asyncpg` to requirements: `pip install asyncpg`
4. The SQLAlchemy models work with both SQLite and PostgreSQL

---

## SSL/HTTPS

For production, add SSL with Let's Encrypt:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

Update `.env`:
```
FRONTEND_URL=https://your-domain.com
BACKEND_URL=https://your-domain.com
GOOGLE_REDIRECT_URI=https://your-domain.com/api/auth/callback
```

Update the Google Cloud Console OAuth2 redirect URI to match.

---

## API Rate Limits

- Google Ads API Basic access: 15,000 operations/day
- Each research run uses ~80-120 API calls (2-3 per account × 40 accounts)
- Built-in delays: 1s between Keyword Planner calls, 2s between accounts
- Total estimated run time: 5-10 minutes for all 40 accounts
- If rate limited, the app saves progress and shows a clear message

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No accounts found" | Click "Sync from MCC" — or check that API credentials are configured |
| Mock data showing | Set `GOOGLE_ADS_DEVELOPER_TOKEN` in `.env` for real data |
| OAuth errors | Verify redirect URI matches in `.env` and Google Cloud Console |
| "Rate limited" | Wait 24 hours — Google resets daily quota at midnight Pacific |
| Empty Keyword Planner results | Account may have low/no recent spend |
| Tests failing | Run `pip install -r requirements.txt` to ensure all deps installed |

---

## Project Structure

```
KWPlanner/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── config.py            # Environment settings
│   │   ├── database.py          # SQLAlchemy engine/session
│   │   ├── models/
│   │   │   ├── models.py        # ORM models (Account, KeywordIdea, etc.)
│   │   │   └── schemas.py       # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── auth.py          # Google OAuth2 login/callback
│   │   │   ├── accounts.py      # Account listing & sync
│   │   │   ├── research.py      # Research run management
│   │   │   ├── results.py       # Keyword idea browsing & filtering
│   │   │   ├── decisions.py     # Approve/reject/watchlist
│   │   │   ├── export.py        # CSV/Excel/Sheets export
│   │   │   └── settings_router.py  # Config management
│   │   └── services/
│   │       ├── scorer.py        # Keyword scoring engine
│   │       ├── google_ads.py    # Google Ads API client
│   │       ├── research.py      # Research orchestration
│   │       └── export.py        # Export file generation
│   ├── tests/
│   │   ├── test_scorer.py       # 46 scoring engine tests
│   │   └── test_api.py          # 24 API integration tests
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.jsx             # React app entry
│   │   ├── lib/api.js           # API client
│   │   ├── components/
│   │   │   └── Layout.jsx       # App shell & navigation
│   │   └── pages/
│   │       ├── Dashboard.jsx    # Account overview
│   │       ├── AccountDetail.jsx # Keyword ideas & decisions
│   │       ├── Settings.jsx     # Configuration
│   │       └── ResearchProgress.jsx # Live progress
│   ├── package.json
│   └── index.html
├── MCC_Keyword_Research_Platform_Spec.md
├── SETUP_AND_DEPLOY.md
└── .gitignore
```
