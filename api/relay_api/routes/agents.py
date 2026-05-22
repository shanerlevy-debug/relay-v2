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

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
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
from relay_api.services.agent_icons import AgentIconError, delete_icon, save_icon
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
        "slack_display_name_in_use": 409,
        "archived": 409,
        "invalid_slug": 400,
        "invalid": 400,
    }.get(e.code, 400)
    return HTTPException(
        status_code=status_code,
        detail={"code": e.code, "message": str(e)},
    )


def _icon_error_to_http(e: AgentIconError) -> HTTPException:
    status_code = {
        "too_large": 413,
        "bad_image_type": 415,
        "bad_image": 400,
        "storage_error": 500,
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
            slack_display_name=req.slack_display_name,
            slack_icon_url=req.slack_icon_url,
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
            "has_persona": bool(agent.slack_display_name or agent.slack_icon_url),
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
        "slack_display_name": agent.slack_display_name,
        "slack_icon_url": agent.slack_icon_url,
    }

    fields_set = set(req.model_dump(exclude_unset=True).keys())

    try:
        update_agent(
            db,
            agent=agent,
            slug=req.slug,
            anthropic_agent_id=req.anthropic_agent_id,
            environment_id=req.environment_id,
            description=req.description,
            is_default=req.is_default,
            fields_set=fields_set,
            slack_display_name=req.slack_display_name,
            slack_icon_url=req.slack_icon_url,
        )
    except AgentError as e:
        raise _agent_error_to_http(e) from e

    after = {
        "slug": agent.slug,
        "anthropic_agent_id": agent.anthropic_agent_id,
        "environment_id": agent.environment_id,
        "description": agent.description,
        "is_default": agent.is_default,
        "slack_display_name": agent.slack_display_name,
        "slack_icon_url": agent.slack_icon_url,
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
    # Best-effort cleanup of the on-disk icon — archived agents shouldn't
    # retain footprint, and re-creating with the same slug+display_name
    # could otherwise hit a stale file. delete_icon never raises.
    delete_icon(workspace_id=workspace.id, agent_id=agent.id)

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


# ---------------------------------------------------------------------------
# Icon upload / delete
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/icon")
async def post_agent_icon(
    agent_id: uuid.UUID,
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> AgentOut:
    """Upload a PNG/JPEG/GIF as the agent's Slack avatar.

    On success: persists the file to disk, sets `slack_icon_url` to the
    public URL, returns the updated AgentOut. Replaces any previous icon
    for this agent (other file extensions are cleaned up first).
    """
    agent = get_agent_by_id(db, workspace_id=workspace.id, agent_id=agent_id)
    if agent is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "agent not found"},
        )
    if agent.archived_at is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "archived", "message": "cannot edit an archived agent"},
        )

    # Stream up to RELAY_AGENT_ICON_MAX_BYTES + 1 to detect over-cap uploads
    # without buffering the whole world if someone tries to upload a huge file.
    cap = settings.RELAY_AGENT_ICON_MAX_BYTES
    body = await file.read(cap + 1)
    if len(body) > cap:
        raise _icon_error_to_http(AgentIconError(
            f"icon must be {cap / 1_048_576:.1f} MB or smaller",
            code="too_large",
        ))

    try:
        saved = save_icon(
            workspace_id=workspace.id,
            agent_id=agent.id,
            content=body,
            content_type=file.content_type or "application/octet-stream",
        )
    except AgentIconError as e:
        raise _icon_error_to_http(e) from e

    agent.slack_icon_url = saved.public_url

    db.add(AuditLog(
        workspace_id=workspace.id,
        actor_user_id=admin.id,
        event_type="agent.icon_updated",
        subject_type="agent",
        subject_id=agent.id,
        metadata_json={
            "slug": agent.slug,
            "icon_url": agent.slack_icon_url,
        },
    ))
    db.commit()
    db.refresh(agent)
    return AgentOut.model_validate(agent)


@router.delete("/{agent_id}/icon")
def delete_agent_icon(
    agent_id: uuid.UUID,
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> AgentOut:
    """Clear the agent's avatar. Removes the on-disk file (if any) and
    nulls the URL on the row.

    Note: this doesn't affect a `:emoji:` icon set via PATCH — that's
    just a string, not a file. The route still nulls slack_icon_url
    regardless of which form the icon took.
    """
    agent = get_agent_by_id(db, workspace_id=workspace.id, agent_id=agent_id)
    if agent is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "agent not found"},
        )
    if agent.archived_at is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "archived", "message": "cannot edit an archived agent"},
        )

    delete_icon(workspace_id=workspace.id, agent_id=agent.id)
    agent.slack_icon_url = None

    db.add(AuditLog(
        workspace_id=workspace.id,
        actor_user_id=admin.id,
        event_type="agent.icon_cleared",
        subject_type="agent",
        subject_id=agent.id,
        metadata_json={"slug": agent.slug},
    ))
    db.commit()
    db.refresh(agent)
    return AgentOut.model_validate(agent)
