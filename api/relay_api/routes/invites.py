"""Public invite endpoints — invitee hits these to view + accept.

GET  /api/invites/{token}        view invite details (workspace name, email, role)
POST /api/invites/{token}/accept create the User account, log them in via cookie

Both endpoints are unauthenticated — the invite token IS the authentication
material. Single-use: the token-hash unique index + accepted_at stamp
prevents replay.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from relay_api.db.models import AuditLog, Workspace
from relay_api.db.session import get_db
from relay_api.schemas.auth import SessionOut, UserOut, WorkspaceOut
from relay_api.schemas.users import AcceptInviteRequest, InvitePublicOut
from relay_api.services.auth.jwt_tokens import issue_session_token
from relay_api.services.auth.sessions import set_session_cookie
from relay_api.services.invites import (
    InviteError,
    accept_invite,
    get_invite_by_raw_token,
)

router = APIRouter(prefix="/api/invites", tags=["invites"])


def _invite_error_to_http(e: InviteError) -> HTTPException:
    """Common mapping for invite-flow failures."""
    status_code = {
        "not_found": 404,
        "expired": 410,
        "already_accepted": 410,
        "missing_token": 400,
    }.get(e.code, 400)
    return HTTPException(
        status_code=status_code,
        detail={"code": e.code, "message": str(e)},
    )


@router.get("/{token}")
def get_invite(
    token: str,
    db: Session = Depends(get_db),
) -> InvitePublicOut:
    """View invite details. Returns the workspace name + invitee email + role
    so the accept-invite page can render 'You're invited to join Acme as a
    member.' Reveals nothing else about the workspace."""
    try:
        invite = get_invite_by_raw_token(db, raw_token=token)
    except InviteError as e:
        raise _invite_error_to_http(e) from e

    workspace = db.get(Workspace, invite.workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "invite not found"},
        )

    return InvitePublicOut(
        email=invite.email,
        role=invite.role,
        workspace_display_name=workspace.display_name,
        expires_at=invite.expires_at,
    )


@router.post("/{token}/accept")
def post_accept(
    token: str,
    req: AcceptInviteRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionOut:
    """Accept an invite: create the User, mark invite consumed, set session cookie.

    Caller is now logged in as the new user (same as freshly-signed-up).
    """
    try:
        invite = get_invite_by_raw_token(db, raw_token=token)
    except InviteError as e:
        raise _invite_error_to_http(e) from e

    try:
        user = accept_invite(db, invite=invite, password=req.password)
    except InviteError as e:
        # weak_password + email_in_use + user_limit_reached land here
        status_code = {
            "weak_password": 400,
            "email_in_use": 409,
            "user_limit_reached": 409,
        }.get(e.code, 400)
        raise HTTPException(
            status_code=status_code,
            detail={"code": e.code, "message": str(e)},
        ) from e

    workspace = db.get(Workspace, user.workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "workspace_missing",
                "message": "user's workspace not found",
            },
        )

    db.add(AuditLog(
        workspace_id=workspace.id,
        actor_user_id=user.id,
        event_type="user.created_via_invite",
        subject_type="user",
        subject_id=user.id,
        metadata_json={"email": user.email, "role": user.role},
    ))
    db.commit()

    token_jwt, expires_at = issue_session_token(
        user_id=user.id,
        workspace_id=user.workspace_id,
    )
    set_session_cookie(response, token_jwt, expires_at)

    return SessionOut(
        user=UserOut.model_validate(user),
        workspace=WorkspaceOut.model_validate(workspace),
    )
