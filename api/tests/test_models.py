"""ORM smoke tests against a live Postgres.

Each test creates a fresh workspace (using a UUID-y display name to keep
them isolated) and tears down on teardown. Requires docker-compose
postgres up; skipped automatically if the DB can't be reached at import
time would be cleaner but the connection happens lazily per test.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from relay_api.db.models import (
    AuditLog,
    EnterpriseRequest,
    Invite,
    User,
    Workspace,
)
from relay_api.db.session import SessionLocal


pytestmark = pytest.mark.dbtest


@pytest.fixture
def db():
    """Yield a session and roll back at end so tests don't leak rows."""
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _make_workspace(db, name: str | None = None) -> Workspace:
    ws = Workspace(display_name=name or f"test-{uuid.uuid4().hex[:8]}")
    db.add(ws)
    db.flush()
    assert ws.id is not None
    assert ws.created_at is not None
    assert ws.created_at.tzinfo is not None, "created_at must be tz-aware"
    return ws


def test_workspace_roundtrip(db) -> None:
    ws = _make_workspace(db, name="Acme Ltd")
    assert ws.display_name == "Acme Ltd"
    assert ws.archived_at is None


def test_user_attaches_to_workspace(db) -> None:
    ws = _make_workspace(db)
    user = User(
        workspace_id=ws.id,
        email="founder@acme.test",
        role="admin",
    )
    db.add(user)
    db.flush()
    assert user.role == "admin"
    assert user.created_at is not None

    # The relationship loads
    db.refresh(ws)
    assert len(ws.users) == 1
    assert ws.users[0].email == "founder@acme.test"


def test_user_role_check_constraint_rejects_invalid(db) -> None:
    from sqlalchemy.exc import IntegrityError

    ws = _make_workspace(db)
    bad = User(
        workspace_id=ws.id,
        email="weird@acme.test",
        role="superhero",  # not in ('admin', 'member')
    )
    db.add(bad)
    with pytest.raises(IntegrityError):
        db.flush()


def test_audit_log_with_jsonb_metadata(db) -> None:
    ws = _make_workspace(db)
    user = User(workspace_id=ws.id, email="a@x.test", role="admin")
    db.add(user)
    db.flush()

    entry = AuditLog(
        workspace_id=ws.id,
        actor_user_id=user.id,
        event_type="workspace.slack_install_completed",
        subject_type="workspace",
        subject_id=ws.id,
        metadata_json={"slack_team_id": "T123", "scopes": ["chat:write", "channels:history"]},
    )
    db.add(entry)
    db.flush()
    assert entry.metadata_json["slack_team_id"] == "T123"
    assert entry.occurred_at.tzinfo is not None


def test_invite_token_hash_unique(db) -> None:
    from sqlalchemy.exc import IntegrityError

    ws = _make_workspace(db)
    admin = User(workspace_id=ws.id, email="admin@x.test", role="admin")
    db.add(admin)
    db.flush()

    expires = datetime.now(tz=timezone.utc) + timedelta(days=7)
    token_hash = b"\xaa" * 32

    inv1 = Invite(
        workspace_id=ws.id,
        email="invitee@x.test",
        role="member",
        token_hash=token_hash,
        expires_at=expires,
        created_by_user_id=admin.id,
    )
    db.add(inv1)
    db.flush()

    inv2 = Invite(
        workspace_id=ws.id,
        email="other@x.test",
        role="member",
        token_hash=token_hash,  # collision
        expires_at=expires,
        created_by_user_id=admin.id,
    )
    db.add(inv2)
    with pytest.raises(IntegrityError):
        db.flush()


def test_enterprise_request_captures_context(db) -> None:
    ws = _make_workspace(db)
    req = EnterpriseRequest(
        workspace_id=ws.id,
        user_id=None,
        context="user_limit",
        notes="hit the 25-user ceiling, want to add 40 more",
    )
    db.add(req)
    db.flush()
    assert req.context == "user_limit"
    assert req.notified_at is None
