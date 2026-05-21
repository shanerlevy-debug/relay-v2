"""End-to-end auth flow tests via FastAPI TestClient.

Covers the polished happy path AND the failure modes a real client will
hit. Every assertion has a corresponding UX implication — when a test
fails, fix BOTH the API and the docs that promise the behavior.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from relay_api.main import app

pytestmark = pytest.mark.dbtest


@pytest.fixture
def client():
    """Fresh client per test — cookies don't leak across cases."""
    with TestClient(app) as c:
        yield c


def _signup_payload(*, email: str | None = None, ws: str | None = None) -> dict:
    suffix = uuid.uuid4().hex[:8]
    return {
        "email": email or f"founder-{suffix}@acme.test",
        "password": "correct-horse-battery-staple",
        "workspace_name": ws or f"Acme {suffix}",
    }


def test_signup_creates_workspace_and_returns_session(client: TestClient) -> None:
    payload = _signup_payload()
    resp = client.post("/api/auth/signup", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["user"]["email"] == payload["email"]
    assert body["user"]["role"] == "admin"
    assert body["workspace"]["display_name"] == payload["workspace_name"]
    # Session cookie set
    assert "relay_session" in resp.cookies


def test_signup_rejects_short_password(client: TestClient) -> None:
    payload = _signup_payload()
    payload["password"] = "short"
    resp = client.post("/api/auth/signup", json=payload)
    # 422 from pydantic field validator (min_length=12 in SignupRequest)
    assert resp.status_code == 422


def test_signup_rejects_invalid_email(client: TestClient) -> None:
    payload = _signup_payload()
    payload["email"] = "not-an-email"
    resp = client.post("/api/auth/signup", json=payload)
    assert resp.status_code == 422


def test_duplicate_email_returns_409(client: TestClient) -> None:
    p = _signup_payload()
    r1 = client.post("/api/auth/signup", json=p)
    assert r1.status_code == 201

    # Second signup with same email — different workspace name
    p2 = dict(p)
    p2["workspace_name"] = "Acme Mark Two"
    r2 = client.post("/api/auth/signup", json=p2)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "email_in_use"


def test_me_requires_session(client: TestClient) -> None:
    resp = client.get("/api/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "not_authenticated"


def test_full_signup_login_logout_cycle(client: TestClient) -> None:
    payload = _signup_payload()

    # 1. Signup
    r1 = client.post("/api/auth/signup", json=payload)
    assert r1.status_code == 201

    # 2. /api/me works while signed in
    r2 = client.get("/api/me")
    assert r2.status_code == 200
    assert r2.json()["user"]["email"] == payload["email"]

    # 3. Logout clears the cookie
    r3 = client.post("/api/auth/logout")
    assert r3.status_code == 200
    # The cookie name is set by Set-Cookie with max-age=0 / Expires in the past
    # TestClient honors the delete by removing the cookie from its jar
    r4 = client.get("/api/me")
    assert r4.status_code == 401

    # 4. Login back in
    r5 = client.post(
        "/api/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert r5.status_code == 200, r5.text
    assert r5.json()["user"]["email"] == payload["email"]

    # 5. /api/me works again
    r6 = client.get("/api/me")
    assert r6.status_code == 200


def test_login_wrong_password_returns_401(client: TestClient) -> None:
    payload = _signup_payload()
    r = client.post("/api/auth/signup", json=payload)
    assert r.status_code == 201
    client.post("/api/auth/logout")

    bad = client.post(
        "/api/auth/login",
        json={"email": payload["email"], "password": "wrong-password-here"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_credentials"


def test_login_unknown_email_returns_401(client: TestClient) -> None:
    """Same error code as wrong-password — never leaks which emails are
    registered."""
    resp = client.post(
        "/api/auth/login",
        json={"email": "nobody@nowhere.test", "password": "anything-12-chars"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


def test_tampered_cookie_returns_401(client: TestClient) -> None:
    """Forging a session cookie with garbage value should not authenticate."""
    client.cookies.set("relay_session", "not-a-valid-jwt")
    resp = client.get("/api/me")
    assert resp.status_code == 401
