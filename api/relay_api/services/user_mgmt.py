"""User-list + soft-delete operations.

Soft-delete (`deleted_at` stamp) rather than DELETE — preserves audit log
references and the email-uniqueness check (which already excludes deleted
rows).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from relay_api.db.models import User


class UserMgmtError(Exception):
    def __init__(self, message: str, *, code: str = "invalid"):
        super().__init__(message)
        self.code = code


def list_workspace_users(
    db: Session,
    *,
    workspace_id: uuid.UUID,
) -> list[User]:
    """All active users in the workspace, oldest-first."""
    return list(
        db.execute(
            select(User)
            .where(User.workspace_id == workspace_id)
            .where(User.deleted_at.is_(None))
            .order_by(User.created_at)
        ).scalars()
    )


def delete_user(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> User:
    """Soft-delete a user. Raises UserMgmtError on policy violations:
        - user not in this workspace
        - user is the last admin (can't orphan the workspace)
        - user is deleting themselves (use /api/auth/logout, not this)
    """
    if user_id == actor_user_id:
        raise UserMgmtError(
            "you can't remove yourself — log out instead",
            code="self_delete",
        )

    target = db.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise UserMgmtError("user not found", code="not_found")
    if target.workspace_id != workspace_id:
        # Cross-workspace lookup — never confirm the user exists in a
        # different tenant. Same 404 as not-found.
        raise UserMgmtError("user not found", code="not_found")

    # Last-admin guard.
    if target.role == "admin":
        remaining_admins = (
            db.execute(
                select(User)
                .where(User.workspace_id == workspace_id)
                .where(User.role == "admin")
                .where(User.deleted_at.is_(None))
                .where(User.id != user_id)
            ).scalars().first()
        )
        if remaining_admins is None:
            raise UserMgmtError(
                "can't remove the last admin — promote another user first",
                code="last_admin",
            )

    target.deleted_at = datetime.now(UTC)
    db.flush()
    return target
