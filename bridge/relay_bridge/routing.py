"""Slug -> agent resolution + thread-pin upsert.

Routing precedence:
  1. First whitespace-stripped word is a known active slug -> use it
     ("explicit slug wins over the pin" — supports mid-thread agent
     switching, e.g. typing `vanguard what about Q3?` in a thread Alfred
     was already on. Result is treated as a fresh session under the new
     agent and the pin updates accordingly.)
  2. Thread is already pinned to an active agent  -> use that agent
  3. Workspace has a default agent  -> use the default
  4. Otherwise  -> no agent (bridge replies with help text)

Pin upsert happens after each successful CMA invocation. If the pinned
agent has been archived since the thread started, fall through to default
routing on the next turn — `last_session_id` is discarded along with the
pin (no point continuing a CMA session whose agent definition is gone).
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from relay_api.db.models import Agent, SlackThread
from relay_api.services.agents import (
    find_default_agent,
    get_agent_by_addressable_name,
    get_agent_by_id,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Slack mentions arrive as "<@U07ABC> the rest of the message". Strip them.
_MENTION_RE = re.compile(r"^<@[A-Z0-9]+>\s*")


@dataclass
class RoutingResult:
    """What the router decided. `agent=None` means none matched and the
    caller should send a help reply."""

    agent: Agent | None
    prompt: str
    reason: str  # 'thread_pin' | 'explicit_slug' | 'default' | 'no_default'
    pinned_thread: SlackThread | None = None


def route_message(
    db: "Session",
    *,
    workspace_id: uuid.UUID,
    text: str,
    channel_id: str,
    thread_ts: str,
) -> RoutingResult:
    """Pick the agent that handles this message.

    Caller is responsible for handling each `reason` appropriately:
      thread_pin     -> reuse pinned_thread.last_session_id on CMA invoke
      explicit_slug  -> create new session
      default        -> create new session
      no_default     -> reply with help text, do NOT invoke CMA
    """
    cleaned = _MENTION_RE.sub("", text or "").strip()

    # Look up the pin once, regardless of which branch wins. We need it
    # below either to return as thread_pin, to attach to an explicit_slug
    # switch (so the caller can detect this was a switch and clear the
    # old session_id), or to drop if its agent is archived.
    pin = db.execute(
        select(SlackThread).where(
            SlackThread.workspace_id == workspace_id,
            SlackThread.channel_id == channel_id,
            SlackThread.thread_ts == thread_ts,
        )
    ).scalar_one_or_none()

    # 1. Explicit slug as the first whitespace-delimited token. This wins
    # over the thread pin so users can switch agents mid-conversation:
    #   alfred:  "(reply in a thread alfred was pinned to)
    #   user:    "vanguard what about Q3"  -> switches to vanguard
    # The pin upsert at the end of the turn will overwrite the pinned
    # agent_id + last_session_id with the new agent's.
    parts = cleaned.split(None, 1)
    if parts:
        # Match by whatever the user typed — slug OR slack_display_name.
        # If the agent's slug is `helpdesk` and slack_display_name is
        # `Slackie`, typing either word as the first token routes here.
        candidate = parts[0]
        explicit = get_agent_by_addressable_name(
            db, workspace_id=workspace_id, name=candidate
        )
        if explicit is not None:
            # If the explicit slug matches the already-pinned agent, treat
            # this as a normal pinned-thread continuation so the existing
            # CMA session is reused. (The slug prefix is conversational
            # nicety, not an actual switch.)
            if (
                pin is not None
                and pin.agent_id == explicit.id
                and explicit.archived_at is None
            ):
                return RoutingResult(
                    agent=explicit,
                    prompt=parts[1] if len(parts) > 1 else "",
                    reason="thread_pin",
                    pinned_thread=pin,
                )
            return RoutingResult(
                agent=explicit,
                prompt=parts[1] if len(parts) > 1 else "",
                reason="explicit_slug",
            )

    # 2. Thread pin (no explicit slug, or slug didn't match an active agent)
    if pin is not None:
        pinned_agent = get_agent_by_id(
            db, workspace_id=workspace_id, agent_id=pin.agent_id
        )
        if pinned_agent is not None and pinned_agent.archived_at is None:
            return RoutingResult(
                agent=pinned_agent,
                prompt=cleaned,
                reason="thread_pin",
                pinned_thread=pin,
            )
        # Pinned agent archived -> drop the pin, fall through to default routing.
        # The session_id is unreusable since its agent is gone.
        db.delete(pin)
        db.flush()

    # 3. Default
    default_agent = find_default_agent(db, workspace_id=workspace_id)
    if default_agent is not None:
        return RoutingResult(
            agent=default_agent,
            prompt=cleaned,
            reason="default",
        )

    # 4. No agent available
    return RoutingResult(
        agent=None,
        prompt=cleaned,
        reason="no_default",
    )


def upsert_thread_pin(
    db: "Session",
    *,
    workspace_id: uuid.UUID,
    channel_id: str,
    thread_ts: str,
    agent: Agent,
    session_id: str,
) -> SlackThread:
    """Record (or update) the (channel_id, thread_ts) -> agent mapping.

    Caller flushes / commits.
    """
    pin = db.execute(
        select(SlackThread).where(
            SlackThread.workspace_id == workspace_id,
            SlackThread.channel_id == channel_id,
            SlackThread.thread_ts == thread_ts,
        )
    ).scalar_one_or_none()

    now = datetime.now(UTC)
    if pin is None:
        pin = SlackThread(
            workspace_id=workspace_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            agent_id=agent.id,
            last_session_id=session_id,
            created_at=now,
            updated_at=now,
        )
        db.add(pin)
    else:
        pin.agent_id = agent.id
        pin.last_session_id = session_id
        pin.updated_at = now

    db.flush()
    return pin
