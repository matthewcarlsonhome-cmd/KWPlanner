"""OAuth2 authentication routes for Google Ads API access."""

import logging
from typing import Optional

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse

from app.config import settings
from app.models.schemas import UserInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory session store (use Redis in production)
_sessions: dict = {}

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SCOPES = [
    "https://www.googleapis.com/auth/adwords",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


@router.get("/login")
async def login():
    """Redirect to Google OAuth2 consent screen."""
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}")


@router.get("/callback")
async def callback(code: str, request: Request):
    """Handle OAuth2 callback — exchange code for tokens."""
    import httpx

    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_response = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        })

        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange auth code")

        tokens = token_response.json()

        # Get user info
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )

        if userinfo_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")

        userinfo = userinfo_response.json()

    # Store session
    import secrets
    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = {
        "email": userinfo.get("email"),
        "name": userinfo.get("name"),
        "picture": userinfo.get("picture"),
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
    }

    # Set cookie and redirect to frontend
    response = RedirectResponse(url=settings.frontend_url)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=86400 * 30,  # 30 days
        samesite="lax",
    )
    return response


@router.get("/me", response_model=UserInfo)
async def me(request: Request):
    """Return current user info."""
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in _sessions:
        # For development, return a mock user
        return UserInfo(
            email="matthew@sspdigital.com",
            name="Matthew (Dev Mode)",
            picture=None,
            is_authenticated=True,
        )

    session = _sessions[session_id]
    return UserInfo(
        email=session["email"],
        name=session.get("name"),
        picture=session.get("picture"),
        is_authenticated=True,
    )


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Clear session."""
    session_id = request.cookies.get("session_id")
    if session_id and session_id in _sessions:
        del _sessions[session_id]
    response.delete_cookie("session_id")
    return {"message": "Logged out"}


def get_refresh_token(request: Request) -> Optional[str]:
    """Helper to get refresh token from current session."""
    session_id = request.cookies.get("session_id")
    if session_id and session_id in _sessions:
        return _sessions[session_id].get("refresh_token")
    return None
