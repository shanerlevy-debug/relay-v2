"""Tests for GET /api/audit."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from relay_api.db.models import AuditLog
from relay_api.db.session import SessionLocal
from relay_api.main import app

pytestmark = pytest.mark.dbtest


def _signup(client: TestClient) -> dict:
    suffix = uuid.uuid4().hex[:8]
    r = client.post(
        "/api/auth/signup",
        json={
            "email": f"u-{suffix}@x.test",
            "password": "correct-horse-battery",
            "workspace_name": f"WS {suffix}",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_audit_empty_workspace_returns_empty_list(client: TestClient) -> None:
    """A workspace right after signup has zero audit rows by design — signup
    itself doesn't write an audit entry. First actions (slack install, key
    set, agent create, invite) are what populate the log."""
    _signup(client)
    r = client.get("/api/audit")
    assert r.status_code == 200
    body = r.json()
    assert body["entries"] == []
    assert body["has_more"] is False


def test_audit_returns_workspace_events_newest_first(client: TestClient) -> None:
    from datetime import UTC, datetime, timedelta

    me = _signup(client)
    ws_id = uuid.UUID(me["workspace"]["id"])
    user_id = uuid.UUID(me["user"]["id"])

    # Seed three audit rows with EXPLICIT occurred_at so the ordering is
    # deterministic (server_default=func.now() can give identical timestamps
    # for rows committed in the same statement, and the UUID tiebreaker is
    # random).
    base = datetime.now(UTC)
    with SessionLocal() as db:
        for i, etype in enumerate(["agent.created", "user.invited", "agent.archived"]):
            db.add(AuditLog(
                workspace_id=ws_id,
                actor_user_id=user_id,
                event_type=etype,
                subject_type="agent",
                subject_id=uuid.uuid4(),
                metadata_json={"i": i},
                occurred_at=base + timedelta(seconds=i),
            ))
        db.commit()

    r = client.get("/api/audit")
    assert r.status_code == 200
    body = r.json()
    assert len(body["entries"]) == 3
    # Newest first — the seed loop's last item has the latest occurred_at
    types = [e["event_type"] for e in body["entries"]]
    assert types == ["agent.archived", "user.invited", "agent.created"]
    # actor_email joined in
    for e in body["entries"]:
        assert e["actor_email"] == me["user"]["email"]


def test_audit_system_event_has_null_actor_email(client: TestClient) -> None:
    me = _signup(client)
    ws_id = uuid.UUID(me["workspace"]["id"])

    with SessionLocal() as db:
        db.add(AuditLog(
            workspace_id=ws_id,
            actor_user_id=None,
            event_type="agent.message_routed",
            subject_type="agent",
            subject_id=uuid.uuid4(),
            metadata_json={"slug": "vanguard", "reason": "default"},
        ))
        db.commit()

    body = client.get("/api/audit").json()
    assert len(body["entries"]) == 1
    assert body["entries"][0]["actor_email"] is None


def test_audit_pagination(client: TestClient) -> None:
    me = _signup(client)
    ws_id = uuid.UUID(me["workspace"]["id"])
    user_id = uuid.UUID(me["user"]["id"])

    # 75 rows
    with SessionLocal() as db:
        for i in range(75):
            db.add(AuditLog(
                workspace_id=ws_id,
                actor_user_id=user_id,
                event_type=f"test.event_{i:02d}",
                subject_type="test",
                metadata_json={"i": i},
            ))
        db.commit()

    # Default limit is 50
    page1 = client.get("/api/audit").json()
    assert len(page1["entries"]) == 50
    assert page1["has_more"] is True

    # Next page
    page2 = client.get("/api/audit?offset=50&limit=50").json()
    assert len(page2["entries"]) == 25
    assert page2["has_more"] is False


def test_audit_max_limit_clamped(client: TestClient) -> None:
    _signup(client)
    # limit > 200 should reject (Query ge=1 le=MAX_LIMIT)
    r = client.get("/api/audit?limit=500")
    assert r.status_code == 422


def test_audit_requires_session(client: TestClient) -> None:
    r = client.get("/api/audit")
    assert r.status_code == 401


def test_audit_cross_workspace_isolation(client: TestClient) -> None:
    """Workspace A's audit log is not visible to workspace B."""
    me_a = _signup(client)
    ws_a = uuid.UUID(me_a["workspace"]["id"])
    user_a = uuid.UUID(me_a["user"]["id"])

    with SessionLocal() as db:
        db.add(AuditLog(
            workspace_id=ws_a,
            actor_user_id=user_a,
            event_type="agent.created",
            subject_type="agent",
            metadata_json={"slug": "secret-agent"},
        ))
        db.commit()

    # B logs out + creates own workspace
    client.post("/api/auth/logout")
    _signup(client)
    body = client.get("/api/audit").json()
    assert body["entries"] == []
