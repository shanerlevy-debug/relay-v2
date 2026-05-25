"""Workspace user management — list, invite, remove.

All mutations are admin-only. The 25-user cap is enforced at invite-create
time AND re-checked at accept time (the world can change between).

The invite-create response carries the raw `invite_url` so the admin can
either share it manually OR rely on the (week-3) email integration to send
it. In dev the URL is also logged to stdout — never lose your test invite.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from relay_api.core.config import settings
from relay_api.core.dependencies import current_user, current_workspace, require_admin
from relay_api.core.logging import get_logger
from relay_api.db.models import AuditLog, Invite, User, Workspace
from relay_api.db.session import get_db
from relay_api.schemas.users import (
    InviteCreateRequest,
    InviteOut,
    UserListItem,
    WorkspaceSeatsOut,
)
from relay_api.services.email import EmailError, EmailMessage, render_invite_email, send
from relay_api.services.invites import (
    InviteError,
    count_workspace_seats,
    create_invite,
    list_pending_invites,
)
from relay_api.services.user_mgmt import UserMgmtError, delete_user, list_workspace_users

log = get_logger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])

# Companion router for invites — admins manage them under /api/users/...
# but invitees hit the public /api/invites/{token} surface (see routes/invites.py).


@router.get("")
def get_users(
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    """List active users + pending invites + seat counts."""
    users = list_workspace_users(db, workspace_id=workspace.id)
    invites = list_pending_invites(db, workspace_id=workspace.id)
    active, pending = count_workspace_seats(db, workspace_id=workspace.id)
    return {
        "users": [UserListItem.model_validate(u) for u in users],
        "pending_invites": [InviteOut.model_validate(i) for i in invites],
        "seats": WorkspaceSeatsOut(
            active=active,
            pending_invites=pending,
            cap=settings.RELAY_USERS_PER_WORKSPACE,
        ),
    }


@router.post("/invite", status_code=status.HTTP_201_CREATED)
def post_invite(
    req: InviteCreateRequest,
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    """Admin invites a teammate. Returns the invite row + the raw URL.

    In dev: the URL also prints to stdout (look for `invite.created` in logs).
    In prod (week 3+): the URL ALSO gets emailed via Resend.
    """
    try:
        invite, raw_token = create_invite(
            db,
            workspace_id=workspace.id,
            invited_by_user_id=admin.id,
            email=req.email,
            role=req.role,
        )
    except InviteError as e:
        # user_limit_reached + email_in_use + invite_already_pending → 409
        # weak validation failures → 400
        conflict_codes = {"user_limit_reached", "email_in_use", "invite_already_pending"}
        status_code = 409 if e.code in conflict_codes else 400
        raise HTTPException(
            status_code=status_code,
            detail={"code": e.code, "message": str(e)},
        ) from e

    db.add(AuditLog(
        workspace_id=workspace.id,
        actor_user_id=admin.id,
        event_type="user.invited",
        subject_type="invite",
        subject_id=invite.id,
        metadata_json={"email": invite.email, "role": invite.role},
    ))
    db.commit()
    db.refresh(invite)

    # The invite URL drives Slack OIDC, with the raw token in the query
    # so the callback can consume the invite + create the linked user.
    invite_url = (
        f"{settings.RELAY_API_PUBLIC_URL.rstrip('/')}"
        f"/api/oauth/slack-signin/start?invite_token={raw_token}"
    )
    log.info(
        "invite.created",
        invite_id=str(invite.id),
        email=invite.email,
        invite_url=invite_url,
    )

    # Best-effort email send. If the email provider fails (no API key,
    # network error, bad domain), surface the URL to the admin so they
    # can share manually — don't roll back the invite.
    email_sent = False
    try:
        html, text = render_invite_email(
            workspace_name=workspace.display_name,
            invite_url=invite_url,
            inviter_email=admin.email,
        )
        send(EmailMessage(
            to=invite.email,
            subject=f"You're invited to {workspace.display_name} on Relay",
            html=html,
            text=text,
        ))
        email_sent = True
    except EmailError as e:
        log.warning(
            "invite.email_send_failed",
            invite_id=str(invite.id),
            error=str(e),
        )

    return {
        "invite": InviteOut.model_validate(invite),
        "invite_url": invite_url,
        "email_sent": email_sent,
    }


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_route(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> None:
    """Soft-delete a workspace user. 404 if cross-workspace; 409 if
    self-delete or last-admin."""
    try:
        target = delete_user(
            db,
            workspace_id=workspace.id,
            user_id=user_id,
            actor_user_id=admin.id,
        )
    except UserMgmtError as e:
        status_code = {
            "not_found": 404,
            "self_delete": 409,
            "last_admin": 409,
        }.get(e.code, 400)
        raise HTTPException(
            status_code=status_code,
            detail={"code": e.code, "message": str(e)},
        ) from e

    db.add(AuditLog(
        workspace_id=workspace.id,
        actor_user_id=admin.id,
        event_type="user.removed",
        subject_type="user",
        subject_id=target.id,
        metadata_json={"email": target.email, "role": target.role},
    ))
    db.commit()
    return None
