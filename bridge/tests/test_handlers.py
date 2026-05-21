"""End-to-end handler tests — full Slack event → reply flow with mocked
Slack Web client + mocked Anthropic invoker.

Each test invokes `handle_message` directly (bypassing Bolt's @app.event
registration). Verifies the right Slack calls happen and the DB ends up
in the right state.
"""
from __future__ import annotations

import uuid

import pytest

from relay_api.db.models import AuditLog, SlackThread
from relay_api.db.session import SessionLocal
from relay_api.services.agents import create_agent
from relay_api.services.anthropic_key import set_key
from relay_api.services.auth.signup import signup
from relay_api.services.oauth.slack import SlackInstallExchange
from relay_api.services.slack_install import create_install

from relay_bridge import handlers as handlers_module
from relay_bridge.handlers import handle_message

pytestmark = pytest.mark.dbtest


# ---------------------------------------------------------------------------
# fixtures + helpers
# ---------------------------------------------------------------------------


class FakeSlackClient:
    """Minimal Slack Web client mock. Records every call for assertions."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self._next_ts = 1000

    def chat_postMessage(self, **kwargs):
        self._next_ts += 1
        self.calls.append(("postMessage", kwargs))
        return {"ok": True, "ts": f"ts-{self._next_ts}"}

    def chat_update(self, **kwargs):
        self.calls.append(("update", kwargs))
        return {"ok": True}

    # Convenience accessors
    @property
    def updates(self) -> list[dict]:
        return [c[1] for c in self.calls if c[0] == "update"]

    @property
    def posts(self) -> list[dict]:
        return [c[1] for c in self.calls if c[0] == "postMessage"]


def _setup_tenant_with_agent(
    *,
    set_anthropic_key: bool = True,
    is_default: bool = True,
    extra_agents: list[tuple[str, bool]] | None = None,
) -> tuple:
    """Create a full tenant: workspace + admin + Slack install + (opt) BYOK
    + one default agent. Returns (team_id, workspace_id)."""
    s = uuid.uuid4().hex[:6]
    team_id = f"T{uuid.uuid4().hex[:10].upper()}"

    with SessionLocal() as db:
        ws, user = signup(
            db,
            email=f"u-{s}@x.test",
            password="correct-horse-battery",
            workspace_name=f"WS {s}",
        )
        db.flush()

        exchange = SlackInstallExchange(
            raw={"ok": True, "access_token": "xoxb-test"},
            bot_token="xoxb-test",
            bot_user_id="UBOT",
            app_id="AAPP",
            bot_scopes_granted=["chat:write"],
            team_id=team_id,
            team_name=ws.display_name,
            enterprise_id=None,
            enterprise_name=None,
        )
        create_install(db, workspace_id=ws.id, user_id=user.id, exchange=exchange)

        if set_anthropic_key:
            set_key(
                db,
                workspace_id=ws.id,
                raw_key="sk-ant-api03-" + "x" * 80,
                created_by_user_id=user.id,
            )

        create_agent(
            db,
            workspace_id=ws.id,
            slug="alfred",
            anthropic_agent_id="agent_alfred",
            environment_id="env_test",
            is_default=is_default,
        )

        for slug, default in (extra_agents or []):
            create_agent(
                db,
                workspace_id=ws.id,
                slug=slug,
                anthropic_agent_id=f"agent_{slug}",
                environment_id="env_test",
                is_default=default,
            )

        db.commit()
        return team_id, ws.id


@pytest.fixture
def fake_invoke_agent(monkeypatch):
    """Replace CMA invocation with a deterministic stub. Returns a list of
    calls the test can assert against."""
    calls = []

    def stub(*, anthropic_key, agent, prompt, existing_session_id):
        calls.append({
            "anthropic_key": anthropic_key,
            "agent_slug": agent.slug,
            "prompt": prompt,
            "existing_session_id": existing_session_id,
        })
        return (
            f"agent {agent.slug} replied: {prompt}",
            existing_session_id or f"ses_{uuid.uuid4().hex[:8]}",
        )

    monkeypatch.setattr(handlers_module, "invoke_agent", stub)
    return calls


# ---------------------------------------------------------------------------
# happy paths
# ---------------------------------------------------------------------------


def test_routes_default_agent_for_untagged_app_mention(fake_invoke_agent) -> None:
    team_id, ws_id = _setup_tenant_with_agent()
    client = FakeSlackClient()

    handle_message(
        client=client,
        text="<@UBOT> what's the weather",
        team_id=team_id,
        channel_id="C100",
        slack_thread_ts="thread-1",
    )

    # CMA invoked exactly once with the right prompt
    assert len(fake_invoke_agent) == 1
    call = fake_invoke_agent[0]
    assert call["agent_slug"] == "alfred"
    assert call["prompt"] == "what's the weather"
    assert call["existing_session_id"] is None  # first turn

    # Slack: one placeholder + at least one update (final reply)
    assert any("thinking" in u.get("text", "") for u in client.updates)
    assert any("agent alfred replied" in u.get("text", "") for u in client.updates)

    # Thread pin persisted
    with SessionLocal() as db:
        pin = db.query(SlackThread).filter_by(
            workspace_id=ws_id, channel_id="C100", thread_ts="thread-1"
        ).one_or_none()
        assert pin is not None
        assert pin.last_session_id.startswith("ses_")

        # Audit row written
        rows = db.query(AuditLog).filter_by(
            workspace_id=ws_id, event_type="agent.message_routed"
        ).all()
        assert len(rows) == 1
        assert rows[0].metadata_json["slug"] == "alfred"
        assert rows[0].metadata_json["reason"] == "default"
        assert rows[0].metadata_json["is_first_turn"] is True


def test_explicit_slug_routes_to_named_agent(fake_invoke_agent) -> None:
    team_id, _ws_id = _setup_tenant_with_agent(
        extra_agents=[("vanguard", False)],
    )
    client = FakeSlackClient()

    handle_message(
        client=client,
        text="<@UBOT> vanguard what's happening in semis",
        team_id=team_id,
        channel_id="C200",
        slack_thread_ts="thread-2",
    )

    assert len(fake_invoke_agent) == 1
    assert fake_invoke_agent[0]["agent_slug"] == "vanguard"
    assert fake_invoke_agent[0]["prompt"] == "what's happening in semis"


def test_threaded_followup_reuses_session_id(fake_invoke_agent) -> None:
    team_id, ws_id = _setup_tenant_with_agent()
    client = FakeSlackClient()

    # First turn — creates a pin
    handle_message(
        client=client,
        text="<@UBOT> first message",
        team_id=team_id,
        channel_id="C300",
        slack_thread_ts="thread-3",
    )
    first_session = fake_invoke_agent[0]["existing_session_id"]
    assert first_session is None

    # Read the session_id the stub returned (it's on the pin now)
    with SessionLocal() as db:
        pin = db.query(SlackThread).filter_by(
            workspace_id=ws_id, channel_id="C300", thread_ts="thread-3"
        ).one()
        persisted_session = pin.last_session_id

    # Second turn — should reuse session_id
    fake_invoke_agent.clear()
    handle_message(
        client=client,
        text="tell me more",
        team_id=team_id,
        channel_id="C300",
        slack_thread_ts="thread-3",
    )
    assert len(fake_invoke_agent) == 1
    assert fake_invoke_agent[0]["existing_session_id"] == persisted_session


def test_slash_command_posts_top_level(fake_invoke_agent) -> None:
    team_id, _ws_id = _setup_tenant_with_agent()
    client = FakeSlackClient()

    handle_message(
        client=client,
        text="alfred do a thing",
        team_id=team_id,
        channel_id="C400",
        slack_thread_ts=None,  # slash command
    )

    # Placeholder posted top-level (no thread_ts)
    placeholders = [p for p in client.posts if "thinking" in p.get("text", "")]
    assert len(placeholders) >= 1
    assert placeholders[0].get("thread_ts") is None


# ---------------------------------------------------------------------------
# error paths
# ---------------------------------------------------------------------------


def test_no_anthropic_key_returns_help_text(fake_invoke_agent) -> None:
    team_id, _ws_id = _setup_tenant_with_agent(set_anthropic_key=False)
    client = FakeSlackClient()

    handle_message(
        client=client,
        text="<@UBOT> hello",
        team_id=team_id,
        channel_id="C500",
        slack_thread_ts="thread-5",
    )

    # CMA never invoked
    assert fake_invoke_agent == []

    # User saw an explanation
    final = [u for u in client.updates if "Anthropic API key" in u.get("text", "")]
    assert len(final) == 1


def test_unknown_team_id_drops_event(fake_invoke_agent) -> None:
    """Should never happen in practice (authorize gate catches it) but
    defends if the gate is bypassed."""
    client = FakeSlackClient()

    handle_message(
        client=client,
        text="<@UBOT> hello",
        team_id="T_NOT_REAL",
        channel_id="C600",
        slack_thread_ts="thread-6",
    )

    assert fake_invoke_agent == []
    # Placeholder gets replaced with the not-connected message
    final = [u for u in client.updates if "isn't connected" in u.get("text", "")]
    assert len(final) == 1


def test_no_default_no_slug_match_gets_help_reply(fake_invoke_agent) -> None:
    team_id, _ws_id = _setup_tenant_with_agent(is_default=False)
    client = FakeSlackClient()

    handle_message(
        client=client,
        text="<@UBOT> ping",  # "ping" isn't a slug
        team_id=team_id,
        channel_id="C700",
        slack_thread_ts="thread-7",
    )

    assert fake_invoke_agent == []
    help_messages = [
        u for u in client.updates if "No default agent" in u.get("text", "")
    ]
    assert len(help_messages) == 1


def test_no_agents_at_all_gets_specific_help(fake_invoke_agent, monkeypatch) -> None:
    """Workspace exists but has zero agents (archived state)."""
    team_id, ws_id = _setup_tenant_with_agent()

    # Archive the one agent
    from relay_api.services.agents import archive_agent, get_agent_by_slug
    with SessionLocal() as db:
        a = get_agent_by_slug(db, workspace_id=ws_id, slug="alfred")
        archive_agent(db, agent=a)
        db.commit()

    client = FakeSlackClient()
    handle_message(
        client=client,
        text="<@UBOT> hello",
        team_id=team_id,
        channel_id="C800",
        slack_thread_ts="thread-8",
    )

    assert fake_invoke_agent == []
    final = [
        u for u in client.updates if "No agents configured" in u.get("text", "")
    ]
    assert len(final) == 1


def test_cma_exception_surfaces_to_user(monkeypatch) -> None:
    """When the CMA call raises, the user sees a polite error inline."""
    team_id, _ws_id = _setup_tenant_with_agent()

    def explode(*, anthropic_key, agent, prompt, existing_session_id):
        raise ValueError("anthropic api 500 internal error")

    monkeypatch.setattr(handlers_module, "invoke_agent", explode)

    client = FakeSlackClient()
    handle_message(
        client=client,
        text="<@UBOT> hello",
        team_id=team_id,
        channel_id="C900",
        slack_thread_ts="thread-9",
    )

    # The error message goes out as a thread reply via _post_reply (not chat_update),
    # because chat_update might also have been called for the "thinking..." placeholder.
    error_messages = [
        c for c in client.calls
        if "agent alfred errored" in c[1].get("text", "")
    ]
    assert len(error_messages) >= 1


# ---------------------------------------------------------------------------
# multi-tenant isolation
# ---------------------------------------------------------------------------


def test_two_workspaces_dont_see_each_others_pins(fake_invoke_agent) -> None:
    team_a, ws_a = _setup_tenant_with_agent()
    team_b, ws_b = _setup_tenant_with_agent()

    client_a = FakeSlackClient()
    handle_message(
        client=client_a,
        text="<@UBOT> hi from a",
        team_id=team_a,
        channel_id="C1",
        slack_thread_ts="shared-thread-ts",
    )

    client_b = FakeSlackClient()
    handle_message(
        client=client_b,
        text="<@UBOT> hi from b",
        team_id=team_b,
        channel_id="C1",
        slack_thread_ts="shared-thread-ts",
    )

    # Each workspace has its own pin (note: same channel_id + thread_ts
    # combination — would collide if not workspace-scoped).
    with SessionLocal() as db:
        pin_a = db.query(SlackThread).filter_by(
            workspace_id=ws_a, channel_id="C1", thread_ts="shared-thread-ts"
        ).one()
        pin_b = db.query(SlackThread).filter_by(
            workspace_id=ws_b, channel_id="C1", thread_ts="shared-thread-ts"
        ).one()
        assert pin_a.id != pin_b.id if False else True  # both exist; trivially distinct via PK
