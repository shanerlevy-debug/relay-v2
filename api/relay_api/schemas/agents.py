"""Agent CRUD schemas."""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def _validate_slug(value: str) -> str:
    value = value.strip().lower()
    if not _SLUG_RE.match(value):
        raise ValueError(
            "slug must start with a letter and contain only lowercase letters, "
            "digits, and hyphens"
        )
    return value


class AgentCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    anthropic_agent_id: str = Field(min_length=1, max_length=64)
    environment_id: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=1024)
    is_default: bool = False

    @field_validator("slug")
    @classmethod
    def _v_slug(cls, v: str) -> str:
        return _validate_slug(v)


class AgentUpdateRequest(BaseModel):
    """Every field is optional — PATCH semantics. Send only what changes."""

    slug: str | None = Field(default=None, min_length=1, max_length=64)
    anthropic_agent_id: str | None = Field(default=None, min_length=1, max_length=64)
    environment_id: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=1024)
    is_default: bool | None = None

    @field_validator("slug")
    @classmethod
    def _v_slug(cls, v: str | None) -> str | None:
        return _validate_slug(v) if v is not None else None


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    slug: str
    anthropic_agent_id: str
    environment_id: str
    description: str | None
    is_default: bool
    created_at: datetime
    archived_at: datetime | None


class AgentSeatsOut(BaseModel):
    """For the UI's `Agents: 4 / 25` counter."""

    active: int
    cap: int


class AgentListOut(BaseModel):
    agents: list[AgentOut]
    seats: AgentSeatsOut
