"""BYOK Anthropic-key tests."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from relay_api.db.models import User
from relay_api.db.session import SessionLocal
from relay_api.main import app
from relay_api.services.anthropic_key import get_plaintext_key

pytestmark = pytest.mark.dbtest


def _signup_admin(client: TestClient) -> dict:
    suffix = uuid.uuid4().hex[:8]
    r = client.post(
        "/api/auth/signup",
        json={
            "email": f"admin-{suffix}@acme.test",
            "password": "correct-horse-battery",
            "workspace_name": f"Acme {suffix}",
        },
    )
    assert r.status_code == 201
    return r.json()


VALID_KEY = "sk-ant-api03-" + "x" * 80
ANOTHER_KEY = "sk-ant-api03-" + "y" * 80


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_status_starts_at_has_key_false(client: TestClient) -> None:
    _signup_admin(client)
    r = client.get("/api/workspace/anthropic-key")
    assert r.status_code == 200
    body = r.json()
    assert body["has_key"] is False
    assert body["created_at"] is None


def test_set_and_status(client: TestClient) -> None:
    me = _signup_admin(client)
    r = client.put("/api/workspace/anthropic-key", json={"key": VALID_KEY})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_key"] is True
    assert body["created_at"] is not None
    assert body["created_by_user_id"] == me["user"]["id"]

    # Plaintext readable by the bridge path (direct service call)
    with SessionLocal() as db:
        plaintext = get_plaintext_key(db, workspace_id=uuid.UUID(me["workspace"]["id"]))
        assert plaintext == VALID_KEY


def test_set_replaces_existing(client: TestClient) -> None:
    me = _signup_admin(client)
    r1 = client.put("/api/workspace/anthropic-key", json={"key": VALID_KEY})
    assert r1.status_code == 200
    r2 = client.put("/api/workspace/anthropic-key", json={"key": ANOTHER_KEY})
    assert r2.status_code == 200

    # Second key wins
    with SessionLocal() as db:
        plaintext = get_plaintext_key(db, workspace_id=uuid.UUID(me["workspace"]["id"]))
        assert plaintext == ANOTHER_KEY


def test_delete_clears_key(client: TestClient) -> None:
    me = _signup_admin(client)
    client.put("/api/workspace/anthropic-key", json={"key": VALID_KEY})
    r = client.delete("/api/workspace/anthropic-key")
    assert r.status_code == 204

    r = client.get("/api/workspace/anthropic-key")
    assert r.json()["has_key"] is False

    with SessionLocal() as db:
        assert get_plaintext_key(db, workspace_id=uuid.UUID(me["workspace"]["id"])) is None


def test_delete_is_idempotent(client: TestClient) -> None:
    """DELETE on a workspace with no key returns 204 cleanly."""
    _signup_admin(client)
    r = client.delete("/api/workspace/anthropic-key")
    assert r.status_code == 204


def test_invalid_prefix_rejected(client: TestClient) -> None:
    _signup_admin(client)
    r = client.put(
        "/api/workspace/anthropic-key",
        json={"key": "not-an-anthropic-key-just-some-string-here-padding"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_key_format"


def test_too_short_rejected(client: TestClient) -> None:
    _signup_admin(client)
    r = client.put("/api/workspace/anthropic-key", json={"key": "sk-ant-"})
    # min_length=10 in the schema catches this at validation layer
    assert r.status_code == 422


def test_non_admin_cannot_set_or_delete(client: TestClient) -> None:
    me = _signup_admin(client)
    with SessionLocal() as db:
        u = db.get(User, uuid.UUID(me["user"]["id"]))
        u.role = "member"
        db.commit()

    r = client.put("/api/workspace/anthropic-key", json={"key": VALID_KEY})
    assert r.status_code == 403
    r = client.delete("/api/workspace/anthropic-key")
    assert r.status_code == 403

    # GET still works for members
    r = client.get("/api/workspace/anthropic-key")
    assert r.status_code == 200


def test_unauthenticated_blocked(client: TestClient) -> None:
    r = client.get("/api/workspace/anthropic-key")
    assert r.status_code == 401


def test_cross_workspace_isolation(client: TestClient) -> None:
    """A key set in workspace A is never returned to workspace B."""
    me_a = _signup_admin(client)
    client.put("/api/workspace/anthropic-key", json={"key": VALID_KEY})
    client.post("/api/auth/logout")

    me_b = _signup_admin(client)
    body = client.get("/api/workspace/anthropic-key").json()
    assert body["has_key"] is False

    # And the bridge path for workspace B sees nothing
    with SessionLocal() as db:
        assert get_plaintext_key(db, workspace_id=uuid.UUID(me_b["workspace"]["id"])) is None
        # But workspace A still has its key
        assert get_plaintext_key(db, workspace_id=uuid.UUID(me_a["workspace"]["id"])) == VALID_KEY
