"""BYO Anthropic key schemas — never expose plaintext from the API."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnthropicKeySetRequest(BaseModel):
    """Admin sets / replaces the workspace's Anthropic key."""

    key: str = Field(min_length=10, max_length=512)


class AnthropicKeyStatusOut(BaseModel):
    """Returned by GET /api/workspace/anthropic-key.

    Tells the UI whether a key is configured + when it was set, so the
    page can show 'Connected since Apr 2026' vs 'Add your Anthropic key'.
    Never includes the plaintext key.
    """

    model_config = ConfigDict(from_attributes=True)

    has_key: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by_user_id: uuid.UUID | None = None
