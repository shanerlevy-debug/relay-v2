"""Tenant resolver tests against a live Postgres."""
from __future__ import annotations

import uuid

import pytest

from relay_api.db.session import SessionLocal
from relay_api.services.anthropic_key import set_key
from relay_api.services.auth.signup import signup
from relay_api.services.slack_install import create_install
from relay_api.services.oauth.slack import SlackInstallExchange

from relay_bridge.tenant import resolve_tenant

pytestmark = pytest.mark.dbtest


def _make_exchange(team_id: str) -> SlackInstallExchange:
    return SlackInstallExchange(
        raw={"ok": True, "access_token": "xoxb-bridge-test-token"},
        bot_token="xoxb-bridge-test-token",
        bot_user_id="UTESTBOT",
        app_id="ATESTAPP",
        bot_scopes_granted=["chat:write"],
        team_id=team_id,
        team_name="Bridge Test Workspace",
        enterprise_id=None,
        enterprise_name=None,
    )


def test_resolve_for_unknown_team_returns_none() -> None:
    with SessionLocal() as db:
        ctx = resolve_tenant(db, team_id="T_DEFINITELY_NOT_REAL")
        assert ctx is None


def test_resolve_returns_workspace_install_and_keys() -> None:
    with SessionLocal() as db:
        s = uuid.uuid4().hex[:6]
        ws, admin = signup(
            db,
            email=f"u-{s}@x.test",
            password="correct-horse-battery",
            workspace_name=f"WS {s}",
        )
        db.flush()
        team_id = f"T{uuid.uuid4().hex[:10].upper()}"
        create_install(
            db, workspace_id=ws.id, user_id=admin.id, exchange=_make_exchange(team_id)
        )
        db.commit()

        ctx = resolve_tenant(db, team_id=team_id)
        assert ctx is not None
        assert ctx.workspace.id == ws.id
        assert ctx.bot_token == "xoxb-bridge-test-token"
        assert ctx.install.bot_user_id == "UTESTBOT"
        assert ctx.anthropic_key is None  # no key set yet


def test_resolve_decrypts_anthropic_key_when_present() -> None:
    with SessionLocal() as db:
        s = uuid.uuid4().hex[:6]
        ws, admin = signup(
            db,
            email=f"u-{s}@x.test",
            password="correct-horse-battery",
            workspace_name=f"WS {s}",
        )
        db.flush()
        team_id = f"T{uuid.uuid4().hex[:10].upper()}"
        create_install(
            db, workspace_id=ws.id, user_id=admin.id, exchange=_make_exchange(team_id)
        )
        set_key(
            db,
            workspace_id=ws.id,
            raw_key="sk-ant-api03-" + "z" * 80,
            created_by_user_id=admin.id,
        )
        db.commit()

        ctx = resolve_tenant(db, team_id=team_id)
        assert ctx is not None
        assert ctx.anthropic_key is not None
        assert ctx.anthropic_key.startswith("sk-ant-")
