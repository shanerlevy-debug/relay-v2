"""Agents CRUD tests.

Covers the full CRUD surface + the two key invariants (slug uniqueness
per workspace, single-default-active-agent) + the 25-agent cap +
admin-only gates.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from relay_api.core.config import settings
from relay_api.db.models import User
from relay_api.db.session import SessionLocal
from relay_api.main import app

pytestmark = pytest.mark.dbtest


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _signup_admin(client: TestClient) -> dict:
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "email": f"admin-{suffix}@acme.test",
        "password": "correct-horse-battery",
        "workspace_name": f"Acme {suffix}",
    }
    r = client.post("/api/auth/signup", json=payload)
    assert r.status_code == 201
    return r.json()


def _create_agent(
    client: TestClient,
    *,
    slug: str | None = None,
    is_default: bool = False,
    anthropic_agent_id: str | None = None,
    environment_id: str | None = None,
) -> dict:
    payload = {
        "slug": slug or f"agent-{uuid.uuid4().hex[:6]}",
        "anthropic_agent_id": anthropic_agent_id or f"agent_{uuid.uuid4().hex[:20]}",
        "environment_id": environment_id or f"env_{uuid.uuid4().hex[:18]}",
        "description": "test agent",
        "is_default": is_default,
    }
    r = client.post("/api/agents", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


def test_full_crud_cycle(client: TestClient) -> None:
    _signup_admin(client)

    # Empty list on a fresh workspace
    r = client.get("/api/agents")
    assert r.status_code == 200
    body = r.json()
    assert body["agents"] == []
    assert body["seats"]["active"] == 0
    assert body["seats"]["cap"] == settings.RELAY_AGENTS_PER_WORKSPACE

    # Create
    agent = _create_agent(client, slug="vanguard", is_default=True)
    assert agent["slug"] == "vanguard"
    assert agent["is_default"] is True
    agent_id = agent["id"]

    # Get
    r = client.get(f"/api/agents/{agent_id}")
    assert r.status_code == 200
    assert r.json()["slug"] == "vanguard"

    # List shows one agent
    body = client.get("/api/agents").json()
    assert len(body["agents"]) == 1
    assert body["seats"]["active"] == 1

    # Update — change description + slug
    r = client.patch(
        f"/api/agents/{agent_id}",
        json={"slug": "scout", "description": "renamed"},
    )
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["slug"] == "scout"
    assert after["description"] == "renamed"
    assert after["is_default"] is True  # unchanged

    # Archive (DELETE)
    r = client.delete(f"/api/agents/{agent_id}")
    assert r.status_code == 204

    # No longer in active list, seat reclaimed
    body = client.get("/api/agents").json()
    assert body["agents"] == []
    assert body["seats"]["active"] == 0


def test_slug_must_be_unique_per_workspace(client: TestClient) -> None:
    _signup_admin(client)
    _create_agent(client, slug="vanguard")
    r = client.post(
        "/api/agents",
        json={
            "slug": "vanguard",
            "anthropic_agent_id": "agent_001",
            "environment_id": "env_001",
        },
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "slug_in_use"


def test_default_exclusivity_within_workspace(client: TestClient) -> None:
    """Setting a new default flips the old one off (no constraint violation)."""
    _signup_admin(client)
    a1 = _create_agent(client, slug="alfred", is_default=True)
    a2 = _create_agent(client, slug="vanguard", is_default=False)

    # Promote a2 to default — a1 should flip off
    r = client.patch(f"/api/agents/{a2['id']}", json={"is_default": True})
    assert r.status_code == 200
    assert r.json()["is_default"] is True

    after_a1 = client.get(f"/api/agents/{a1['id']}").json()
    assert after_a1["is_default"] is False


def test_archived_agent_releases_slug(client: TestClient) -> None:
    """After archive, the same slug can be claimed by a new agent."""
    _signup_admin(client)
    a1 = _create_agent(client, slug="researcher")
    r = client.delete(f"/api/agents/{a1['id']}")
    assert r.status_code == 204

    # Same slug now available
    a2 = _create_agent(client, slug="researcher")
    assert a2["slug"] == "researcher"


def test_archived_agent_clears_default_flag(client: TestClient) -> None:
    """Archiving the default agent frees the default slot."""
    _signup_admin(client)
    a1 = _create_agent(client, slug="alfred", is_default=True)
    r = client.delete(f"/api/agents/{a1['id']}")
    assert r.status_code == 204

    # New agent can claim default
    a2 = _create_agent(client, slug="vanguard", is_default=True)
    assert a2["is_default"] is True


def test_cannot_edit_archived_agent(client: TestClient) -> None:
    _signup_admin(client)
    a = _create_agent(client, slug="ghost")
    client.delete(f"/api/agents/{a['id']}")
    r = client.patch(f"/api/agents/{a['id']}", json={"description": "new"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "archived"


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


def test_invalid_slug_rejected_by_pydantic(client: TestClient) -> None:
    _signup_admin(client)
    r = client.post(
        "/api/agents",
        json={
            "slug": "Bad Slug With Spaces",
            "anthropic_agent_id": "agent_001",
            "environment_id": "env_001",
        },
    )
    assert r.status_code == 422  # pydantic validator rejects before service


def test_uppercase_slug_normalized_to_lowercase(client: TestClient) -> None:
    """Slugs are case-insensitive — `Alfred` becomes `alfred`."""
    _signup_admin(client)
    r = client.post(
        "/api/agents",
        json={
            "slug": "Alfred",
            "anthropic_agent_id": "agent_001",
            "environment_id": "env_001",
        },
    )
    assert r.status_code == 201
    assert r.json()["slug"] == "alfred"


def test_slug_starting_with_digit_rejected(client: TestClient) -> None:
    _signup_admin(client)
    r = client.post(
        "/api/agents",
        json={
            "slug": "1alfred",
            "anthropic_agent_id": "agent_001",
            "environment_id": "env_001",
        },
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# 25-agent cap
# ---------------------------------------------------------------------------


def test_agent_limit_returns_409(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "relay_api.core.config.settings.RELAY_AGENTS_PER_WORKSPACE", 2
    )
    _signup_admin(client)
    _create_agent(client, slug="a")
    _create_agent(client, slug="b")
    r = client.post(
        "/api/agents",
        json={
            "slug": "c",
            "anthropic_agent_id": "agent_001",
            "environment_id": "env_001",
        },
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "agent_limit_reached"


def test_archived_agents_dont_count_toward_cap(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "relay_api.core.config.settings.RELAY_AGENTS_PER_WORKSPACE", 2
    )
    _signup_admin(client)
    a = _create_agent(client, slug="alpha")
    _create_agent(client, slug="beta")
    # At cap — archive alpha
    client.delete(f"/api/agents/{a['id']}")
    # Now under cap — can create another
    r = client.post(
        "/api/agents",
        json={
            "slug": "gamma",
            "anthropic_agent_id": "agent_001",
            "environment_id": "env_001",
        },
    )
    assert r.status_code == 201


# ---------------------------------------------------------------------------
# auth gates
# ---------------------------------------------------------------------------


def test_non_admin_cannot_create_or_modify(client: TestClient) -> None:
    admin = _signup_admin(client)
    agent = _create_agent(client, slug="alfred")
    # Downgrade
    with SessionLocal() as db:
        u = db.get(User, uuid.UUID(admin["user"]["id"]))
        u.role = "member"
        db.commit()

    # POST blocked
    r = client.post(
        "/api/agents",
        json={
            "slug": "newone",
            "anthropic_agent_id": "agent_001",
            "environment_id": "env_001",
        },
    )
    assert r.status_code == 403

    # PATCH blocked
    r = client.patch(f"/api/agents/{agent['id']}", json={"description": "x"})
    assert r.status_code == 403

    # DELETE blocked
    r = client.delete(f"/api/agents/{agent['id']}")
    assert r.status_code == 403

    # GET still works (read access)
    r = client.get("/api/agents")
    assert r.status_code == 200


def test_unauthenticated_requests_blocked(client: TestClient) -> None:
    r = client.get("/api/agents")
    assert r.status_code == 401
    r = client.post(
        "/api/agents",
        json={"slug": "x", "anthropic_agent_id": "a", "environment_id": "e"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# cross-workspace isolation
# ---------------------------------------------------------------------------


def test_other_workspaces_agents_invisible(client: TestClient) -> None:
    """A user can't see (or 404) agents from a different workspace."""
    _signup_admin(client)
    a = _create_agent(client, slug="secret")
    other_workspace_agent_id = a["id"]

    # Logout, signup as a different tenant
    client.post("/api/auth/logout")
    _signup_admin(client)

    # GET returns empty for this fresh tenant
    body = client.get("/api/agents").json()
    assert body["agents"] == []

    # Direct GET of the other workspace's agent ID → 404 (not 403; we don't
    # confirm it exists in any other tenant)
    r = client.get(f"/api/agents/{other_workspace_agent_id}")
    assert r.status_code == 404
