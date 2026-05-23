"""DTOs for the CMA discovery endpoints (browse-and-pick Add Agent picker)."""
from __future__ import annotations

from pydantic import BaseModel


class CmaAgentSummaryOut(BaseModel):
    id: str
    model: str | None
    system: str | None  # full system prompt; UI truncates for preview
    archived_at: str | None


class CmaEnvironmentSummaryOut(BaseModel):
    id: str
    name: str | None
    networking_type: str | None


class CmaAgentsListOut(BaseModel):
    agents: list[CmaAgentSummaryOut]


class CmaEnvironmentsListOut(BaseModel):
    environments: list[CmaEnvironmentSummaryOut]
    # Last environment used when creating/updating an agent in this
    # workspace. The Add Agent picker pre-selects this when set.
    default_environment_id: str | None = None
