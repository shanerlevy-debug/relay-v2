"""Group CRUD + membership routes.

  GET    /api/groups                          list active groups
  POST   /api/groups                          admin: create (non-default)
  GET    /api/groups/{id}                     group detail (users + agents)
  PATCH  /api/groups/{id}                     admin: rename
  DELETE /api/groups/{id}                     admin: archive (default group rejected)

  PUT    /api/groups/{id}/users/{user_id}     admin: add member
  DELETE /api/groups/{id}/users/{user_id}     admin: remove member
  PUT    /api/groups/{id}/agents/{agent_id}   admin: add agent
  DELETE /api/groups/{id}/agents/{agent_id}   admin: remove agent

  GET    /api/users/{id}/groups               list a user's groups (for chips)
  GET    /api/agents/{id}/groups              list an agent's groups (for chips)

All mutations write to audit_log.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from relay_api.core.dependencies import current_workspace, require_admin
from relay_api.db.models import Agent, AuditLog, User, Workspace
from relay_api.db.session import get_db
from relay_api.db.models import AgentGroup, Group, GroupMembership
from relay_api.schemas.groups import (
    GroupCreateRequest,
    GroupListOut,
    GroupMemberAgent,
    GroupMembershipMap,
    GroupMembersOut,
    GroupMemberUser,
    GroupOut,
    GroupRenameRequest,
    GroupSummary,
)
from sqlalchemy import select
from relay_api.services.agents import get_agent_by_id
from relay_api.services.groups import (
    GroupError,
    add_agent_to_group,
    add_user_to_group,
    archive_group,
    create_group,
    get_group,
    list_agents_in_group,
    list_groups,
    list_groups_for_agent,
    list_groups_for_user,
    list_users_in_group,
    remove_agent_from_group,
    remove_user_from_group,
    rename_group,
)

router = APIRouter(prefix="/api/groups", tags=["groups"])


def _group_error_to_http(e: GroupError) -> HTTPException:
    status_code = {
        "name_in_use": 409,
        "default_group": 409,
        "invalid_name": 400,
        "invalid": 400,
    }.get(e.code, 400)
    return HTTPException(
        status_code=status_code,
        detail={"code": e.code, "message": str(e)},
    )


def _get_or_404(
    db: Session, *, workspace_id: uuid.UUID, group_id: uuid.UUID,
):
    group = get_group(db, workspace_id=workspace_id, group_id=group_id)
    if group is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "group not found"},
        )
    return group


# ---------------------------------------------------------------------------
# Group CRUD
# ---------------------------------------------------------------------------


@router.get("")
def get_groups(
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> GroupListOut:
    groups = list_groups(db, workspace_id=workspace.id)
    return GroupListOut(groups=[GroupOut.model_validate(g) for g in groups])


@router.post("", status_code=status.HTTP_201_CREATED)
def post_group(
    req: GroupCreateRequest,
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> GroupOut:
    try:
        group = create_group(db, workspace_id=workspace.id, name=req.name)
    except GroupError as e:
        raise _group_error_to_http(e) from e
    db.add(AuditLog(
        workspace_id=workspace.id,
        actor_user_id=admin.id,
        event_type="group.created",
        subject_type="group",
        subject_id=group.id,
        metadata_json={"name": group.name},
    ))
    db.commit()
    db.refresh(group)
    return GroupOut.model_validate(group)


@router.get("/{group_id}")
def get_group_detail(
    group_id: uuid.UUID,
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> GroupMembersOut:
    group = _get_or_404(db, workspace_id=workspace.id, group_id=group_id)
    users = list_users_in_group(db, group=group)
    agents = list_agents_in_group(db, group=group)
    return GroupMembersOut(
        group=GroupOut.model_validate(group),
        users=[GroupMemberUser.model_validate(u) for u in users],
        agents=[GroupMemberAgent.model_validate(a) for a in agents],
    )


@router.patch("/{group_id}")
def patch_group(
    group_id: uuid.UUID,
    req: GroupRenameRequest,
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> GroupOut:
    group = _get_or_404(db, workspace_id=workspace.id, group_id=group_id)
    before = group.name
    try:
        rename_group(db, group=group, name=req.name)
    except GroupError as e:
        raise _group_error_to_http(e) from e
    if before != group.name:
        db.add(AuditLog(
            workspace_id=workspace.id,
            actor_user_id=admin.id,
            event_type="group.renamed",
            subject_type="group",
            subject_id=group.id,
            metadata_json={"from": before, "to": group.name},
        ))
    db.commit()
    db.refresh(group)
    return GroupOut.model_validate(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: uuid.UUID,
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> None:
    group = _get_or_404(db, workspace_id=workspace.id, group_id=group_id)
    try:
        archive_group(db, group=group)
    except GroupError as e:
        raise _group_error_to_http(e) from e
    db.add(AuditLog(
        workspace_id=workspace.id,
        actor_user_id=admin.id,
        event_type="group.archived",
        subject_type="group",
        subject_id=group.id,
        metadata_json={"name": group.name},
    ))
    db.commit()
    return None


# ---------------------------------------------------------------------------
# User membership
# ---------------------------------------------------------------------------


def _ensure_user_in_workspace(
    db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> User:
    user = db.get(User, user_id)
    if user is None or user.workspace_id != workspace_id or user.deleted_at is not None:
        raise HTTPException(
            status_code=404,
            detail={"code": "user_not_found", "message": "user not found in workspace"},
        )
    return user


@router.put("/{group_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def put_group_user(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> None:
    group = _get_or_404(db, workspace_id=workspace.id, group_id=group_id)
    user = _ensure_user_in_workspace(db, workspace_id=workspace.id, user_id=user_id)
    add_user_to_group(db, group=group, user_id=user.id)
    db.add(AuditLog(
        workspace_id=workspace.id,
        actor_user_id=admin.id,
        event_type="group.user_added",
        subject_type="group",
        subject_id=group.id,
        metadata_json={"group_name": group.name, "user_id": str(user.id), "email": user.email},
    ))
    db.commit()


@router.delete("/{group_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group_user(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> None:
    group = _get_or_404(db, workspace_id=workspace.id, group_id=group_id)
    user = _ensure_user_in_workspace(db, workspace_id=workspace.id, user_id=user_id)
    remove_user_from_group(db, group=group, user_id=user.id)
    db.add(AuditLog(
        workspace_id=workspace.id,
        actor_user_id=admin.id,
        event_type="group.user_removed",
        subject_type="group",
        subject_id=group.id,
        metadata_json={"group_name": group.name, "user_id": str(user.id), "email": user.email},
    ))
    db.commit()


# ---------------------------------------------------------------------------
# Agent membership
# ---------------------------------------------------------------------------


def _ensure_agent_in_workspace(
    db: Session, *, workspace_id: uuid.UUID, agent_id: uuid.UUID
) -> Agent:
    agent = get_agent_by_id(db, workspace_id=workspace_id, agent_id=agent_id)
    if agent is None or agent.archived_at is not None:
        raise HTTPException(
            status_code=404,
            detail={"code": "agent_not_found", "message": "agent not found in workspace"},
        )
    return agent


@router.put("/{group_id}/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def put_group_agent(
    group_id: uuid.UUID,
    agent_id: uuid.UUID,
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> None:
    group = _get_or_404(db, workspace_id=workspace.id, group_id=group_id)
    agent = _ensure_agent_in_workspace(db, workspace_id=workspace.id, agent_id=agent_id)
    add_agent_to_group(db, group=group, agent_id=agent.id)
    db.add(AuditLog(
        workspace_id=workspace.id,
        actor_user_id=admin.id,
        event_type="group.agent_added",
        subject_type="group",
        subject_id=group.id,
        metadata_json={"group_name": group.name, "agent_id": str(agent.id), "slug": agent.slug},
    ))
    db.commit()


@router.delete("/{group_id}/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group_agent(
    group_id: uuid.UUID,
    agent_id: uuid.UUID,
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> None:
    group = _get_or_404(db, workspace_id=workspace.id, group_id=group_id)
    agent = _ensure_agent_in_workspace(db, workspace_id=workspace.id, agent_id=agent_id)
    remove_agent_from_group(db, group=group, agent_id=agent.id)
    db.add(AuditLog(
        workspace_id=workspace.id,
        actor_user_id=admin.id,
        event_type="group.agent_removed",
        subject_type="group",
        subject_id=group.id,
        metadata_json={"group_name": group.name, "agent_id": str(agent.id), "slug": agent.slug},
    ))
    db.commit()


# ---------------------------------------------------------------------------
# Batch membership map — used by /agents and /users for chip rendering
# ---------------------------------------------------------------------------


@router.get("/memberships")
def get_memberships(
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> GroupMembershipMap:
    """One round-trip: every user → its groups + every agent → its
    groups for this workspace. The list pages render chips inline
    without N+1 fetches."""
    # Pull every active group in the workspace into a id→summary map
    groups_by_id: dict[uuid.UUID, GroupSummary] = {
        g.id: GroupSummary(id=g.id, name=g.name, is_default=g.is_default)
        for g in db.execute(
            select(Group)
            .where(Group.workspace_id == workspace.id)
            .where(Group.archived_at.is_(None))
        ).scalars()
    }
    # Single sweep over the edge tables, filtered to workspace's groups.
    users_map: dict[str, list[GroupSummary]] = {}
    for user_id, group_id in db.execute(
        select(GroupMembership.user_id, GroupMembership.group_id)
        .where(GroupMembership.group_id.in_(groups_by_id.keys()))
    ).all():
        users_map.setdefault(str(user_id), []).append(groups_by_id[group_id])
    agents_map: dict[str, list[GroupSummary]] = {}
    for agent_id, group_id in db.execute(
        select(AgentGroup.agent_id, AgentGroup.group_id)
        .where(AgentGroup.group_id.in_(groups_by_id.keys()))
    ).all():
        agents_map.setdefault(str(agent_id), []).append(groups_by_id[group_id])

    # Stable sort: default group first, then by name.
    def _sort(seq: list[GroupSummary]) -> list[GroupSummary]:
        return sorted(seq, key=lambda g: (not g.is_default, g.name.lower()))
    return GroupMembershipMap(
        users={k: _sort(v) for k, v in users_map.items()},
        agents={k: _sort(v) for k, v in agents_map.items()},
    )


# ---------------------------------------------------------------------------
# Reverse lookups — fed by the chip on /agents and /users rows
# ---------------------------------------------------------------------------


@router.get("/by-user/{user_id}")
def get_groups_for_user(
    user_id: uuid.UUID,
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> list[GroupSummary]:
    _ensure_user_in_workspace(db, workspace_id=workspace.id, user_id=user_id)
    groups = list_groups_for_user(db, user_id=user_id)
    return [
        GroupSummary(id=g.id, name=g.name, is_default=g.is_default) for g in groups
    ]


@router.get("/by-agent/{agent_id}")
def get_groups_for_agent(
    agent_id: uuid.UUID,
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> list[GroupSummary]:
    _ensure_agent_in_workspace(db, workspace_id=workspace.id, agent_id=agent_id)
    groups = list_groups_for_agent(db, agent_id=agent_id)
    return [
        GroupSummary(id=g.id, name=g.name, is_default=g.is_default) for g in groups
    ]
