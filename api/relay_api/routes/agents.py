"""Agents CRUD routes — replaces v1's git-ops agents.yaml.

  GET    /api/agents              list active agents + seat count
  POST   /api/agents              admin: create (25-cap)
  GET    /api/agents/{id}         single agent
  PATCH  /api/agents/{id}         admin: edit
  DELETE /api/agents/{id}         admin: archive

All mutations write to audit_log.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from relay_api.core.config import settings
from relay_api.core.dependencies import current_workspace, require_admin
from relay_api.db.models import Agent, AuditLog, User, Workspace
from relay_api.db.session import get_db
from relay_api.schemas.agents import (
    AgentCreateRequest,
    AgentListOut,
    AgentOut,
    AgentSeatsOut,
    AgentUpdateRequest,
)
from relay_api.services.agents import (
    AgentError,
    archive_agent,
    count_active_agents,
    create_agent,
    get_agent_by_id,
    list_agents,
    update_agent,
)

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _agent_error_to_http(e: AgentError) -> HTTPException:
    status_code = {
        "agent_limit_reached": 409,
        "slug_in_use": 409,
        "archived": 409,
        "invalid_slug": 400,
        "invalid": 400,
    }.get(e.code, 400)
    return HTTPException(
        status_code=status_code,
        detail={"code": e.code, "message": str(e)},
    )


@router.get("")
def get_agents(
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> AgentListOut:
    agents = list_agents(db, workspace_id=workspace.id)
    return AgentListOut(
        agents=[AgentOut.model_validate(a) for a in agents],
        seats=AgentSeatsOut(
            active=count_active_agents(db, workspace_id=workspace.id),
            cap=settings.RELAY_AGENTS_PER_WORKSPACE,
        ),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def post_agent(
    req: AgentCreateRequest,
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> AgentOut:
    try:
        agent = create_agent(
            db,
            workspace_id=workspace.id,
            slug=req.slug,
            anthropic_agent_id=req.anthropic_agent_id,
            environment_id=req.environment_id,
            description=req.description,
            is_default=req.is_default,
        )
    except AgentError as e:
        raise _agent_error_to_http(e) from e

    db.add(AuditLog(
        workspace_id=workspace.id,
        actor_user_id=admin.id,
        event_type="agent.created",
        subject_type="agent",
        subject_id=agent.id,
        metadata_json={
            "slug": agent.slug,
            "anthropic_agent_id": agent.anthropic_agent_id,
            "is_default": agent.is_default,
        },
    ))
    db.commit()
    db.refresh(agent)
    return AgentOut.model_validate(agent)


@router.get("/{agent_id}")
def get_one(
    agent_id: uuid.UUID,
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> AgentOut:
    agent = get_agent_by_id(db, workspace_id=workspace.id, agent_id=agent_id)
    if agent is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "agent not found"},
        )
    return AgentOut.model_validate(agent)


@router.patch("/{agent_id}")
def patch_agent(
    agent_id: uuid.UUID,
    req: AgentUpdateRequest,
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> AgentOut:
    agent = get_agent_by_id(db, workspace_id=workspace.id, agent_id=agent_id)
    if agent is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "agent not found"},
        )

    # Snapshot the original values for the audit log delta.
    before = {
        "slug": agent.slug,
        "anthropic_agent_id": agent.anthropic_agent_id,
        "environment_id": agent.environment_id,
        "description": agent.description,
        "is_default": agent.is_default,
    }

    try:
        update_agent(
            db,
            agent=agent,
            slug=req.slug,
            anthropic_agent_id=req.anthropic_agent_id,
            environment_id=req.environment_id,
            description=req.description,
            is_default=req.is_default,
        )
    except AgentError as e:
        raise _agent_error_to_http(e) from e

    after = {
        "slug": agent.slug,
        "anthropic_agent_id": agent.anthropic_agent_id,
        "environment_id": agent.environment_id,
        "description": agent.description,
        "is_default": agent.is_default,
    }
    changes = {k: {"from": before[k], "to": after[k]} for k in before if before[k] != after[k]}

    if changes:
        db.add(AuditLog(
            workspace_id=workspace.id,
            actor_user_id=admin.id,
            event_type="agent.updated",
            subject_type="agent",
            subject_id=agent.id,
            metadata_json={"slug": agent.slug, "changes": changes},
        ))
    db.commit()
    db.refresh(agent)
    return AgentOut.model_validate(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    agent_id: uuid.UUID,
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> None:
    agent = get_agent_by_id(db, workspace_id=workspace.id, agent_id=agent_id)
    if agent is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "agent not found"},
        )

    archive_agent(db, agent=agent)

    db.add(AuditLog(
        workspace_id=workspace.id,
        actor_user_id=admin.id,
        event_type="agent.archived",
        subject_type="agent",
        subject_id=agent.id,
        metadata_json={"slug": agent.slug},
    ))
    db.commit()
    return None
