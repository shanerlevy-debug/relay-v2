"""Workspace invite flow.

create_invite     admin invites teammate by email — counts toward 25-user cap
get_invite        public lookup by raw token (for the accept-invite page)
accept_invite     creates a User from a valid pending invite + a password
revoke_invite     admin pulls a not-yet-accepted invite

The 25-user cap is enforced as `active_users + pending_invites <= 25`. A
pending invite that's about to be accepted will become a user; counting
it toward the cap stops admins from over-inviting in anticipation of
attrition.
"""
from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from relay_api.core.config import settings
from relay_api.db.models import Invite, User
from relay_api.services.auth import tokens
from relay_api.services.auth.passwords import hash_password

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_PASSWORD_LEN = 12


class InviteError(Exception):
    """Expected failures in the invite flow. `code` for UI branching."""

    def __init__(self, message: str, *, code: str = "invalid"):
        super().__init__(message)
        self.code = code


def _now() -> datetime:
    return datetime.now(UTC)


def count_workspace_seats(db: Session, *, workspace_id: uuid.UUID) -> tuple[int, int]:
    """Return (active_users, pending_invites) for the cap calculation."""
    active = db.execute(
        select(func.count(User.id))
        .where(User.workspace_id == workspace_id)
        .where(User.deleted_at.is_(None))
    ).scalar_one()

    pending = db.execute(
        select(func.count(Invite.id))
        .where(Invite.workspace_id == workspace_id)
        .where(Invite.accepted_at.is_(None))
        .where(Invite.expires_at > _now())
    ).scalar_one()

    return int(active), int(pending)


def list_pending_invites(db: Session, *, workspace_id: uuid.UUID) -> list[Invite]:
    """Active invites for the workspace — not yet accepted, not expired.
    Oldest first so admins see the longest-outstanding ones at the top."""
    return list(
        db.execute(
            select(Invite)
            .where(Invite.workspace_id == workspace_id)
            .where(Invite.accepted_at.is_(None))
            .where(Invite.expires_at > _now())
            .order_by(Invite.created_at)
        ).scalars()
    )


def create_invite(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    invited_by_user_id: uuid.UUID,
    email: str,
    role: str = "member",
    ttl: timedelta | None = None,
) -> tuple[Invite, str]:
    """Create an invite row. Returns (invite_row, raw_token_for_email).

    The raw token is what gets emailed; it's NEVER stored. Caller (route) is
    responsible for sending the actual email (or printing to console in dev).
    """
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise InviteError("invalid email format", code="invalid_email")
    if role not in ("admin", "member"):
        raise InviteError("role must be 'admin' or 'member'", code="invalid_role")

    # Cap check — active users + outstanding (non-expired, non-accepted) invites.
    active, pending = count_workspace_seats(db, workspace_id=workspace_id)
    cap = settings.RELAY_USERS_PER_WORKSPACE
    if active + pending >= cap:
        raise InviteError(
            f"workspace is at the {cap}-user limit (Enterprise unlocks more)",
            code="user_limit_reached",
        )

    # Reject if the email is already an active user anywhere in this Relay
    # deployment. v1 invariant: one email per Relay (matches signup.py).
    existing = db.execute(
        select(User.id)
        .where(func.lower(User.email) == email)
        .where(User.deleted_at.is_(None))
    ).first()
    if existing is not None:
        raise InviteError(
            "this email is already registered with a Relay account",
            code="email_in_use",
        )

    # Reject if there's already an outstanding invite for this email in this
    # workspace. (Different workspaces with the same email is its own error
    # at accept time, when the User row creation would collide.)
    pending_for_email = db.execute(
        select(Invite.id)
        .where(Invite.workspace_id == workspace_id)
        .where(func.lower(Invite.email) == email)
        .where(Invite.accepted_at.is_(None))
        .where(Invite.expires_at > _now())
    ).first()
    if pending_for_email is not None:
        raise InviteError(
            "this email already has a pending invite — revoke it first to re-send",
            code="invite_already_pending",
        )

    raw_token, token_hash = tokens.mint_token()
    invite = Invite(
        workspace_id=workspace_id,
        email=email,
        role=role,
        token_hash=token_hash,
        expires_at=tokens.expires_at(ttl or tokens.INVITE_TTL),
        created_by_user_id=invited_by_user_id,
    )
    db.add(invite)
    db.flush()

    return invite, raw_token


def get_invite_by_raw_token(db: Session, *, raw_token: str) -> Invite:
    """Lookup invite by the raw token (from the URL). Raises InviteError
    on unknown / expired / accepted invites.
    """
    if not raw_token:
        raise InviteError("token required", code="missing_token")
    token_hash = tokens.hash_token(raw_token)
    invite = db.execute(
        select(Invite).where(Invite.token_hash == token_hash)
    ).scalar_one_or_none()
    if invite is None:
        raise InviteError("invite not found", code="not_found")
    if invite.accepted_at is not None:
        raise InviteError("invite already accepted", code="already_accepted")
    if tokens.is_expired(invite.expires_at):
        raise InviteError("invite has expired", code="expired")
    return invite


def accept_invite(
    db: Session,
    *,
    invite: Invite,
    password: str,
) -> User:
    """Consume an invite: create the User, mark invite accepted, return User.

    Caller commits. Caller has already validated the invite via
    `get_invite_by_raw_token`.
    """
    if len(password) < _MIN_PASSWORD_LEN:
        raise InviteError(
            f"password must be at least {_MIN_PASSWORD_LEN} characters",
            code="weak_password",
        )

    # Cap re-check at accept time — the world could have changed between
    # invite creation and acceptance.
    active, pending = count_workspace_seats(db, workspace_id=invite.workspace_id)
    cap = settings.RELAY_USERS_PER_WORKSPACE
    # This invite is one of the "pending" — exclude it from the count.
    if active + max(0, pending - 1) >= cap:
        raise InviteError(
            f"workspace is at the {cap}-user limit",
            code="user_limit_reached",
        )

    # Reject if a User already exists for this email globally — same
    # invariant as signup.
    existing = db.execute(
        select(User.id)
        .where(func.lower(User.email) == invite.email)
        .where(User.deleted_at.is_(None))
    ).first()
    if existing is not None:
        raise InviteError(
            "this email is already registered with a Relay account",
            code="email_in_use",
        )

    user = User(
        workspace_id=invite.workspace_id,
        email=invite.email,
        password_hash=hash_password(password),
        role=invite.role,
        email_verified_at=_now(),  # accepting the invite proves mailbox ownership
    )
    db.add(user)
    db.flush()

    invite.accepted_at = _now()
    invite.accepted_by_user_id = user.id
    db.flush()

    return user


def revoke_invite(db: Session, *, invite: Invite) -> None:
    """Admin-side cancellation. We just expire it — same effect, no extra
    column needed.
    """
    if invite.accepted_at is not None:
        # Can't revoke an already-accepted invite. Removing the user is
        # a separate operation (user_mgmt.delete_user).
        return
    invite.expires_at = _now()
    db.flush()
