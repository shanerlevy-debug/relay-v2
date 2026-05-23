"""Google OAuth login + signup routes.

GET /api/oauth/google/start     unauth. Returns 303 to Google's authorize URL.
GET /api/oauth/google/callback  unauth. Validates state, exchanges code,
                                creates new workspace+user OR logs in
                                existing one, sets session cookie.

Behavior:
- If a User with the Google email already exists → log them in.
- If no User → bootstrap: create new Workspace (display_name from
  Google profile) + new admin User (email_verified_at = now) + session
  cookie. Same end state as a fresh /api/auth/signup.

This unifies "Continue with Google" between /login and /signup — both
buttons go to the same /start, the callback figures out the right thing.
"""
from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from relay_api.core.config import settings
from relay_api.core.logging import get_logger
from relay_api.db.models import AuditLog, User, Workspace
from relay_api.db.session import get_db
from relay_api.services.auth.jwt_tokens import issue_session_token
from relay_api.services.auth.sessions import set_session_cookie
from relay_api.services.oauth.base import (
    OAUTH_STATE_COOKIE,
    OAuthError,
    deserialize_state,
)
from relay_api.services.oauth.google import GoogleProvider

log = get_logger(__name__)

router = APIRouter(prefix="/api/oauth/google", tags=["oauth-google"])


def _redirect_uri() -> str:
    return f"{settings.RELAY_API_PUBLIC_URL.rstrip('/')}/api/oauth/google/callback"


def _ui_redirect(path: str, **params) -> RedirectResponse:
    base = settings.RELAY_APP_BASE_URL.rstrip("/")
    qs = urlencode(params) if params else ""
    url = f"{base}{path}" + (f"?{qs}" if qs else "")
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _set_state_cookie(response: Response, value: str) -> None:
    """Same shape as the Slack-install state cookie but scoped to the
    Google OAuth callback path. Short-lived — only needs to survive the
    Google round-trip."""
    domain = settings.RELAY_OAUTH_COOKIE_DOMAIN or None
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=value,
        httponly=True,
        secure=settings.RELAY_ENV != "dev",
        samesite="lax",
        max_age=600,
        domain=domain,
        path="/api/oauth/google",
    )


def _clear_state_cookie(response: Response) -> None:
    domain = settings.RELAY_OAUTH_COOKIE_DOMAIN or None
    response.delete_cookie(
        key=OAUTH_STATE_COOKIE,
        domain=domain,
        path="/api/oauth/google",
    )


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------


@router.get("/start")
def get_start() -> RedirectResponse:
    """Begin a Google OAuth login. Public — no session required.

    Sets the signed state cookie and 303s to Google.
    """
    provider = GoogleProvider()
    try:
        result = provider.start_login(redirect_uri=_redirect_uri())
    except OAuthError as e:
        raise HTTPException(
            status_code=500 if e.code == "misconfigured" else 400,
            detail={"code": e.code, "message": str(e)},
        ) from e
    response = RedirectResponse(
        url=result.authorization_url,
        status_code=status.HTTP_303_SEE_OTHER,
    )
    _set_state_cookie(response, result.state_cookie_value)
    return response


# ---------------------------------------------------------------------------
# /callback
# ---------------------------------------------------------------------------


@router.get("/callback")
async def get_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Validate state, exchange code, log-in-or-bootstrap.

    Outcomes:
      ok          → set session cookie, redirect to /home
      bootstrap   → same (we just created the account in-flight)
      error codes → redirect to /login?google_oauth=error&code=<reason>
    """
    if error:
        resp = _ui_redirect("/login", google_oauth="error", code=f"google_{error}")
        _clear_state_cookie(resp)
        return resp

    if not code or not state:
        resp = _ui_redirect("/login", google_oauth="error", code="missing_params")
        _clear_state_cookie(resp)
        return resp

    state_cookie_value = request.cookies.get(OAUTH_STATE_COOKIE)
    if not state_cookie_value:
        return _ui_redirect("/login", google_oauth="error", code="no_state_cookie")

    try:
        state_payload = deserialize_state(state_cookie_value)
    except OAuthError:
        resp = _ui_redirect("/login", google_oauth="error", code="bad_state")
        _clear_state_cookie(resp)
        return resp

    if state_payload.get("nonce") != state:
        resp = _ui_redirect("/login", google_oauth="error", code="state_mismatch")
        _clear_state_cookie(resp)
        return resp

    verifier = state_payload.get("verifier")
    if not verifier:
        resp = _ui_redirect("/login", google_oauth="error", code="bad_state")
        _clear_state_cookie(resp)
        return resp

    # Exchange code for identity
    provider = GoogleProvider()
    try:
        identity = await provider.exchange_code(
            code=code,
            redirect_uri=_redirect_uri(),
            verifier=verifier,
        )
    except OAuthError as e:
        resp = _ui_redirect("/login", google_oauth="error", code=e.code)
        _clear_state_cookie(resp)
        return resp

    # Look up existing user by email — email lookup is the unifying identity.
    user = db.execute(
        select(User)
        .where(func.lower(User.email) == identity.email)
        .where(User.deleted_at.is_(None))
    ).scalar_one_or_none()

    bootstrap = user is None
    if bootstrap:
        # Create new workspace + admin user from the Google identity.
        workspace = Workspace(
            display_name=identity.display_name or identity.email.split("@")[0],
        )
        db.add(workspace)
        db.flush()
        user = User(
            workspace_id=workspace.id,
            email=identity.email,
            # No password — they log in via Google. Setting a password
            # later goes through a forgot-password flow (deferred).
            password_hash=None,
            email_verified_at=func.now(),
            role="admin",
        )
        db.add(user)
        db.flush()
        # Seed default group + admin membership for the new workspace.
        from relay_api.services.groups import (
            add_user_to_default_group,
            create_default_group,
        )
        create_default_group(db, workspace=workspace)
        add_user_to_default_group(db, user=user)
        db.add(AuditLog(
            workspace_id=workspace.id,
            actor_user_id=user.id,
            event_type="user.created_via_google_oauth",
            subject_type="user",
            subject_id=user.id,
            metadata_json={"email": user.email, "google_sub": identity.sub},
        ))
    else:
        # Existing user — stamp email_verified_at if Google says verified
        # and we hadn't recorded it.
        if user.email_verified_at is None:
            user.email_verified_at = func.now()
        db.add(AuditLog(
            workspace_id=user.workspace_id,
            actor_user_id=user.id,
            event_type="user.logged_in_via_google_oauth",
            subject_type="user",
            subject_id=user.id,
            metadata_json={"email": user.email, "google_sub": identity.sub},
        ))

    db.commit()
    db.refresh(user)

    # Issue session cookie + redirect to /home
    token, expires_at = issue_session_token(
        user_id=user.id,
        workspace_id=user.workspace_id,
    )
    resp = _ui_redirect("/home")
    set_session_cookie(resp, token, expires_at)
    _clear_state_cookie(resp)

    log.info(
        "google_oauth.success",
        bootstrap=bootstrap,
        user_id=str(user.id),
        workspace_id=str(user.workspace_id),
    )
    return resp
