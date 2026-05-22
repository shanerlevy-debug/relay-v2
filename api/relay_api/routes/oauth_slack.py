"""Slack OAuth install routes — both in-product "Connect Slack" and
landing-page "Add to Slack".

GET  /api/oauth/slack/start     — public. Branches on session presence:
                                  - signed-in admin → in-product install
                                    (state carries workspace_id + user_id)
                                  - anonymous → Add-to-Slack bootstrap flow
                                    (state carries {"anonymous": true})
GET  /api/oauth/slack/callback  — public (Slack hits it). Validates state
                                  cookie, exchanges code, and either:
                                  - attaches install to the authed workspace
                                    (in-product path), or
                                  - creates a fresh Workspace + admin User
                                    and a session cookie (bootstrap path).

The OAuth "state" lives in a signed cookie (relay_oauth_state) — Slack just
echoes the state value back as a query param, and we use the cookie to
validate it. CSRF defense + carries (workspace_id, user_id) or the
"anonymous" marker so the callback knows which path to take.
"""
from __future__ import annotations

import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from relay_api.core.config import settings
from relay_api.core.logging import get_logger
from relay_api.db.models import AuditLog, User
from relay_api.db.session import get_db
from relay_api.services.auth.jwt_tokens import (
    TokenError,
    issue_session_token,
    verify_session_token,
)
from relay_api.services.auth.sessions import COOKIE_NAME, set_session_cookie
from relay_api.services.oauth.base import (
    OAUTH_STATE_COOKIE,
    OAuthError,
    deserialize_state,
)
from relay_api.services.oauth.slack import SlackProvider
from relay_api.services.slack_install import (
    SlackInstallError,
    bootstrap_from_slack_install,
    create_install,
)

log = get_logger(__name__)

router = APIRouter(prefix="/api/oauth/slack", tags=["oauth-slack"])


def _redirect_uri() -> str:
    """The callback URL Slack returns the browser to. Configured in the
    Slack app's OAuth & Permissions page; must match exactly."""
    return f"{settings.RELAY_API_PUBLIC_URL.rstrip('/')}/api/oauth/slack/callback"


def _ui_redirect(status: str, *, code: str | None = None) -> RedirectResponse:
    """Redirect for the *in-product* path — lands on /settings with a toast.

    Use _anon_redirect() for the bootstrap path; the anonymous user isn't
    signed in yet so /settings would just 401.
    """
    qs = {"slack_install": status}
    if code:
        qs["code"] = code
    return RedirectResponse(
        url=f"{settings.RELAY_APP_BASE_URL.rstrip('/')}/settings?{urlencode(qs)}",
        status_code=status_module_303(),
    )


def _anon_redirect(path: str, **params) -> RedirectResponse:
    """Redirect for the anonymous Add-to-Slack path. The visitor hasn't
    completed Relay signup yet — send them to /, /login, or /signup with
    a query-param flag the page reads to render a toast/banner."""
    base = settings.RELAY_APP_BASE_URL.rstrip("/")
    qs = urlencode(params) if params else ""
    url = f"{base}{path}" + (f"?{qs}" if qs else "")
    return RedirectResponse(url=url, status_code=status_module_303())


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
# /start — admin clicks "Connect Slack" OR anonymous "Add to Slack"
# ---------------------------------------------------------------------------


def _resolve_optional_session(
    request: Request,
    db: Session,
) -> User | None:
    """Decode the session cookie if present + valid. Returns None for any
    of: no cookie, invalid token, expired, deleted user. The /start route
    uses this to decide between the in-product path and the anonymous
    Add-to-Slack bootstrap path.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = verify_session_token(token)
    except TokenError:
        return None
    user_id_raw = payload.get("sub")
    if not user_id_raw:
        return None
    try:
        user_id = uuid.UUID(user_id_raw)
    except ValueError:
        return None
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        return None
    return user


@router.get("/start")
def get_start(
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Begin a Slack install. Public — anonymous visitors get the bootstrap
    path; signed-in admins get the in-product attach path.

    Sets the state cookie and 303s to Slack.
    """
    user = _resolve_optional_session(request, db)
    provider = SlackProvider()

    if user is not None:
        # Signed-in flow — must be an admin to attach an install to a
        # workspace. Members get a 403 with a useful error code.
        if user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "admin_required",
                    "message": "only workspace admins can install Slack",
                },
            )
        try:
            result = provider.start_install(
                redirect_uri=_redirect_uri(),
                workspace_id=str(user.workspace_id),
                user_id=str(user.id),
            )
        except OAuthError as e:
            raise HTTPException(
                status_code=500,
                detail={"code": e.code, "message": str(e)},
            ) from e
    else:
        # Anonymous flow — Add to Slack. State carries no workspace/user;
        # the callback fetches the installer's email via users.info and
        # creates a new Relay workspace.
        try:
            result = provider.start_install_anonymous(redirect_uri=_redirect_uri())
        except OAuthError as e:
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
    """Validate the state cookie, exchange the code, dispatch to either the
    in-product attach path or the anonymous bootstrap path.

    Public endpoint — Slack hits this directly. CSRF defense is the signed
    state cookie. Never trust query params except as inputs to validation.
    """
    if error:
        resp = _ui_redirect("error", code=f"slack_{error}")
        _clear_state_cookie(resp)
        return resp

    if not code or not state:
        resp = _ui_redirect("error", code="missing_params")
        _clear_state_cookie(resp)
        return resp

    state_cookie_value = request.cookies.get(OAUTH_STATE_COOKIE)
    if not state_cookie_value:
        return _ui_redirect("error", code="no_state_cookie")

    try:
        state_payload = deserialize_state(state_cookie_value)
    except OAuthError:
        resp = _ui_redirect("error", code="bad_state")
        _clear_state_cookie(resp)
        return resp

    if state_payload.get("nonce") != state:
        resp = _ui_redirect("error", code="state_mismatch")
        _clear_state_cookie(resp)
        return resp

    # Dispatch on state shape — anonymous bootstrap vs admin attach.
    is_anonymous = bool(state_payload.get("anonymous"))
    if is_anonymous:
        return await _handle_anonymous_callback(
            code=code,
            db=db,
        )

    return await _handle_authenticated_callback(
        code=code,
        state_payload=state_payload,
        db=db,
    )


# ---------------------------------------------------------------------------
# Callback dispatch helpers
# ---------------------------------------------------------------------------


async def _handle_authenticated_callback(
    *,
    code: str,
    state_payload: dict,
    db: Session,
) -> RedirectResponse:
    """Existing in-product path: state carries workspace_id + user_id."""
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

    # Re-check the user is still an admin. Role changes mid-flow are rare
    # but the alternative is a silent install by a former admin.
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None or user.role != "admin":
        resp = _ui_redirect("error", code="admin_required")
        _clear_state_cookie(resp)
        return resp
    if user.workspace_id != workspace_id:
        resp = _ui_redirect("error", code="workspace_mismatch")
        _clear_state_cookie(resp)
        return resp

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

    try:
        install = create_install(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            exchange=exchange,
        )
    except SlackInstallError as e:
        db.rollback()
        resp = _ui_redirect("error", code=e.code)
        _clear_state_cookie(resp)
        return resp

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


async def _handle_anonymous_callback(
    *,
    code: str,
    db: Session,
) -> RedirectResponse:
    """Add-to-Slack bootstrap path. No Relay session yet — we mint one.

    Flow:
      1. Exchange Slack code → bot token + authed_user.id
      2. Call users.info → installer email + name
      3. Bootstrap Workspace + admin User + install (one transaction)
      4. Issue a session cookie
      5. Redirect to /home with a fresh workspace ready to use

    Failure routing (each falls back to a UI page with a query-param flag):
      email_in_use         → /login?slack=email_in_use
      email_unavailable    → /signup?slack=email_unavailable
      team_already_*       → /login?slack=team_already_connected
      everything else      → /signup?slack=error&code=<...>
    """
    provider = SlackProvider()
    try:
        exchange = await provider.exchange_code(
            code=code,
            redirect_uri=_redirect_uri(),
        )
    except OAuthError as e:
        resp = _anon_redirect("/signup", slack="error", code=e.code)
        _clear_state_cookie(resp)
        return resp

    if not exchange.authed_user_id:
        # Slack didn't tell us who clicked install. Shouldn't happen with
        # the scopes we request, but defend anyway.
        resp = _anon_redirect("/signup", slack="email_unavailable")
        _clear_state_cookie(resp)
        return resp

    try:
        installer = await provider.get_user_info(
            bot_token=exchange.bot_token,
            user_id=exchange.authed_user_id,
        )
    except OAuthError as e:
        resp = _anon_redirect(
            "/signup",
            slack=e.code if e.code == "email_unavailable" else "error",
            code=e.code,
        )
        _clear_state_cookie(resp)
        return resp

    try:
        result = bootstrap_from_slack_install(
            db,
            exchange=exchange,
            installer=installer,
        )
    except SlackInstallError as e:
        db.rollback()
        if e.code == "email_in_use":
            resp = _anon_redirect("/login", slack="email_in_use")
        elif e.code == "team_already_connected":
            resp = _anon_redirect("/login", slack="team_already_connected")
        else:
            resp = _anon_redirect("/signup", slack="error", code=e.code)
        _clear_state_cookie(resp)
        return resp

    # Audit log on the new workspace.
    db.add(AuditLog(
        workspace_id=result.workspace.id,
        actor_user_id=result.user.id,
        event_type="workspace.created_via_slack_install",
        subject_type="workspace",
        subject_id=result.workspace.id,
        metadata_json={
            "slack_team_id": exchange.team_id,
            "slack_team_name": exchange.team_name,
            "installer_email": installer.email,
            "installer_slack_user_id": installer.user_id,
            "scopes_granted": exchange.bot_scopes_granted,
        },
    ))
    db.add(AuditLog(
        workspace_id=result.workspace.id,
        actor_user_id=result.user.id,
        event_type="workspace.slack_installed",
        subject_type="slack_install",
        subject_id=result.install.id,
        metadata_json={
            "slack_team_id": exchange.team_id,
            "slack_team_name": exchange.team_name,
            "scopes_granted": exchange.bot_scopes_granted,
            "bot_user_id": exchange.bot_user_id,
            "bootstrap": True,
        },
    ))
    db.commit()
    db.refresh(result.user)

    # Mint a session and redirect to /home. The new workspace still needs
    # an Anthropic key + at least one agent before /relay works — the UI
    # shows a setup banner for that.
    token, expires_at = issue_session_token(
        user_id=result.user.id,
        workspace_id=result.user.workspace_id,
    )
    resp = _anon_redirect("/home", slack="installed")
    set_session_cookie(resp, token, expires_at)
    _clear_state_cookie(resp)

    log.info(
        "slack_install.bootstrap_success",
        user_id=str(result.user.id),
        workspace_id=str(result.workspace.id),
        slack_team_id=exchange.team_id,
    )
    return resp
