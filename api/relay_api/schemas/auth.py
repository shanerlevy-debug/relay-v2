"""Pydantic request/response schemas for auth + identity surfaces."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# RFC-2606-friendly: accepts `.test`, `.example`, `.localhost` for test fixtures
# without giving up the basic structural shape check. We don't try to RFC-5321
# this — email-validator's deliverability heuristics are not worth the false
# rejections on internal accounts.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL_RE.match(value):
        raise ValueError("invalid email format")
    return value


class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)
    workspace_name: str = Field(min_length=2, max_length=255)

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str) -> str:
        return _normalize_email(v)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str) -> str:
        return _normalize_email(v)


class UserOut(BaseModel):
    """Public-facing user shape. Never includes password_hash or other
    secret-side fields."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: Literal["admin", "member"]
    workspace_id: uuid.UUID
    email_verified_at: datetime | None
    created_at: datetime


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    slack_team_id: str | None
    created_at: datetime


class SessionOut(BaseModel):
    """Returned by /api/auth/signup, /api/auth/login, /api/me.

    The cookie carries the auth token; this body carries the rendered
    identity the UI needs immediately after login.
    """

    user: UserOut
    workspace: WorkspaceOut
