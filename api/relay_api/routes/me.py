"""GET /api/me — the "who am I" endpoint the UI calls on app load.

Returns 401 if no valid session cookie, 200 with user+workspace otherwise.
The UI uses 401 here to decide "redirect to login."
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from relay_api.core.dependencies import current_user, current_workspace
from relay_api.db.models import User, Workspace
from relay_api.schemas.auth import SessionOut, UserOut, WorkspaceOut

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me")
def get_me(
    user: User = Depends(current_user),
    workspace: Workspace = Depends(current_workspace),
) -> SessionOut:
    return SessionOut(
        user=UserOut.model_validate(user),
        workspace=WorkspaceOut.model_validate(workspace),
    )
