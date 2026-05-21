"""Claude Managed Agents invocation — multi-tenant adaptation of v1's bridge.

Same SDK shape as v1 (validated end-to-end in week 1 of v2 lift):
  - `client.beta.sessions.create(agent=..., environment_id=...)`
  - `client.beta.sessions.events.send(session_id, events=[{"type":"user.message","content":[{"type":"text","text":...}]}])`
  - `client.beta.sessions.events.stream(session_id=...)` is a context manager
  - Terminal: `session.status_terminated` OR `session.status_idle` with
    `stop_reason.type != "requires_action"`

Per-tenant differences:
  - Anthropic key is decrypted from envelope storage just-in-time (NEVER cached)
  - Session reuse: first turn creates a session; follow-ups reuse `last_session_id`
"""
from __future__ import annotations

from anthropic import Anthropic

from relay_api.core.config import settings
from relay_api.core.logging import get_logger
from relay_api.db.models import Agent

log = get_logger("relay-bridge.cma")


def _extract_text(content) -> str:
    """Pull text out of agent.message content blocks. Same coercion as v1
    — content can be a string, a list of typed blocks, or a typed object.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for c in content:
            text = getattr(c, "text", None)
            if text is None and isinstance(c, dict):
                text = c.get("text")
            if text:
                out.append(text)
        return "".join(out)
    text = getattr(content, "text", None)
    return text or ""


def invoke_agent(
    *,
    anthropic_key: str,
    agent: Agent,
    prompt: str,
    existing_session_id: str | None,
) -> tuple[str, str]:
    """Create or reuse a CMA session and stream the reply.

    Returns (reply_text, session_id). The session_id is what the caller
    persists into the thread pin so the next turn can reuse the session
    (CMA preserves conversation history within a session).

    Raises any anthropic.* exception. Caller surfaces as user-visible error.
    """
    claude = Anthropic(api_key=anthropic_key)

    session_id = existing_session_id
    if session_id is None:
        session = claude.beta.sessions.create(
            agent=agent.anthropic_agent_id,
            environment_id=agent.environment_id,
        )
        session_id = session.id
        log.info(
            "cma.session_created",
            slug=agent.slug,
            session_id=session_id,
        )
    else:
        log.info(
            "cma.session_reused",
            slug=agent.slug,
            session_id=session_id,
        )

    chunks: list[str] = []

    # Open the stream BEFORE sending the kickoff so we don't miss early events.
    with claude.beta.sessions.events.stream(session_id=session_id) as stream:
        claude.beta.sessions.events.send(
            session_id,
            events=[{
                "type": "user.message",
                "content": [{"type": "text", "text": prompt}],
            }],
        )

        for ev in stream:
            ev_type = getattr(ev, "type", "") or ""
            if settings.RELAY_BRIDGE_LOG_EVENT_TYPES:
                log.info("cma.stream_ev", type=ev_type)

            if ev_type == "agent.message":
                chunks.append(_extract_text(getattr(ev, "content", None)))
                continue

            if ev_type == "session.status_terminated":
                break

            if ev_type == "session.status_idle":
                stop_reason = getattr(ev, "stop_reason", None)
                reason_type = (
                    getattr(stop_reason, "type", None) if stop_reason else None
                )
                if reason_type == "requires_action":
                    log.warning(
                        "cma.idled_awaiting_tool_confirmation",
                        session_id=session_id,
                    )
                break

    reply_text = "".join(chunks).strip()
    return reply_text or "_(no reply from agent)_", session_id
