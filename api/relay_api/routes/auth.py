"""Auth routes: signup, login, logout."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from relay_api.db.models import Workspace
from relay_api.db.session import get_db
from relay_api.schemas.auth import (
    LoginRequest,
    SessionOut,
    SignupRequest,
    UserOut,
    WorkspaceOut,
)
from relay_api.services.auth.jwt_tokens import issue_session_token
from relay_api.services.auth.sessions import (
    clear_session_cookie,
    set_session_cookie,
)
from relay_api.services.auth.signup import SignupError, authenticate, signup

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _session_out(user, workspace) -> SessionOut:
    return SessionOut(
        user=UserOut.model_validate(user),
        workspace=WorkspaceOut.model_validate(workspace),
    )


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def post_signup(
    req: SignupRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionOut:
    try:
        workspace, user = signup(
            db,
            email=req.email,
            password=req.password,
            workspace_name=req.workspace_name,
        )
        db.commit()
    except SignupError as e:
        # email_in_use is the one we expect to surface as 409; everything
        # else is a 400 (validation).
        status_code = 409 if e.code == "email_in_use" else 400
        raise HTTPException(
            status_code=status_code,
            detail={"code": e.code, "message": str(e)},
        ) from e

    token, expires_at = issue_session_token(
        user_id=user.id,
        workspace_id=user.workspace_id,
    )
    set_session_cookie(response, token, expires_at)
    return _session_out(user, workspace)


@router.post("/login")
def post_login(
    req: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionOut:
    try:
        user = authenticate(db, email=req.email, password=req.password)
    except SignupError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": e.code, "message": str(e)},
        ) from e

    workspace = db.get(Workspace, user.workspace_id)
    if workspace is None:
        # Should never happen — a User with no Workspace is data corruption.
        raise HTTPException(
            status_code=500,
            detail={
                "code": "workspace_missing",
                "message": "user's workspace not found",
            },
        )

    token, expires_at = issue_session_token(
        user_id=user.id,
        workspace_id=user.workspace_id,
    )
    set_session_cookie(response, token, expires_at)
    return _session_out(user, workspace)


@router.post("/logout")
def post_logout(response: Response) -> dict:
    """Clear the session cookie. No-op if there wasn't one."""
    clear_session_cookie(response)
    return {"status": "ok"}
