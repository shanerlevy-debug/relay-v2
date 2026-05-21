"""Audit log read schemas — paginated event timeline."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditLogEntry(BaseModel):
    """Single audit row. `actor_email` is joined from `users.email` when
    the actor exists; null for system-originated events (e.g. bridge-side
    `agent.message_routed`) or when the actor row was hard-deleted."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    subject_type: str
    subject_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    actor_email: str | None
    metadata_json: dict
    occurred_at: datetime


class AuditListOut(BaseModel):
    entries: list[AuditLogEntry]
    has_more: bool = Field(
        description="True if there are more rows beyond this page — UI shows a Load-more affordance.",
    )
