"""User-management + invite-flow schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from relay_api.schemas.auth import _normalize_email  # reuse the .test-friendly validator


class InviteCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: Literal["admin", "member"] = "member"

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str) -> str:
        return _normalize_email(v)


class AcceptInviteRequest(BaseModel):
    password: str = Field(min_length=12, max_length=128)


class InviteOut(BaseModel):
    """Returned to admins listing pending invites. NEVER includes token_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: Literal["admin", "member"]
    expires_at: datetime
    created_at: datetime
    created_by_user_id: uuid.UUID | None


class InvitePublicOut(BaseModel):
    """Returned to the unauthenticated invitee at GET /api/invites/{token}.

    Reveals the workspace name + invited email so the accept-invite page
    can render "You're invited to join Acme as a member" — but nothing
    else about the workspace.
    """

    email: str
    role: Literal["admin", "member"]
    workspace_display_name: str
    expires_at: datetime


class UserListItem(BaseModel):
    """Public-facing user-list shape. NEVER includes password_hash or
    workspace_id (implicit from the request)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: Literal["admin", "member"]
    email_verified_at: datetime | None
    created_at: datetime


class WorkspaceSeatsOut(BaseModel):
    """Returned alongside the user list so the UI can render the
    `8 / 25 users` counter without a second round trip."""

    active: int
    pending_invites: int
    cap: int
