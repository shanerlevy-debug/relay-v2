"""Reusable FastAPI dependencies — current_user, current_workspace, require_admin.

These are the auth boundary. Every authenticated route declares
`user: User = Depends(current_user)` to require a session, and
`require_admin` is the gate for workspace-admin-only routes.
"""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from relay_api.db.models import User, Workspace
from relay_api.db.session import get_db
from relay_api.services.auth.jwt_tokens import TokenError, verify_session_token
from relay_api.services.auth.sessions import COOKIE_NAME


def _not_authenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "not_authenticated", "message": "session required"},
    )


def current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Decode the session cookie and return the User. Raises 401 for any
    of: no cookie, invalid/expired/tampered token, deleted user.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise _not_authenticated()
    try:
        payload = verify_session_token(token)
    except TokenError as e:
        raise _not_authenticated() from e

    user_id_raw = payload.get("sub")
    if not user_id_raw:
        raise _not_authenticated()
    try:
        user_id = uuid.UUID(user_id_raw)
    except ValueError as e:
        raise _not_authenticated() from e

    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise _not_authenticated()
    return user


def current_workspace(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Workspace:
    """Return the user's workspace, ensuring it's not archived."""
    workspace = db.get(Workspace, user.workspace_id)
    if workspace is None or workspace.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "workspace_unavailable",
                "message": "workspace not active",
            },
        )
    return workspace


def require_admin(user: User = Depends(current_user)) -> User:
    """Gate routes that should only respond to workspace admins."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "admin_required", "message": "admin role required"},
        )
    return user
