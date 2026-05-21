"""End-to-end invite + user-management tests via TestClient.

Covers the happy path (admin invites → invitee accepts → logged in →
visible in user list) AND every documented error code so the UI can
trust the error contract.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from relay_api.core.config import settings
from relay_api.db.models import Invite, User
from relay_api.db.session import SessionLocal
from relay_api.main import app

pytestmark = pytest.mark.dbtest


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _signup_admin(client: TestClient, *, password: str = "correct-horse-battery") -> dict:
    """Sign up a fresh workspace + admin user. Returns the signup body."""
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "email": f"admin-{suffix}@acme.test",
        "password": password,
        "workspace_name": f"Acme {suffix}",
    }
    r = client.post("/api/auth/signup", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    body["_password"] = password
    return body


def _invite(client: TestClient, *, email: str | None = None, role: str = "member") -> dict:
    """Send an invite as the currently-logged-in admin."""
    payload = {
        "email": email or f"invitee-{uuid.uuid4().hex[:8]}@acme.test",
        "role": role,
    }
    r = client.post("/api/users/invite", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_full_invite_and_accept_flow(client: TestClient) -> None:
    """Admin signs up → invites teammate → teammate accepts → logged in as member."""
    admin = _signup_admin(client)
    workspace_id = admin["workspace"]["id"]

    # Admin creates invite
    invitee_email = f"teammate-{uuid.uuid4().hex[:8]}@acme.test"
    invite_body = _invite(client, email=invitee_email, role="member")
    assert invite_body["invite"]["email"] == invitee_email
    assert invite_body["invite"]["role"] == "member"
    assert invite_body["invite_url"].startswith(settings.RELAY_APP_BASE_URL)

    # Extract the raw token from the URL — the only place it appears
    raw_token = invite_body["invite_url"].rsplit("/", 1)[-1]

    # Admin logs out so we test invite acceptance as an unauthenticated user
    client.post("/api/auth/logout")
    assert client.get("/api/me").status_code == 401

    # Public lookup of the invite (the accept-invite page would do this on load)
    r = client.get(f"/api/invites/{raw_token}")
    assert r.status_code == 200
    public = r.json()
    assert public["email"] == invitee_email
    assert public["role"] == "member"
    assert public["workspace_display_name"] == admin["workspace"]["display_name"]

    # Accept
    r = client.post(
        f"/api/invites/{raw_token}/accept",
        json={"password": "another-good-password-here"},
    )
    assert r.status_code == 200, r.text
    new_member = r.json()
    assert new_member["user"]["email"] == invitee_email
    assert new_member["user"]["role"] == "member"
    assert new_member["workspace"]["id"] == workspace_id

    # Now logged in as the new member
    r = client.get("/api/me")
    assert r.status_code == 200
    assert r.json()["user"]["email"] == invitee_email

    # The invite token is single-use
    client.post("/api/auth/logout")
    r2 = client.post(
        f"/api/invites/{raw_token}/accept",
        json={"password": "another-good-password-here"},
    )
    assert r2.status_code == 410
    assert r2.json()["error"]["code"] == "already_accepted"


def test_non_admin_cannot_invite(client: TestClient) -> None:
    """Members can't invite — only admins."""
    admin = _signup_admin(client)
    # Downgrade the admin to member
    with SessionLocal() as db:
        u = db.get(User, uuid.UUID(admin["user"]["id"]))
        u.role = "member"
        db.commit()

    r = client.post(
        "/api/users/invite",
        json={"email": "x@acme.test", "role": "member"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "admin_required"


def test_invite_requires_session(client: TestClient) -> None:
    r = client.post(
        "/api/users/invite",
        json={"email": "x@acme.test", "role": "member"},
    )
    assert r.status_code == 401


def test_list_users_shows_admin_and_seats(client: TestClient) -> None:
    admin = _signup_admin(client)
    r = client.get("/api/users")
    assert r.status_code == 200
    body = r.json()
    assert len(body["users"]) == 1
    assert body["users"][0]["email"] == admin["user"]["email"]
    assert body["seats"]["active"] == 1
    assert body["seats"]["pending_invites"] == 0
    assert body["seats"]["cap"] == settings.RELAY_USERS_PER_WORKSPACE


def test_seats_count_invites_too(client: TestClient) -> None:
    _signup_admin(client)
    _invite(client, email="a@acme.test")
    _invite(client, email="b@acme.test")
    body = client.get("/api/users").json()
    assert body["seats"]["active"] == 1
    assert body["seats"]["pending_invites"] == 2


# ---------------------------------------------------------------------------
# 25-user cap
# ---------------------------------------------------------------------------


def test_user_limit_blocks_invite_at_cap(client: TestClient, monkeypatch) -> None:
    """At the cap, /invite returns 409 user_limit_reached."""
    # Lower the cap for the test rather than creating 24 invite rows.
    monkeypatch.setattr(
        "relay_api.core.config.settings.RELAY_USERS_PER_WORKSPACE", 3
    )
    _signup_admin(client)  # active = 1, cap = 3
    _invite(client, email="b@acme.test")  # pending = 1, total = 2
    _invite(client, email="c@acme.test")  # pending = 2, total = 3 (== cap)

    r = client.post(
        "/api/users/invite",
        json={"email": "d@acme.test", "role": "member"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "user_limit_reached"


def test_revoked_invite_releases_seat(client: TestClient, monkeypatch) -> None:
    """Expiring an invite frees a seat for a new one."""
    monkeypatch.setattr(
        "relay_api.core.config.settings.RELAY_USERS_PER_WORKSPACE", 2
    )
    _signup_admin(client)  # active = 1
    body = _invite(client, email="b@acme.test")  # pending = 1, total = 2 (== cap)
    raw_token = body["invite_url"].rsplit("/", 1)[-1]

    # At cap — next invite blocked
    blocked = client.post(
        "/api/users/invite",
        json={"email": "c@acme.test", "role": "member"},
    )
    assert blocked.status_code == 409

    # Manually expire the first invite (revoke flow is admin-side)
    with SessionLocal() as db:
        inv = db.execute(
            Invite.__table__.select().where(
                Invite.token_hash
                == _hash_token(raw_token)
            )
        ).first()
        inv_id = uuid.UUID(str(inv._mapping["id"]))
        db.execute(
            Invite.__table__.update().where(Invite.id == inv_id).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1)
            )
        )
        db.commit()

    # Now the seat is free
    r = client.post(
        "/api/users/invite",
        json={"email": "c@acme.test", "role": "member"},
    )
    assert r.status_code == 201


def _hash_token(raw: str) -> bytes:
    import hashlib
    return hashlib.sha256(raw.encode("utf-8")).digest()


# ---------------------------------------------------------------------------
# edge cases
# ---------------------------------------------------------------------------


def test_duplicate_invite_blocked(client: TestClient) -> None:
    """Re-inviting the same email while a pending invite exists → 409."""
    _signup_admin(client)
    _invite(client, email="dup@acme.test")
    r = client.post(
        "/api/users/invite",
        json={"email": "dup@acme.test", "role": "member"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "invite_already_pending"


def test_inviting_existing_user_email_blocked(client: TestClient) -> None:
    """Can't invite an email that's already a registered user anywhere."""
    admin_a = _signup_admin(client)
    existing_email = admin_a["user"]["email"]
    # Logout, signup a different admin in a different workspace
    client.post("/api/auth/logout")
    _signup_admin(client)
    # Try to invite the OTHER admin
    r = client.post(
        "/api/users/invite",
        json={"email": existing_email, "role": "member"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_in_use"


def test_get_invite_with_bad_token_404s(client: TestClient) -> None:
    r = client.get("/api/invites/this-token-does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_accept_with_short_password_400s(client: TestClient) -> None:
    _signup_admin(client)
    body = _invite(client, email="invitee@acme.test")
    raw_token = body["invite_url"].rsplit("/", 1)[-1]
    client.post("/api/auth/logout")
    r = client.post(
        f"/api/invites/{raw_token}/accept",
        json={"password": "short"},
    )
    # 422 from pydantic min_length=12 in AcceptInviteRequest
    assert r.status_code == 422


def test_expired_invite_410(client: TestClient) -> None:
    _signup_admin(client)
    body = _invite(client, email="expiring@acme.test")
    raw_token = body["invite_url"].rsplit("/", 1)[-1]

    # Expire it manually
    with SessionLocal() as db:
        inv = db.execute(
            Invite.__table__.select().where(
                Invite.token_hash == _hash_token(raw_token)
            )
        ).first()
        inv_id = uuid.UUID(str(inv._mapping["id"]))
        db.execute(
            Invite.__table__.update().where(Invite.id == inv_id).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1)
            )
        )
        db.commit()

    client.post("/api/auth/logout")
    r = client.get(f"/api/invites/{raw_token}")
    assert r.status_code == 410
    assert r.json()["error"]["code"] == "expired"


# ---------------------------------------------------------------------------
# user deletion
# ---------------------------------------------------------------------------


def test_admin_can_remove_member(client: TestClient) -> None:
    admin = _signup_admin(client)
    body = _invite(client, email="member@acme.test")
    raw_token = body["invite_url"].rsplit("/", 1)[-1]

    # Member accepts (separate session)
    client.post("/api/auth/logout")
    r = client.post(
        f"/api/invites/{raw_token}/accept",
        json={"password": "another-secure-password"},
    )
    assert r.status_code == 200
    member_user_id = r.json()["user"]["id"]
    client.post("/api/auth/logout")

    # Admin logs back in
    client.post(
        "/api/auth/login",
        json={"email": admin["user"]["email"], "password": admin["_password"]},
    )

    # And removes the member
    r = client.delete(f"/api/users/{member_user_id}")
    assert r.status_code == 204

    # User list now shows only the admin
    body = client.get("/api/users").json()
    assert len(body["users"]) == 1
    assert body["users"][0]["id"] == admin["user"]["id"]


def test_admin_cannot_self_delete(client: TestClient) -> None:
    admin = _signup_admin(client)
    r = client.delete(f"/api/users/{admin['user']['id']}")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "self_delete"


def test_last_admin_guard_at_service_level() -> None:
    """Direct service test of the last-admin guard — avoids HTTP-flow
    contortions while still proving the invariant: a workspace must always
    have at least one admin.
    """
    from relay_api.services.auth.signup import signup
    from relay_api.services.user_mgmt import UserMgmtError, delete_user

    s = uuid.uuid4().hex[:6]
    with SessionLocal() as db:
        ws, admin1 = signup(
            db,
            email=f"a1-{s}@x.test",
            password="correct-horse-battery",
            workspace_name=f"WS {s}",
        )
        # Add a second admin directly
        admin2 = User(
            workspace_id=ws.id,
            email=f"a2-{s}@x.test",
            password_hash="not-a-real-hash",
            role="admin",
        )
        db.add(admin2)
        db.flush()

        # Add a member (not an admin)
        member = User(
            workspace_id=ws.id,
            email=f"m-{s}@x.test",
            password_hash="not-a-real-hash",
            role="member",
        )
        db.add(member)
        db.flush()

        # admin1 deletes admin2 → fine, admin1 remains
        delete_user(db, workspace_id=ws.id, user_id=admin2.id, actor_user_id=admin1.id)
        db.flush()

        # admin1 deletes the member → fine, admin1 still the admin
        delete_user(db, workspace_id=ws.id, user_id=member.id, actor_user_id=admin1.id)
        db.flush()

        # Now admin1 is the only admin. Bring in a second admin so admin1
        # has someone to try (and fail) to delete via the last-admin path.
        admin3 = User(
            workspace_id=ws.id,
            email=f"a3-{s}@x.test",
            password_hash="not-a-real-hash",
            role="admin",
        )
        db.add(admin3)
        db.flush()

        # Soft-delete admin1. Should succeed — admin3 still around.
        delete_user(db, workspace_id=ws.id, user_id=admin1.id, actor_user_id=admin3.id)
        db.flush()

        # Now admin3 is the only admin. Trying to delete admin3 with admin3
        # as actor is `self_delete` (covered separately). But trying with a
        # non-existent actor would still be blocked by `last_admin` IF the
        # actor weren't the same as the target. Since we don't have another
        # admin to act, simulate by inviting a freshly-created OTHER admin
        # then immediately trying to delete admin3 from their perspective.
        admin4 = User(
            workspace_id=ws.id,
            email=f"a4-{s}@x.test",
            password_hash="not-a-real-hash",
            role="member",  # not an admin yet
        )
        db.add(admin4)
        db.flush()

        # Member admin4 cannot be the actor for delete (require_admin gate
        # is HTTP-layer, not service-layer). But we're testing the service.
        # The service trusts the caller did the admin check. We're testing
        # the last_admin guard specifically: deleting admin3 when admin3 is
        # the only admin should fail regardless of actor.
        with pytest.raises(UserMgmtError) as exc:
            delete_user(
                db,
                workspace_id=ws.id,
                user_id=admin3.id,
                actor_user_id=admin4.id,
            )
        assert exc.value.code == "last_admin"
