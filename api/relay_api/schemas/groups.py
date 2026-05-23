"""Group CRUD + membership schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    is_default: bool
    created_at: datetime
    archived_at: datetime | None


class GroupSummary(BaseModel):
    """Compact form for the membership chips on /agents and /users rows."""

    id: uuid.UUID
    name: str
    is_default: bool


class GroupCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class GroupRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class GroupMembersOut(BaseModel):
    """Detail view — who and what is in a group."""

    group: GroupOut
    users: list["GroupMemberUser"]
    agents: list["GroupMemberAgent"]


class GroupMemberUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str


class GroupMemberAgent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    slack_display_name: str | None
    slack_icon_url: str | None


class GroupListOut(BaseModel):
    groups: list[GroupOut]


class GroupMembershipMap(BaseModel):
    """Batch lookup for chip rendering on /agents and /users.
    Keys are UUID strings (frontend stores ids as strings)."""

    users: dict[str, list[GroupSummary]]
    agents: dict[str, list[GroupSummary]]


class GroupMembershipMutateRequest(BaseModel):
    """Body for POST /api/groups/{id}/users/{user_id} +
    POST /api/groups/{id}/agents/{agent_id} — no fields, just a marker."""


GroupMembersOut.model_rebuild()
