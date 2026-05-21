"""Signup + login services.

Signup creates a brand-new tenant: one Workspace + one admin User, both
in a single transaction. v1 has no email verification — receipt of an
invite email is verification enough when present (week 1 day 5+); signup
without invite is open and trusts the email until something breaks.

Login finds the user by case-insensitive email across all workspaces.
v1's implicit invariant is "one email per Relay deployment"; enforced
at the application layer (a SELECT before the INSERT in signup).
"""
from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from relay_api.db.models import User, Workspace
from relay_api.services.auth.passwords import (
    InvalidPassword,
    hash_password,
    verify_password,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_PASSWORD_LEN = 12


class SignupError(Exception):
    """Expected signup/login failures. The `code` field is what the UI
    branches on; the message is human-readable."""

    def __init__(self, message: str, *, code: str = "invalid"):
        super().__init__(message)
        self.code = code


def signup(
    db: Session,
    *,
    email: str,
    password: str,
    workspace_name: str,
) -> tuple[Workspace, User]:
    """Create workspace + admin user atomically. Caller commits.

    Raises SignupError on validation or uniqueness failures.
    """
    email = email.strip().lower()
    workspace_name = workspace_name.strip()

    if not _EMAIL_RE.match(email):
        raise SignupError("invalid email format", code="invalid_email")
    if len(password) < _MIN_PASSWORD_LEN:
        raise SignupError(
            f"password must be at least {_MIN_PASSWORD_LEN} characters",
            code="weak_password",
        )
    if not workspace_name:
        raise SignupError("workspace name cannot be empty", code="invalid_workspace_name")

    # Application-level email uniqueness across all workspaces. v1
    # invariant: one email per Relay deployment. The race window between
    # this SELECT and the INSERT below is tiny (<10ms typical); if two
    # signups for the same email collide there, the second one's caller
    # gets a 500 instead of a 409 — acceptable for v1. Tighten later with
    # a global partial unique index.
    existing = db.execute(
        select(User.id)
        .where(func.lower(User.email) == email)
        .where(User.deleted_at.is_(None))
    ).first()
    if existing is not None:
        raise SignupError("email already in use", code="email_in_use")

    workspace = Workspace(display_name=workspace_name)
    db.add(workspace)
    db.flush()

    user = User(
        workspace_id=workspace.id,
        email=email,
        password_hash=hash_password(password),
        role="admin",
    )
    db.add(user)
    db.flush()

    return workspace, user


def authenticate(
    db: Session,
    *,
    email: str,
    password: str,
) -> User:
    """Find the user by email, verify the password, return the User.

    Raises SignupError on bad credentials — same shape for "no user" and
    "wrong password" so an attacker can't probe which emails are
    registered.
    """
    email = email.strip().lower()
    user = db.execute(
        select(User)
        .where(func.lower(User.email) == email)
        .where(User.deleted_at.is_(None))
    ).scalar_one_or_none()

    if user is None or user.password_hash is None:
        raise SignupError("invalid credentials", code="invalid_credentials")

    try:
        verify_password(password, hashed=user.password_hash)
    except InvalidPassword as e:
        raise SignupError("invalid credentials", code="invalid_credentials") from e

    return user
