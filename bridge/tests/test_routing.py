"""Routing tests — slug -> agent precedence + thread pin upsert."""
from __future__ import annotations

import uuid

import pytest

from relay_api.db.session import SessionLocal
from relay_api.services.agents import archive_agent, create_agent
from relay_api.services.auth.signup import signup

from relay_bridge.routing import route_message, upsert_thread_pin

pytestmark = pytest.mark.dbtest


def _setup_workspace() -> tuple:
    """Helper: signup + return (workspace_id, admin_user_id) after commit."""
    s = uuid.uuid4().hex[:6]
    with SessionLocal() as db:
        ws, user = signup(
            db,
            email=f"u-{s}@x.test",
            password="correct-horse-battery",
            workspace_name=f"WS {s}",
        )
        db.commit()
        return ws.id, user.id


# ---------------------------------------------------------------------------
# precedence
# ---------------------------------------------------------------------------


def test_no_agents_returns_no_default() -> None:
    ws_id, _ = _setup_workspace()
    with SessionLocal() as db:
        result = route_message(
            db,
            workspace_id=ws_id,
            text="hello there",
            channel_id="C1",
            thread_ts="t1",
        )
        assert result.agent is None
        assert result.reason == "no_default"


def test_routes_to_default_for_untagged_message() -> None:
    ws_id, _ = _setup_workspace()
    with SessionLocal() as db:
        agent = create_agent(
            db,
            workspace_id=ws_id,
            slug="alfred",
            anthropic_agent_id="agent_001",
            environment_id="env_001",
            is_default=True,
        )
        db.commit()

    with SessionLocal() as db:
        result = route_message(
            db,
            workspace_id=ws_id,
            text="just chatting",
            channel_id="C1",
            thread_ts="t1",
        )
        assert result.reason == "default"
        assert result.agent.slug == "alfred"
        assert result.prompt == "just chatting"


def test_explicit_slug_wins_over_default() -> None:
    ws_id, _ = _setup_workspace()
    with SessionLocal() as db:
        create_agent(
            db,
            workspace_id=ws_id,
            slug="alfred",
            anthropic_agent_id="a1",
            environment_id="e1",
            is_default=True,
        )
        create_agent(
            db,
            workspace_id=ws_id,
            slug="vanguard",
            anthropic_agent_id="a2",
            environment_id="e2",
            is_default=False,
        )
        db.commit()

    with SessionLocal() as db:
        result = route_message(
            db,
            workspace_id=ws_id,
            text="vanguard what's happening in semis",
            channel_id="C1",
            thread_ts="t1",
        )
        assert result.reason == "explicit_slug"
        assert result.agent.slug == "vanguard"
        assert result.prompt == "what's happening in semis"


def test_slug_match_is_case_insensitive() -> None:
    ws_id, _ = _setup_workspace()
    with SessionLocal() as db:
        create_agent(
            db,
            workspace_id=ws_id,
            slug="vanguard",
            anthropic_agent_id="a",
            environment_id="e",
        )
        db.commit()

    with SessionLocal() as db:
        result = route_message(
            db,
            workspace_id=ws_id,
            text="Vanguard ping",
            channel_id="C1",
            thread_ts="t1",
        )
        assert result.reason == "explicit_slug"
        assert result.agent.slug == "vanguard"


def test_strips_at_mention_prefix() -> None:
    """Slack's actual event text is `<@U07ABC> rest of message` — strip the mention."""
    ws_id, _ = _setup_workspace()
    with SessionLocal() as db:
        create_agent(
            db,
            workspace_id=ws_id,
            slug="vanguard",
            anthropic_agent_id="a",
            environment_id="e",
        )
        db.commit()

    with SessionLocal() as db:
        result = route_message(
            db,
            workspace_id=ws_id,
            text="<@U07ABCDEF> vanguard what's up",
            channel_id="C1",
            thread_ts="t1",
        )
        assert result.reason == "explicit_slug"
        assert result.prompt == "what's up"


# ---------------------------------------------------------------------------
# thread pin
# ---------------------------------------------------------------------------


def test_pinned_thread_reuses_agent_across_turns() -> None:
    ws_id, _ = _setup_workspace()
    with SessionLocal() as db:
        a1 = create_agent(
            db,
            workspace_id=ws_id,
            slug="alfred",
            anthropic_agent_id="a1",
            environment_id="e1",
            is_default=True,
        )
        a2 = create_agent(
            db,
            workspace_id=ws_id,
            slug="vanguard",
            anthropic_agent_id="a2",
            environment_id="e2",
        )
        db.commit()

    # First turn: explicit `vanguard ...`
    with SessionLocal() as db:
        r = route_message(
            db,
            workspace_id=ws_id,
            text="vanguard hello",
            channel_id="C1",
            thread_ts="t1",
        )
        upsert_thread_pin(
            db,
            workspace_id=ws_id,
            channel_id="C1",
            thread_ts="t1",
            agent=r.agent,
            session_id="ses_first",
        )
        db.commit()

    # Second turn in same thread, no @ mention, no slug
    with SessionLocal() as db:
        r = route_message(
            db,
            workspace_id=ws_id,
            text="tell me more",
            channel_id="C1",
            thread_ts="t1",
        )
        assert r.reason == "thread_pin"
        assert r.agent.slug == "vanguard"
        assert r.prompt == "tell me more"
        assert r.pinned_thread is not None
        assert r.pinned_thread.last_session_id == "ses_first"


def test_archived_pinned_agent_falls_through_to_default() -> None:
    ws_id, _ = _setup_workspace()
    with SessionLocal() as db:
        a1 = create_agent(
            db,
            workspace_id=ws_id,
            slug="alfred",
            anthropic_agent_id="a1",
            environment_id="e1",
            is_default=True,
        )
        a2 = create_agent(
            db,
            workspace_id=ws_id,
            slug="vanguard",
            anthropic_agent_id="a2",
            environment_id="e2",
        )
        db.commit()

    # Pin to vanguard
    with SessionLocal() as db:
        r = route_message(
            db,
            workspace_id=ws_id,
            text="vanguard hi",
            channel_id="C1",
            thread_ts="t1",
        )
        upsert_thread_pin(
            db,
            workspace_id=ws_id,
            channel_id="C1",
            thread_ts="t1",
            agent=r.agent,
            session_id="ses1",
        )
        db.commit()

    # Archive vanguard
    with SessionLocal() as db:
        from relay_api.services.agents import get_agent_by_slug
        a = get_agent_by_slug(db, workspace_id=ws_id, slug="vanguard")
        archive_agent(db, agent=a)
        db.commit()

    # Next turn in the same thread should fall through to default
    with SessionLocal() as db:
        r = route_message(
            db,
            workspace_id=ws_id,
            text="anybody home",
            channel_id="C1",
            thread_ts="t1",
        )
        assert r.reason == "default"
        assert r.agent.slug == "alfred"


def test_upsert_updates_existing_pin() -> None:
    ws_id, _ = _setup_workspace()
    with SessionLocal() as db:
        a1 = create_agent(
            db,
            workspace_id=ws_id,
            slug="alfred",
            anthropic_agent_id="a1",
            environment_id="e1",
        )
        upsert_thread_pin(
            db,
            workspace_id=ws_id,
            channel_id="C1",
            thread_ts="t1",
            agent=a1,
            session_id="ses_v1",
        )
        upsert_thread_pin(
            db,
            workspace_id=ws_id,
            channel_id="C1",
            thread_ts="t1",
            agent=a1,
            session_id="ses_v2",
        )
        db.commit()

    with SessionLocal() as db:
        r = route_message(
            db,
            workspace_id=ws_id,
            text="more",
            channel_id="C1",
            thread_ts="t1",
        )
        assert r.pinned_thread.last_session_id == "ses_v2"
