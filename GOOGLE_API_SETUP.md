# Google Ads API — Complete Setup Guide

This guide walks through every step needed to get Google Ads API access
working for the KWPlanner application. There are three separate things
to set up, in this order:

1. **Google Cloud Project** with OAuth2 credentials
2. **Google Ads API Developer Token** from the MCC account
3. **First OAuth2 sign-in** to generate a refresh token

Total time: ~30 minutes for setup, plus 1-5 business days for developer
token approval.

---

## Step 1: Create a Google Cloud Project

### 1a. Choose the right Google account

You need a Google account that can create Cloud projects. Two options:

| Approach | Pros | Cons |
|----------|------|------|
| **Personal Gmail** | No org permissions needed, no Parent Resource field | Separate from company account |
| **Workspace account** | Company-owned, easier to share | Requires org-level Project Creator role |

**If using a Workspace account** and you see "Parent resource" as a required field:
1. Go to https://console.cloud.google.com/iam-admin/iam
2. Switch the project selector at the top to your **organization** (not a project)
3. Click **Grant Access**
4. Principal: your own email address
5. Role: search for **Project Creator** and select it
6. Click **Save**
7. Wait 1-2 minutes, then retry creating the project

**If using a personal Gmail**: the Parent Resource field doesn't appear. Just
proceed to the next step.

### 1b. Create the project

1. Go to https://console.cloud.google.com/projectcreate
2. Project name: `KW Research` (or any name you like)
3. If the Parent resource field appears, click **Browse** and select your organization
   (see 1a above if nothing appears)
4. Click **Create**
5. Wait for the project to provision (~30 seconds)

### 1c. Enable the Google Ads API

1. Make sure your new project is selected in the top dropdown
2. Go to https://console.cloud.google.com/apis/library
3. Search for **Google Ads API**
4. Click on it, then click **Enable**
5. Wait for it to activate (~10 seconds)

### 1d. Configure the OAuth consent screen

Before creating credentials, you must set up a consent screen.

1. Go to https://console.cloud.google.com/apis/credentials/consent
2. Select **External** user type (unless you're on Google Workspace and want internal-only)
3. Click **Create**
4. Fill in:
   - **App name**: `KW Research`
   - **User support email**: your email
   - **Developer contact email**: your email
5. Click **Save and Continue**
6. On the **Scopes** page, click **Add or Remove Scopes**
7. Search for and add these scopes:
   - `https://www.googleapis.com/auth/adwords`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/userinfo.profile`
   - `https://www.googleapis.com/auth/spreadsheets` (optional, for Sheets export)
8. Click **Update**, then **Save and Continue**
9. On the **Test users** page, click **Add Users**
10. Add the email addresses of everyone who will use the app:
    - Your email (required)
    - Team members' emails (Pam, Lisa, Lauren, contractors)
11. Click **Save and Continue**, then **Back to Dashboard**

**Important**: While the app is in "Testing" mode, only the test users you
listed can sign in. This is fine for development and internal use. If you
eventually want to remove this restriction, you can publish the app (requires
Google's verification process, takes weeks — not needed for internal tools).

### 1e. Create OAuth2 credentials

1. Go to https://console.cloud.google.com/apis/credentials
2. Click **Create Credentials** → **OAuth 2.0 Client ID**
3. Application type: **Web application**
4. Name: `KW Research Web`
5. **Authorized JavaScript origins**: (add both)
   - `http://localhost:5173` (local frontend)
   - `https://kwplanner-web.onrender.com` (production frontend — update with your actual Render URL)
6. **Authorized redirect URIs**: (add both)
   - `http://localhost:8000/api/auth/callback` (local backend)
   - `https://kwplanner-api.onrender.com/api/auth/callback` (production — update with your actual Render URL)
7. Click **Create**
8. A dialog shows your **Client ID** and **Client Secret** — copy both
9. These go into your `.env` file:
   ```
   GOOGLE_CLIENT_ID=123456789-abcdef.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxx
   GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/callback
   ```

**Save these credentials securely.** You can always retrieve the Client ID from
the Credentials page, but the Client Secret is only shown once at creation
(you can create a new secret if you lose it).

---

## Step 2: Get a Google Ads API Developer Token

The developer token authenticates your application to the Google Ads API.
It's separate from OAuth2 — OAuth2 handles user identity, the developer token
handles application identity.

### 2a. Access the API Center

1. Sign in to Google Ads at https://ads.google.com
2. Make sure you're in the **MCC (Manager) account** (top-level account that
   manages the child accounts)
3. Click **Tools & Settings** (wrench icon) → **Setup** → **API Center**
4. If you don't see "API Center", you may need to opt in or contact Google support

### 2b. Apply for access

1. In the API Center, you'll see your Developer Token (or the option to create one)
2. Fill in the application form:
   - **API usage**: Select "Managing accounts on behalf of clients"
   - **Product URL**: Your Render backend URL (or `http://localhost:8000` for now)
   - **Contact email**: Your email
   - **Describe your use case**: Something like:
     > "Internal keyword research tool for our agency. We use the
     > KeywordPlanIdeaService to generate keyword ideas for ~40 managed client
     > accounts. The tool is read-only — it queries keyword metrics and
     > generates reports. It does not modify account settings or keywords."
3. Submit the application

### 2c. Access levels

| Level | Daily Limit | Approval Time | When to use |
|-------|-------------|---------------|-------------|
| **Test** | 15,000 ops | Instant | Development — only works with test accounts |
| **Basic** | 15,000 ops | 1-5 business days | Production — works with all accounts |
| **Standard** | Unlimited | Application review | High-volume usage (not needed for ~40 accounts) |

You get **Test access immediately**. This lets you develop and test the app
against test accounts. Apply for **Basic access** as soon as possible since
it can take up to 5 business days.

### 2d. Copy the token

Once you have your developer token (a string like `aBcDeFgHiJkLmNoP`):

```
GOOGLE_ADS_DEVELOPER_TOKEN=aBcDeFgHiJkLmNoP
```

Add this to your `.env` file.

### 2e. Copy your MCC Account ID

1. In Google Ads, look at the top-right corner — your MCC ID is displayed
   in the format `XXX-XXX-XXXX`
2. Store it **without dashes** in your `.env`:

```
GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890
```

---

## Step 3: First Sign-In and Refresh Token

The application handles this automatically through the web UI:

1. Start the backend: `uvicorn app.main:app --reload --port 8000`
2. Start the frontend: `npm run dev`
3. Open http://localhost:5173
4. Click **Sign in with Google**
5. Choose the Google account that has access to the MCC
6. Grant the requested permissions (Google Ads access, email, profile)
7. You'll be redirected back to the app — you're now authenticated

The backend stores the OAuth tokens in a session cookie. For production,
the refresh token persists access across sessions.

---

## Complete `.env` File

After completing all three steps, your `.env` file should look like:

```env
# App
DEBUG=false
SECRET_KEY=a-random-string-at-least-32-characters-long
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:8000

# Database
DATABASE_URL=sqlite+aiosqlite:///./kwplanner.db

# Google Ads API (Step 2)
GOOGLE_ADS_DEVELOPER_TOKEN=aBcDeFgHiJkLmNoP
GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890

# Google OAuth2 (Step 1e)
GOOGLE_CLIENT_ID=123456789-abcdef.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxx
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/callback
```

For Render production, set the same variables in the Render dashboard
and update URLs:
```env
FRONTEND_URL=https://kwplanner-web.onrender.com
BACKEND_URL=https://kwplanner-api.onrender.com
GOOGLE_REDIRECT_URI=https://kwplanner-api.onrender.com/api/auth/callback
DATABASE_URL=postgresql+asyncpg://user:pass@your-project.supabase.co:6543/postgres
```

---

## Troubleshooting

### "Access blocked: This app's request is invalid" (Error 400)
- **Cause**: Redirect URI mismatch
- **Fix**: The redirect URI in your `.env` must **exactly** match one of the
  URIs in Google Cloud Console → Credentials → OAuth 2.0 Client → Authorized
  redirect URIs. Check for trailing slashes, http vs https, port numbers.

### "The developer token is not approved" (Error 401)
- **Cause**: Using a Test-level token with production accounts
- **Fix**: Wait for Basic access approval, or test with test accounts only

### "User not in test users list" (Error 403)
- **Cause**: OAuth consent screen is in Testing mode and the signing-in user
  isn't listed as a test user
- **Fix**: Go to Cloud Console → APIs & Services → OAuth consent screen →
  Test users → Add the user's email

### "Google Ads API has not been enabled" (Error 403)
- **Cause**: The API isn't turned on for your Cloud project
- **Fix**: Go to https://console.cloud.google.com/apis/library and search for
  "Google Ads API" → Enable

### "Parent resource required" (during project creation)
- **Cause**: Workspace account without org-level Project Creator role
- **Fix**: See Step 1a — either grant yourself the role at the org level, or
  use a personal Gmail account to create the Cloud project

### "You don't have permission to access this customer" (Error 403)
- **Cause**: The signed-in user doesn't have access to the MCC
- **Fix**: In Google Ads, go to Tools → Access and Security → add the user's
  email as an Admin or Standard user on the MCC account

### "Rate limited" (Error 429)
- **Cause**: Exceeded daily API quota (15,000 ops for Basic access)
- **Fix**: Wait until midnight Pacific Time for quota reset. The app saves
  progress automatically.

---

## Verification Checklist

After setup, verify everything works:

- [ ] Google Cloud project exists with Google Ads API enabled
- [ ] OAuth consent screen configured with correct scopes
- [ ] Test users added to consent screen
- [ ] OAuth2 Client ID created with correct redirect URIs
- [ ] Developer token obtained from Google Ads API Center
- [ ] MCC Account ID copied (no dashes)
- [ ] `.env` file populated with all 6 values
- [ ] Backend starts without errors: `uvicorn app.main:app --reload`
- [ ] `/api/health` returns `{"status": "ok"}`
- [ ] Sign in with Google works and redirects back to app
- [ ] "Sync from MCC" loads real accounts (not mock data)
- [ ] Running research on one account produces keyword ideas
