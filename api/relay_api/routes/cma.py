"""CMA discovery routes — for the browse-and-pick Add Agent screen.

  GET /api/cma/agents          admin: list every agent the BYOK can see
  GET /api/cma/environments    admin: list every environment the BYOK can see

Both endpoints are admin-only — workspace members don't add agents.
Both use the workspace's stored Anthropic key (envelope-decrypted JIT).
Errors collapse to a small set of codes the UI branches on:

  byok_missing       — no Anthropic key set (UI links to Settings → BYOK)
  byok_invalid       — Anthropic 401'd the key
  rate_limited       — Anthropic 429
  upstream_error     — anything else (with a generic message)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from relay_api.core.dependencies import current_workspace, require_admin
from relay_api.db.models import User, Workspace
from relay_api.db.session import get_db
from relay_api.schemas.cma import (
    CmaAgentsListOut,
    CmaAgentSummaryOut,
    CmaEnvironmentSummaryOut,
    CmaEnvironmentsListOut,
)
from relay_api.services.cma_agents import (
    CmaDiscoveryError,
    list_cma_agents,
    list_cma_environments,
)

router = APIRouter(prefix="/api/cma", tags=["cma"])


def _to_http(e: CmaDiscoveryError) -> HTTPException:
    """Map the small set of CmaDiscoveryError codes to HTTP statuses."""
    status_code = {
        "byok_missing": 400,
        "byok_invalid": 502,
        "rate_limited": 429,
        "upstream_error": 502,
        "agent_not_found": 404,
        "env_not_found": 404,
        "agent_archived": 409,
    }.get(e.code, 502)
    return HTTPException(
        status_code=status_code,
        detail={"code": e.code, "message": str(e)},
    )


@router.get("/agents")
def get_cma_agents(
    _admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> CmaAgentsListOut:
    try:
        agents = list_cma_agents(db, workspace_id=workspace.id)
    except CmaDiscoveryError as e:
        raise _to_http(e) from e
    return CmaAgentsListOut(
        agents=[CmaAgentSummaryOut(**a.__dict__) for a in agents]
    )


@router.get("/environments")
def get_cma_environments(
    _admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> CmaEnvironmentsListOut:
    try:
        envs = list_cma_environments(db, workspace_id=workspace.id)
    except CmaDiscoveryError as e:
        raise _to_http(e) from e
    return CmaEnvironmentsListOut(
        environments=[CmaEnvironmentSummaryOut(**e.__dict__) for e in envs]
    )
