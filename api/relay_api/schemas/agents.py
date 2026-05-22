"""Agent CRUD schemas."""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_EMOJI_RE = re.compile(r"^:[a-z0-9_+\-]+:$")


def _validate_slug(value: str) -> str:
    value = value.strip().lower()
    if not _SLUG_RE.match(value):
        raise ValueError(
            "slug must start with a letter and contain only lowercase letters, "
            "digits, and hyphens"
        )
    return value


def _validate_display_name(value: str | None) -> str | None:
    """Slack username override. ≤30 chars (Slack's practical ceiling),
    trimmed, no surrounding whitespace. Empty string normalizes to None."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > 30:
        raise ValueError("display name must be 30 characters or fewer")
    return value


def _validate_icon_url(value: str | None) -> str | None:
    """Accepts either an `:emoji:` token or an `https://...` URL. Anything
    else (`http://`, `data:`, etc.) is rejected — Slack requires HTTPS for
    icon URLs and we don't want to host non-image URLs by accident."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if _EMOJI_RE.match(value):
        return value
    if value.startswith("https://") and len(value) <= 1024:
        return value
    raise ValueError(
        "icon must be either an :emoji: code or an https:// URL"
    )


class AgentCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    anthropic_agent_id: str = Field(min_length=1, max_length=64)
    environment_id: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=1024)
    is_default: bool = False
    slack_display_name: str | None = Field(default=None, max_length=30)
    slack_icon_url: str | None = Field(default=None, max_length=1024)

    @field_validator("slug")
    @classmethod
    def _v_slug(cls, v: str) -> str:
        return _validate_slug(v)

    @field_validator("slack_display_name")
    @classmethod
    def _v_display_name(cls, v: str | None) -> str | None:
        return _validate_display_name(v)

    @field_validator("slack_icon_url")
    @classmethod
    def _v_icon_url(cls, v: str | None) -> str | None:
        return _validate_icon_url(v)


class AgentUpdateRequest(BaseModel):
    """Every field is optional — PATCH semantics. Send only what changes."""

    slug: str | None = Field(default=None, min_length=1, max_length=64)
    anthropic_agent_id: str | None = Field(default=None, min_length=1, max_length=64)
    environment_id: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=1024)
    is_default: bool | None = None
    slack_display_name: str | None = Field(default=None, max_length=30)
    slack_icon_url: str | None = Field(default=None, max_length=1024)

    @field_validator("slug")
    @classmethod
    def _v_slug(cls, v: str | None) -> str | None:
        return _validate_slug(v) if v is not None else None

    @field_validator("slack_display_name")
    @classmethod
    def _v_display_name(cls, v: str | None) -> str | None:
        return _validate_display_name(v)

    @field_validator("slack_icon_url")
    @classmethod
    def _v_icon_url(cls, v: str | None) -> str | None:
        return _validate_icon_url(v)


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    slug: str
    anthropic_agent_id: str
    environment_id: str
    description: str | None
    is_default: bool
    slack_display_name: str | None
    slack_icon_url: str | None
    created_at: datetime
    archived_at: datetime | None


class AgentSeatsOut(BaseModel):
    """For the UI's `Agents: 4 / 25` counter."""

    active: int
    cap: int


class AgentListOut(BaseModel):
    agents: list[AgentOut]
    seats: AgentSeatsOut
