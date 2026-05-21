"""Workspace-level settings routes — BYOK key management, future settings.

Distinct from /api/users (user mgmt) and /api/agents (agent registry).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from relay_api.core.dependencies import current_workspace, require_admin
from relay_api.db.models import AuditLog, User, Workspace, WorkspaceAnthropicKey
from relay_api.db.session import get_db
from relay_api.schemas.anthropic_key import (
    AnthropicKeySetRequest,
    AnthropicKeyStatusOut,
)
from relay_api.services.anthropic_key import (
    AnthropicKeyError,
    delete_key,
    set_key,
)

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


def _anthropic_key_status(
    db: Session, *, workspace_id
) -> AnthropicKeyStatusOut:
    row = db.execute(
        select(WorkspaceAnthropicKey).where(
            WorkspaceAnthropicKey.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if row is None:
        return AnthropicKeyStatusOut(has_key=False)
    return AnthropicKeyStatusOut(
        has_key=True,
        created_at=row.created_at,
        updated_at=row.updated_at,
        created_by_user_id=row.created_by_user_id,
    )


@router.get("/anthropic-key")
def get_status(
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> AnthropicKeyStatusOut:
    """Returns whether a key is configured + audit-y metadata. Never the key."""
    return _anthropic_key_status(db, workspace_id=workspace.id)


@router.put("/anthropic-key")
def put_key(
    req: AnthropicKeySetRequest,
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> AnthropicKeyStatusOut:
    """Set or replace the workspace's Anthropic API key (admin-only)."""
    is_replacement_existing = (
        db.execute(
            select(WorkspaceAnthropicKey.workspace_id).where(
                WorkspaceAnthropicKey.workspace_id == workspace.id
            )
        ).first()
        is not None
    )
    try:
        set_key(
            db,
            workspace_id=workspace.id,
            raw_key=req.key,
            created_by_user_id=admin.id,
        )
    except AnthropicKeyError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": e.code, "message": str(e)},
        ) from e

    db.add(AuditLog(
        workspace_id=workspace.id,
        actor_user_id=admin.id,
        event_type=(
            "workspace.anthropic_key_replaced"
            if is_replacement_existing
            else "workspace.anthropic_key_set"
        ),
        subject_type="anthropic_key",
        subject_id=None,
        metadata_json={},
    ))
    db.commit()
    return _anthropic_key_status(db, workspace_id=workspace.id)


@router.delete("/anthropic-key", status_code=status.HTTP_204_NO_CONTENT)
def delete_key_route(
    admin: User = Depends(require_admin),
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> None:
    removed = delete_key(db, workspace_id=workspace.id)
    if removed:
        db.add(AuditLog(
            workspace_id=workspace.id,
            actor_user_id=admin.id,
            event_type="workspace.anthropic_key_removed",
            subject_type="anthropic_key",
            subject_id=None,
            metadata_json={},
        ))
        db.commit()
    return None
