"""Slack OAuth install routes.

GET  /api/oauth/slack/start     — authenticated, admin-only. Returns 302
                                  to Slack's authorize URL and sets the
                                  signed state cookie.
GET  /api/oauth/slack/callback  — public (Slack hits it). Validates state
                                  cookie, exchanges code, persists encrypted
                                  bot token, redirects to UI settings page
                                  with ?slack_install=ok|error&code=…

The OAuth "state" lives in a signed cookie (relay_oauth_state) — Slack just
echoes the state value back as a query param, and we use the cookie to
validate it. CSRF defense + carries (workspace_id, user_id) so the callback
knows which workspace owns the install.
"""
from __future__ import annotations

import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from relay_api.core.config import settings
from relay_api.core.dependencies import current_user, current_workspace, require_admin
from relay_api.db.models import AuditLog, User, Workspace
from relay_api.db.session import get_db
from relay_api.services.oauth.base import (
    OAUTH_STATE_COOKIE,
    OAuthError,
    deserialize_state,
)
from relay_api.services.oauth.slack import SlackProvider
from relay_api.services.slack_install import (
    SlackInstallError,
    create_install,
)

router = APIRouter(prefix="/api/oauth/slack", tags=["oauth-slack"])


def _redirect_uri() -> str:
    """The callback URL Slack returns the browser to. Configured in the
    Slack app's OAuth & Permissions page; must match exactly."""
    return f"{settings.RELAY_API_PUBLIC_URL.rstrip('/')}/api/oauth/slack/callback"


def _ui_redirect(status: str, *, code: str | None = None) -> RedirectResponse:
    """Build the URI we send the browser back to after the callback. The
    UI's /settings page reads `?slack_install=` and renders the right toast.
    """
    qs = {"slack_install": status}
    if code:
        qs["code"] = code
    return RedirectResponse(
        url=f"{settings.RELAY_APP_BASE_URL.rstrip('/')}/settings?{urlencode(qs)}",
        status_code=status_module_303(),
    )


def status_module_303() -> int:
    """303 forces a GET on the next request — correct for an OAuth callback
    that's returning the browser to a stateful UI page."""
    return status.HTTP_303_SEE_OTHER


def _set_state_cookie(response: Response, value: str) -> None:
    """Write the OAuth state cookie. Short-lived — only needs to survive
    the Slack redirect round-trip (~10 min for a slow click-through user).
    """
    domain = settings.RELAY_OAUTH_COOKIE_DOMAIN or None
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=value,
        httponly=True,
        secure=settings.RELAY_ENV != "dev",
        samesite="lax",
        max_age=600,  # 10 minutes
        domain=domain,
        path="/api/oauth/slack",  # scoped narrowly
    )


def _clear_state_cookie(response: Response) -> None:
    domain = settings.RELAY_OAUTH_COOKIE_DOMAIN or None
    response.delete_cookie(
        key=OAUTH_STATE_COOKIE,
        domain=domain,
        path="/api/oauth/slack",
    )


# ---------------------------------------------------------------------------
# /start — admin clicks "Connect Slack"
# ---------------------------------------------------------------------------


@router.get("/start")
def get_start(
    request: Request,
    user: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
) -> RedirectResponse:
    """Begin a Slack install. Sets the state cookie and 302s to Slack."""
    provider = SlackProvider()
    try:
        result = provider.start_install(
            redirect_uri=_redirect_uri(),
            workspace_id=str(workspace.id),
            user_id=str(user.id),
        )
    except OAuthError as e:
        # Misconfigured (no client id) — surface as 500. This shouldn't
        # happen in a properly-configured prod deployment.
        raise HTTPException(
            status_code=500,
            detail={"code": e.code, "message": str(e)},
        ) from e

    response = RedirectResponse(
        url=result.authorization_url,
        status_code=status_module_303(),
    )
    _set_state_cookie(response, result.state_cookie_value)
    return response


# ---------------------------------------------------------------------------
# /callback — Slack returns the browser here
# ---------------------------------------------------------------------------


@router.get("/callback")
async def get_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Validate the state cookie, exchange the code, persist the install,
    redirect to UI settings.

    Public endpoint — Slack hits this directly. CSRF defense is the signed
    state cookie. Never trust query params except as inputs to validation.
    """
    # If Slack itself returned an error (user denied, app revoked, etc.),
    # short-circuit to the UI.
    if error:
        # Clear the state cookie regardless — it's no good after a denial.
        resp = _ui_redirect("error", code=f"slack_{error}")
        _clear_state_cookie(resp)
        return resp

    if not code or not state:
        resp = _ui_redirect("error", code="missing_params")
        _clear_state_cookie(resp)
        return resp

    state_cookie_value = request.cookies.get(OAUTH_STATE_COOKIE)
    if not state_cookie_value:
        # Cookie cleared, lost on redirect, or never set (someone navigated
        # to /callback directly). Don't trust the request.
        return _ui_redirect("error", code="no_state_cookie")

    try:
        state_payload = deserialize_state(state_cookie_value)
    except OAuthError:
        resp = _ui_redirect("error", code="bad_state")
        _clear_state_cookie(resp)
        return resp

    if state_payload.get("nonce") != state:
        # State query param doesn't match what's in the signed cookie.
        # Classic CSRF defense — the attacker can't sign a cookie with our
        # secret, so a stolen state value won't match a cookie they planted.
        resp = _ui_redirect("error", code="state_mismatch")
        _clear_state_cookie(resp)
        return resp

    workspace_id_raw = state_payload.get("workspace_id")
    user_id_raw = state_payload.get("user_id")
    if not workspace_id_raw or not user_id_raw:
        resp = _ui_redirect("error", code="bad_state")
        _clear_state_cookie(resp)
        return resp

    try:
        workspace_id = uuid.UUID(workspace_id_raw)
        user_id = uuid.UUID(user_id_raw)
    except ValueError:
        resp = _ui_redirect("error", code="bad_state")
        _clear_state_cookie(resp)
        return resp

    # Re-check the user is still an admin of the workspace. Defends against
    # role changes mid-flow (would be rare, but the alternative is a
    # silent install by a former admin).
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None or user.role != "admin":
        resp = _ui_redirect("error", code="admin_required")
        _clear_state_cookie(resp)
        return resp
    if user.workspace_id != workspace_id:
        resp = _ui_redirect("error", code="workspace_mismatch")
        _clear_state_cookie(resp)
        return resp

    # Exchange the code for a bot token.
    provider = SlackProvider()
    try:
        exchange = await provider.exchange_code(
            code=code,
            redirect_uri=_redirect_uri(),
        )
    except OAuthError as e:
        resp = _ui_redirect("error", code=e.code)
        _clear_state_cookie(resp)
        return resp

    # Persist the install. The service handles the two collision cases
    # (team_already_connected, workspace_has_active_install).
    try:
        install = create_install(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            exchange=exchange,
        )
    except SlackInstallError as e:
        # Rollback any partial state.
        db.rollback()
        resp = _ui_redirect("error", code=e.code)
        _clear_state_cookie(resp)
        return resp

    # Audit log: who installed what when.
    db.add(AuditLog(
        workspace_id=workspace_id,
        actor_user_id=user_id,
        event_type="workspace.slack_installed",
        subject_type="slack_install",
        subject_id=install.id,
        metadata_json={
            "slack_team_id": exchange.team_id,
            "slack_team_name": exchange.team_name,
            "scopes_granted": exchange.bot_scopes_granted,
            "bot_user_id": exchange.bot_user_id,
        },
    ))

    db.commit()

    resp = _ui_redirect("ok")
    _clear_state_cookie(resp)
    return resp
