"""Audit log read endpoint.

GET /api/audit?limit=N&offset=N — paginated by descending occurred_at.
Workspace-scoped via current_workspace.

Joins `users.email` for the actor when present so the UI doesn't have
to make a second roundtrip. Bridge-originated events
(agent.message_routed) have a null actor — those render as `(system)`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from relay_api.core.dependencies import current_workspace
from relay_api.db.models import AuditLog, User, Workspace
from relay_api.db.session import get_db
from relay_api.schemas.audit import AuditListOut, AuditLogEntry

router = APIRouter(prefix="/api/audit", tags=["audit"])

# Hard cap on per-request page size. Operators can paginate beyond it.
MAX_LIMIT = 200
DEFAULT_LIMIT = 50


@router.get("")
def get_audit(
    workspace: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> AuditListOut:
    """Recent audit events for the current workspace.

    Fetches `limit + 1` rows internally so we can tell the UI whether
    there's a next page without a second COUNT query.
    """
    rows = db.execute(
        select(AuditLog, User.email)
        .outerjoin(User, AuditLog.actor_user_id == User.id)
        .where(AuditLog.workspace_id == workspace.id)
        .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit + 1)
    ).all()

    has_more = len(rows) > limit
    page = rows[:limit]

    entries = [
        AuditLogEntry(
            id=row[0].id,
            event_type=row[0].event_type,
            subject_type=row[0].subject_type,
            subject_id=row[0].subject_id,
            actor_user_id=row[0].actor_user_id,
            actor_email=row[1],
            metadata_json=row[0].metadata_json,
            occurred_at=row[0].occurred_at,
        )
        for row in page
    ]
    return AuditListOut(entries=entries, has_more=has_more)
