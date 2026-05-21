"""Tests for the Slack OAuth install flow.

Three tiers:

1. `services/slack_install.py` tests — direct DB calls, no HTTP. Cover
   collision cases (team_already_connected, workspace_has_active_install)
   and the roundtrip through envelope encryption.

2. `services/oauth/slack.py` tests — pure URL-building + state cookie
   round-trip. No httpx involved.

3. Route-level tests — full HTTP cycle through TestClient. SlackProvider.
   exchange_code is monkey-patched to return a canned `SlackInstallExchange`
   so we don't need to mock httpx or hit real Slack.
"""
from __future__ import annotations

import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from relay_api.db.models import AuditLog, User, WorkspaceSlackInstall
from relay_api.db.session import SessionLocal
from relay_api.main import app
from relay_api.services.oauth.base import (
    OAUTH_STATE_COOKIE,
    deserialize_state,
)
from relay_api.services.oauth.slack import (
    AUTHORIZE_URL,
    SlackInstallExchange,
    SlackProvider,
)
from relay_api.services.slack_install import (
    SlackInstallError,
    create_install,
    decrypt_bot_token,
    find_by_team_id,
    get_active_install,
    revoke,
)

pytestmark = pytest.mark.dbtest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _signup_and_login(client: TestClient) -> dict:
    """Sign up a fresh workspace+admin, return the parsed /me response."""
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "email": f"admin-{suffix}@acme.test",
        "password": "correct-horse-battery-staple",
        "workspace_name": f"Acme {suffix}",
    }
    r = client.post("/api/auth/signup", json=payload)
    assert r.status_code == 201, r.text
    me = client.get("/api/me").json()
    me["_password"] = payload["password"]
    return me


def _make_exchange(*, team_id: str | None = None) -> SlackInstallExchange:
    return SlackInstallExchange(
        raw={"ok": True, "access_token": "xoxb-test-token-here"},
        bot_token="xoxb-test-token-here",
        bot_user_id="U0BOT",
        app_id="A0APP",
        bot_scopes_granted=["chat:write", "channels:history"],
        team_id=team_id or f"T{uuid.uuid4().hex[:10].upper()}",
        team_name="Acme Slack",
        enterprise_id=None,
        enterprise_name=None,
    )


# ---------------------------------------------------------------------------
# 1. service-layer tests (direct DB)
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def test_create_install_roundtrip(db, monkeypatch) -> None:
    """Bot token is encrypted at rest and decrypts back to the original."""
    suffix = uuid.uuid4().hex[:8]
    from relay_api.services.auth.signup import signup

    workspace, user = signup(
        db,
        email=f"u-{suffix}@acme.test",
        password="correct-horse-battery",
        workspace_name=f"WS {suffix}",
    )
    db.flush()

    exchange = _make_exchange()
    install = create_install(
        db,
        workspace_id=workspace.id,
        user_id=user.id,
        exchange=exchange,
    )
    db.flush()

    assert install.id is not None
    assert install.workspace_id == workspace.id
    assert install.slack_team_id == exchange.team_id
    assert install.bot_token_nonce != install.bot_token_ct  # they're different bytes

    # Decrypts back to plaintext
    plaintext = decrypt_bot_token(install)
    assert plaintext == "xoxb-test-token-here"

    # Workspace gets the denormalized team_id
    db.refresh(workspace)
    assert workspace.slack_team_id == exchange.team_id


def test_team_already_connected_blocks_install(db) -> None:
    """Two different workspaces can't both have the same Slack team active."""
    from relay_api.services.auth.signup import signup

    s = uuid.uuid4().hex[:6]
    ws_a, user_a = signup(db, email=f"a-{s}@x.test", password="correct-horse-battery", workspace_name=f"A {s}")
    ws_b, user_b = signup(db, email=f"b-{s}@x.test", password="correct-horse-battery", workspace_name=f"B {s}")
    db.flush()

    team_id = f"T{uuid.uuid4().hex[:10].upper()}"
    create_install(db, workspace_id=ws_a.id, user_id=user_a.id, exchange=_make_exchange(team_id=team_id))
    db.flush()

    with pytest.raises(SlackInstallError) as exc_info:
        create_install(
            db,
            workspace_id=ws_b.id,
            user_id=user_b.id,
            exchange=_make_exchange(team_id=team_id),
        )
    assert exc_info.value.code == "team_already_connected"


def test_workspace_cannot_double_install(db) -> None:
    """One workspace can't have two active installs at once."""
    from relay_api.services.auth.signup import signup

    s = uuid.uuid4().hex[:6]
    ws, user = signup(db, email=f"x-{s}@x.test", password="correct-horse-battery", workspace_name=f"X {s}")
    db.flush()

    create_install(db, workspace_id=ws.id, user_id=user.id, exchange=_make_exchange())
    db.flush()

    with pytest.raises(SlackInstallError) as exc_info:
        create_install(db, workspace_id=ws.id, user_id=user.id, exchange=_make_exchange())
    assert exc_info.value.code == "workspace_has_active_install"


def test_revoke_releases_team_id_for_future_install(db) -> None:
    """After revoke, the same team_id can be installed again (same or different ws)."""
    from relay_api.services.auth.signup import signup

    s = uuid.uuid4().hex[:6]
    ws, user = signup(db, email=f"r-{s}@x.test", password="correct-horse-battery", workspace_name=f"R {s}")
    db.flush()

    team_id = f"T{uuid.uuid4().hex[:10].upper()}"
    install = create_install(db, workspace_id=ws.id, user_id=user.id, exchange=_make_exchange(team_id=team_id))
    db.flush()

    revoke(db, install=install)
    db.flush()

    # Workspace's denormalized team_id was cleared
    db.refresh(ws)
    assert ws.slack_team_id is None

    # Same workspace can install again
    new_install = create_install(db, workspace_id=ws.id, user_id=user.id, exchange=_make_exchange(team_id=team_id))
    db.flush()
    assert new_install.id != install.id


def test_find_by_team_id_is_active_only(db) -> None:
    """The bridge's lookup path: team_id → install (skipping revoked rows)."""
    from relay_api.services.auth.signup import signup

    s = uuid.uuid4().hex[:6]
    ws, user = signup(db, email=f"f-{s}@x.test", password="correct-horse-battery", workspace_name=f"F {s}")
    db.flush()

    team_id = f"T{uuid.uuid4().hex[:10].upper()}"
    install = create_install(db, workspace_id=ws.id, user_id=user.id, exchange=_make_exchange(team_id=team_id))
    db.flush()

    found = find_by_team_id(db, slack_team_id=team_id)
    assert found is not None and found.id == install.id

    revoke(db, install=install)
    db.flush()

    after = find_by_team_id(db, slack_team_id=team_id)
    assert after is None


# ---------------------------------------------------------------------------
# 2. SlackProvider.start_install — URL + state cookie round-trip
# ---------------------------------------------------------------------------


def test_start_install_builds_correct_url(monkeypatch) -> None:
    """Authorize URL has all the required params; state cookie round-trips."""
    monkeypatch.setattr(
        "relay_api.core.config.settings.OAUTH_SLACK_CLIENT_ID",
        "fake-slack-client-id",
    )
    p = SlackProvider()
    workspace_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    result = p.start_install(
        redirect_uri="https://relayed.live/api/oauth/slack/callback",
        workspace_id=workspace_id,
        user_id=user_id,
    )

    parsed = urlparse(result.authorization_url)
    assert parsed.netloc == "slack.com"
    assert parsed.path == "/oauth/v2/authorize"
    qs = parse_qs(parsed.query)
    assert qs["client_id"] == ["fake-slack-client-id"]
    assert qs["redirect_uri"] == ["https://relayed.live/api/oauth/slack/callback"]
    assert "state" in qs and qs["state"][0]
    assert "scope" in qs

    # State cookie round-trips with the workspace + user
    payload = deserialize_state(result.state_cookie_value)
    assert payload["workspace_id"] == workspace_id
    assert payload["user_id"] == user_id
    assert payload["nonce"] == qs["state"][0]


# ---------------------------------------------------------------------------
# 3. Route-level tests via TestClient
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    """Configured client with a fake Slack client id so /start succeeds."""
    monkeypatch.setattr(
        "relay_api.core.config.settings.OAUTH_SLACK_CLIENT_ID",
        "fake-slack-client-id",
    )
    monkeypatch.setattr(
        "relay_api.core.config.settings.OAUTH_SLACK_CLIENT_SECRET",
        "fake-slack-client-secret",
    )
    with TestClient(app) as c:
        yield c


def test_start_requires_session(client: TestClient) -> None:
    r = client.get("/api/oauth/slack/start", follow_redirects=False)
    assert r.status_code == 401


def test_start_returns_redirect_to_slack_with_state_cookie(client: TestClient) -> None:
    _signup_and_login(client)

    r = client.get("/api/oauth/slack/start", follow_redirects=False)
    assert r.status_code == 303
    location = r.headers["location"]
    assert location.startswith(AUTHORIZE_URL)
    assert "relay_oauth_state" in r.cookies


def test_callback_with_bad_state_redirects_with_error(client: TestClient) -> None:
    """No cookie → ?slack_install=error&code=no_state_cookie."""
    r = client.get(
        "/api/oauth/slack/callback",
        params={"code": "abc", "state": "xyz"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    loc = urlparse(r.headers["location"])
    qs = parse_qs(loc.query)
    assert qs["slack_install"] == ["error"]
    assert qs["code"] == ["no_state_cookie"]


def test_callback_with_slack_error_short_circuits(client: TestClient) -> None:
    """If Slack itself returned ?error=access_denied, we redirect immediately."""
    r = client.get(
        "/api/oauth/slack/callback",
        params={"error": "access_denied"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    loc = urlparse(r.headers["location"])
    qs = parse_qs(loc.query)
    assert qs["slack_install"] == ["error"]
    assert qs["code"] == ["slack_access_denied"]


def test_full_install_happy_path(client: TestClient, monkeypatch) -> None:
    """End-to-end: start → mock the exchange → callback → DB row created + audit log entry."""
    me = _signup_and_login(client)
    workspace_id = uuid.UUID(me["workspace"]["id"])
    user_id = uuid.UUID(me["user"]["id"])

    # Drive /start, capture the state cookie that gets set
    start_resp = client.get("/api/oauth/slack/start", follow_redirects=False)
    assert start_resp.status_code == 303
    # TestClient's cookie jar already holds the cookie; pull it for the state nonce
    state_cookie_value = client.cookies.get(OAUTH_STATE_COOKIE)
    assert state_cookie_value
    state_payload = deserialize_state(state_cookie_value)
    nonce = state_payload["nonce"]

    # Stub the Slack code exchange
    canned_exchange = _make_exchange()

    async def fake_exchange_code(self, *, code, redirect_uri):
        assert code == "fake-auth-code"
        return canned_exchange

    monkeypatch.setattr(SlackProvider, "exchange_code", fake_exchange_code)

    # Hit /callback like Slack would
    cb_resp = client.get(
        "/api/oauth/slack/callback",
        params={"code": "fake-auth-code", "state": nonce},
        follow_redirects=False,
    )
    assert cb_resp.status_code == 303
    loc = urlparse(cb_resp.headers["location"])
    qs = parse_qs(loc.query)
    assert qs["slack_install"] == ["ok"], f"unexpected redirect: {cb_resp.headers['location']}"

    # DB row exists
    with SessionLocal() as db:
        install = get_active_install(db, workspace_id=workspace_id)
        assert install is not None
        assert install.slack_team_id == canned_exchange.team_id
        assert install.installed_by_user_id == user_id
        assert decrypt_bot_token(install) == "xoxb-test-token-here"

        # Audit log entry
        log_row = db.execute(
            AuditLog.__table__.select().where(
                AuditLog.workspace_id == workspace_id
            ).order_by(AuditLog.occurred_at.desc()).limit(1)
        ).first()
        assert log_row is not None
        log = log_row._mapping
        assert log["event_type"] == "workspace.slack_installed"
        assert log["metadata_json"]["slack_team_id"] == canned_exchange.team_id


def test_callback_state_mismatch_rejected(client: TestClient) -> None:
    """A valid signed cookie but mismatched ?state= query is rejected."""
    _signup_and_login(client)
    # Get a valid state cookie by hitting /start
    client.get("/api/oauth/slack/start", follow_redirects=False)
    # Hit /callback with a tampered state query value
    r = client.get(
        "/api/oauth/slack/callback",
        params={"code": "abc", "state": "not-the-nonce"},
        follow_redirects=False,
    )
    qs = parse_qs(urlparse(r.headers["location"]).query)
    assert qs["code"] == ["state_mismatch"]


def test_non_admin_cannot_start_install(client: TestClient, monkeypatch) -> None:
    """A workspace member (non-admin) gets 403 on /start."""
    _signup_and_login(client)
    # Downgrade the user to member
    with SessionLocal() as db:
        me_resp = client.get("/api/me").json()
        user = db.get(User, uuid.UUID(me_resp["user"]["id"]))
        user.role = "member"
        db.commit()

    r = client.get("/api/oauth/slack/start", follow_redirects=False)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "admin_required"
