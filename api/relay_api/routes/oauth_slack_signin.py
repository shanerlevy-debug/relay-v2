"""Sign in with Slack — OIDC routes.

GET /api/oauth/slack-signin/start
  Optional query: invite_token=<raw_token>
  Behavior:
    - If a session cookie is present → link mode (the logged-in user's
      Relay row will be bound to whatever Slack identity comes back).
    - Elif invite_token present → onboard mode (invite consumed at
      callback, new user created bound to the invite's workspace).
    - Else → plain sign-in (existing user by team+user or email match).

GET /api/oauth/slack-signin/callback
  Three resolution branches as described in /start. Output:
    - On success: session cookie set, redirect to /home (or /home?slack_linked=ok
      in link mode).
    - On failure: redirect to /login?slack_signin=<error_code> with a
      message the UI maps to copy.

Force-migrate enforced: if the Slack identity doesn't match any
existing Relay user and there's no invite, deny with
unregistered_no_invite — admin must invite first.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from relay_api.core.config import settings
from relay_api.core.logging import get_logger
from relay_api.db.models import (
    AuditLog,
    Invite,
    User,
    Workspace,
    WorkspaceSlackInstall,
)
from relay_api.db.session import get_db
from relay_api.services.auth.jwt_tokens import (
    TokenError,
    issue_session_token,
    verify_session_token,
)
from relay_api.services.auth.sessions import COOKIE_NAME, set_session_cookie
from relay_api.services.groups import add_user_to_default_group
from relay_api.services.invites import (
    InviteError,
    count_workspace_seats,
    get_invite_by_raw_token,
)
from relay_api.services.oauth.base import (
    OAUTH_STATE_COOKIE,
    OAuthError,
    deserialize_state,
)
from relay_api.services.oauth.slack_signin import SlackSignInProvider

log = get_logger(__name__)

router = APIRouter(prefix="/api/oauth/slack-signin", tags=["oauth-slack-signin"])


def _redirect_uri() -> str:
    return f"{settings.RELAY_API_PUBLIC_URL.rstrip('/')}/api/oauth/slack-signin/callback"


def _ui_redirect(path: str, **params) -> RedirectResponse:
    base = settings.RELAY_APP_BASE_URL.rstrip("/")
    qs = urlencode(params) if params else ""
    url = f"{base}{path}" + (f"?{qs}" if qs else "")
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _set_state_cookie(response: Response, value: str) -> None:
    domain = settings.RELAY_OAUTH_COOKIE_DOMAIN or None
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=value,
        httponly=True,
        secure=settings.RELAY_ENV != "dev",
        samesite="lax",
        max_age=600,
        domain=domain,
        path="/api/oauth/slack-signin",
    )


def _clear_state_cookie(response: Response) -> None:
    domain = settings.RELAY_OAUTH_COOKIE_DOMAIN or None
    response.delete_cookie(
        key=OAUTH_STATE_COOKIE,
        domain=domain,
        path="/api/oauth/slack-signin",
    )


def _resolve_session_user_id(request: Request) -> uuid.UUID | None:
    """If a valid session cookie is present, return the user_id. Else None.
    Used by /start to detect link-existing-user mode."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = verify_session_token(token)
    except TokenError:
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    try:
        return uuid.UUID(sub)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------


@router.get("/start")
def get_start(
    request: Request,
    invite_token: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Begin Slack OIDC. Public — but extra_state is loaded from the
    session cookie (link mode) or the invite_token query (onboard mode)."""
    extra_state: dict = {}

    # Logged-in link mode
    session_user_id = _resolve_session_user_id(request)
    if session_user_id is not None:
        extra_state["link_to_user_id"] = str(session_user_id)

    # Onboard mode (only honor token if we're NOT also link mode — link
    # wins, since the user is already signed in).
    if not extra_state and invite_token:
        # Validate the token shape upfront so a bad URL fails fast at
        # /start rather than after the Slack round-trip.
        try:
            get_invite_by_raw_token(db, raw_token=invite_token)
        except InviteError as e:
            return _ui_redirect("/login", slack_signin="invite_bad", code=e.code)
        extra_state["invite_token"] = invite_token

    provider = SlackSignInProvider()
    try:
        result = provider.start_signin(
            redirect_uri=_redirect_uri(),
            extra_state=extra_state,
        )
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
    if error:
        resp = _ui_redirect("/login", slack_signin="error", code=f"slack_{error}")
        _clear_state_cookie(resp)
        return resp
    if not code or not state:
        resp = _ui_redirect("/login", slack_signin="error", code="missing_params")
        _clear_state_cookie(resp)
        return resp

    state_cookie_value = request.cookies.get(OAUTH_STATE_COOKIE)
    if not state_cookie_value:
        return _ui_redirect("/login", slack_signin="error", code="no_state_cookie")

    try:
        state_payload = deserialize_state(state_cookie_value)
    except OAuthError:
        resp = _ui_redirect("/login", slack_signin="error", code="bad_state")
        _clear_state_cookie(resp)
        return resp

    if state_payload.get("nonce") != state:
        resp = _ui_redirect("/login", slack_signin="error", code="state_mismatch")
        _clear_state_cookie(resp)
        return resp

    # Exchange code → Slack identity
    provider = SlackSignInProvider()
    try:
        identity = await provider.exchange_code(
            code=code, redirect_uri=_redirect_uri(),
        )
    except OAuthError as e:
        resp = _ui_redirect("/login", slack_signin="error", code=e.code)
        _clear_state_cookie(resp)
        return resp

    # Find the Relay workspace this Slack team is installed on. If none,
    # the user's Slack team hasn't installed Relay — direct them to do
    # Add-to-Slack first.
    install = db.execute(
        select(WorkspaceSlackInstall)
        .where(WorkspaceSlackInstall.slack_team_id == identity.team_id)
        .where(WorkspaceSlackInstall.revoked_at.is_(None))
    ).scalar_one_or_none()
    if install is None:
        resp = _ui_redirect("/login", slack_signin="team_not_installed")
        _clear_state_cookie(resp)
        return resp
    workspace = db.get(Workspace, install.workspace_id)
    if workspace is None or workspace.archived_at is not None:
        resp = _ui_redirect("/login", slack_signin="team_not_installed")
        _clear_state_cookie(resp)
        return resp

    # Dispatch on state flavor
    link_to_user_id_raw = state_payload.get("link_to_user_id")
    invite_token = state_payload.get("invite_token")

    try:
        if link_to_user_id_raw:
            user = _handle_link_mode(
                db,
                identity=identity,
                workspace=workspace,
                link_to_user_id=uuid.UUID(str(link_to_user_id_raw)),
            )
            redirect_path = "/home"
            redirect_params = {"slack_linked": "ok"}
            event_type = "user.linked_slack_identity"
        elif invite_token:
            user = _handle_invite_mode(
                db,
                identity=identity,
                workspace=workspace,
                invite_token=invite_token,
            )
            redirect_path = "/home"
            redirect_params = {"slack_signin": "welcome"}
            event_type = "user.created_via_slack_signin"
        else:
            user = _handle_plain_signin(
                db, identity=identity, workspace=workspace,
            )
            redirect_path = "/home"
            redirect_params = {}
            event_type = "user.logged_in_via_slack_signin"
    except _SignInError as e:
        log.info("slack_signin.denied", code=e.code, team_id=identity.team_id)
        resp = _ui_redirect("/login", slack_signin=e.code)
        _clear_state_cookie(resp)
        return resp

    # Audit row
    db.add(AuditLog(
        workspace_id=user.workspace_id,
        actor_user_id=user.id,
        event_type=event_type,
        subject_type="user",
        subject_id=user.id,
        metadata_json={
            "email": user.email,
            "slack_team_id": identity.team_id,
            "slack_user_id": identity.user_id,
        },
    ))
    db.commit()
    db.refresh(user)

    # Issue session + redirect
    token, expires_at = issue_session_token(
        user_id=user.id, workspace_id=user.workspace_id,
    )
    resp = _ui_redirect(redirect_path, **redirect_params)
    set_session_cookie(resp, token, expires_at)
    _clear_state_cookie(resp)
    log.info(
        "slack_signin.success",
        mode=event_type,
        user_id=str(user.id),
        workspace_id=str(user.workspace_id),
    )
    return resp


# ---------------------------------------------------------------------------
# Mode handlers — raise _SignInError with a UI code on failure.
# ---------------------------------------------------------------------------


class _SignInError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _now() -> datetime:
    return datetime.now(UTC)


def _handle_link_mode(
    db: Session,
    *,
    identity,
    workspace: Workspace,
    link_to_user_id: uuid.UUID,
) -> User:
    """Bind the Slack identity to the currently-signed-in user's row.
    Safe-by-default: refuses to link if the Slack team doesn't match the
    target user's workspace."""
    user = db.get(User, link_to_user_id)
    if user is None or user.deleted_at is not None:
        raise _SignInError("link_user_missing")
    if user.workspace_id != workspace.id:
        # User signed into Slack with a different team than their Relay
        # workspace is bound to. Reject — we don't want cross-workspace
        # link confusion.
        raise _SignInError("link_team_mismatch")

    # If someone ELSE already claimed this slack_user_id in this
    # workspace, refuse rather than steal the binding.
    existing = db.execute(
        select(User)
        .where(User.workspace_id == workspace.id)
        .where(User.slack_user_id == identity.user_id)
        .where(User.deleted_at.is_(None))
        .where(User.id != user.id)
    ).scalar_one_or_none()
    if existing is not None:
        raise _SignInError("slack_user_already_claimed")

    user.slack_user_id = identity.user_id
    user.slack_user_verified_at = _now()
    db.flush()
    return user


def _handle_invite_mode(
    db: Session,
    *,
    identity,
    workspace: Workspace,
    invite_token: str,
) -> User:
    """Consume the invite, create-or-link a User bound to the Slack
    identity. Trust Slack's email — the invite email is only the
    delivery address, the Slack identity is the source of truth."""
    try:
        invite = get_invite_by_raw_token(db, raw_token=invite_token)
    except InviteError:
        raise _SignInError("invite_bad")

    if invite.workspace_id != workspace.id:
        # Invite is for a different workspace than the Slack team is
        # connected to. Probably the admin shared a wrong link.
        raise _SignInError("invite_team_mismatch")

    # Already-linked-this-slack-user check (idempotent re-click)
    existing = db.execute(
        select(User)
        .where(User.workspace_id == workspace.id)
        .where(User.slack_user_id == identity.user_id)
        .where(User.deleted_at.is_(None))
    ).scalar_one_or_none()
    if existing is not None:
        # User already exists — consume the invite as a no-op, log them in.
        invite.accepted_at = _now()
        invite.accepted_by_user_id = existing.id
        db.flush()
        return existing

    # Email-match check (might be an old email/password user who never
    # got a Slack binding — link rather than create a duplicate).
    by_email = db.execute(
        select(User)
        .where(User.workspace_id == workspace.id)
        .where(func.lower(User.email) == identity.email)
        .where(User.deleted_at.is_(None))
    ).scalar_one_or_none()
    if by_email is not None:
        by_email.slack_user_id = identity.user_id
        by_email.slack_user_verified_at = _now()
        invite.accepted_at = _now()
        invite.accepted_by_user_id = by_email.id
        db.flush()
        return by_email

    # Genuinely new user. Cap check (re-check at consume time).
    active, pending = count_workspace_seats(db, workspace_id=workspace.id)
    cap = settings.RELAY_USERS_PER_WORKSPACE
    if active + max(0, pending - 1) >= cap:
        raise _SignInError("user_limit_reached")

    user = User(
        workspace_id=workspace.id,
        email=identity.email,
        password_hash=None,  # no password — they use Slack to sign in
        role=invite.role,
        email_verified_at=_now(),
        slack_user_id=identity.user_id,
        slack_user_verified_at=_now(),
    )
    db.add(user)
    db.flush()
    add_user_to_default_group(db, user=user)

    invite.accepted_at = _now()
    invite.accepted_by_user_id = user.id
    db.flush()
    return user


def _handle_plain_signin(
    db: Session, *, identity, workspace: Workspace,
) -> User:
    """No session, no invite. Find an existing user — by slack_user_id or
    by email. If neither exists, refuse (force-migrate: admin must invite
    first; no self-serve registration)."""
    by_slack = db.execute(
        select(User)
        .where(User.workspace_id == workspace.id)
        .where(User.slack_user_id == identity.user_id)
        .where(User.deleted_at.is_(None))
    ).scalar_one_or_none()
    if by_slack is not None:
        # First sign-in via OIDC after an Add-to-Slack-bootstrap binding
        # — stamp the verified-at marker if it wasn't already there.
        if by_slack.slack_user_verified_at is None:
            by_slack.slack_user_verified_at = _now()
            db.flush()
        return by_slack

    by_email = db.execute(
        select(User)
        .where(User.workspace_id == workspace.id)
        .where(func.lower(User.email) == identity.email)
        .where(User.deleted_at.is_(None))
    ).scalar_one_or_none()
    if by_email is not None:
        by_email.slack_user_id = identity.user_id
        by_email.slack_user_verified_at = _now()
        db.flush()
        return by_email

    # Force-migrate: no self-serve registration. Admin must invite first.
    raise _SignInError("unregistered_no_invite")
