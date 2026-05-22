"""Slack event handlers — forked from v1's bridge.py, tenant-scoped.

Three event types:
  app_mention   @Relay <slug> ... in a channel
  message       DMs to the bot, and threaded follow-ups in channels
                (gated on a pinned thread to avoid responding to all chatter)
  command       /ask <slug> ... slash command

The handlers themselves are sync (Slack-Bolt's default — runs in a thread
pool). Each opens a fresh DB session and resolves the tenant first.
"""
from __future__ import annotations

import uuid

from slack_bolt import App
from slack_sdk.errors import SlackApiError

from relay_api.core.config import settings
from relay_api.core.logging import get_logger
from relay_api.db.models import AuditLog
from relay_api.db.session import SessionLocal

from relay_bridge.cma import invoke_agent
from relay_bridge.routing import RoutingResult, route_message, upsert_thread_pin
from relay_bridge.tenant import TenantContext, resolve_tenant

log = get_logger("relay-bridge.handlers")

SLACK_TEXT_LIMIT = 3500  # safe display ceiling; Slack hard limit is 40000


# ---------------------------------------------------------------------------
# persona overrides — chat:write.customize on the install token lets us pick
# a per-message `username` + `icon_url`/`icon_emoji`.
# ---------------------------------------------------------------------------


def _persona_kwargs(agent) -> dict:
    """Return the `username` / `icon_*` kwargs for this agent's persona.

    `slack_icon_url` carries either an `:emoji:` token or an `https://...`
    URL — we route to `icon_emoji` vs `icon_url` accordingly. Empty dict
    means "use the install's default identity" (the base 'relay' bot).
    """
    out: dict[str, str] = {}
    name = getattr(agent, "slack_display_name", None)
    if name:
        out["username"] = name
    icon = getattr(agent, "slack_icon_url", None)
    if icon:
        icon = icon.strip()
        if icon.startswith(":") and icon.endswith(":"):
            out["icon_emoji"] = icon
        elif icon.startswith("https://"):
            out["icon_url"] = icon
    return out


# ---------------------------------------------------------------------------
# message chunking (lifted verbatim from v1 — already battle-tested)
# ---------------------------------------------------------------------------


def _chunk_text(text: str, max_chars: int = SLACK_TEXT_LIMIT) -> list[str]:
    """Split long text at paragraph/line/word boundaries for Slack chat."""
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        split_at = -1
        for sep in ("\n\n", "\n", " "):
            idx = remaining.rfind(sep, 0, max_chars)
            if idx > max_chars // 2:
                split_at = idx
                break
        if split_at < 0:
            chunks.append(remaining[:max_chars])
            remaining = remaining[max_chars:]
        else:
            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _post_reply(
    client,
    *,
    channel_id: str,
    placeholder_ts: str,
    anchor_ts: str,
    reply: str,
    persona: dict | None = None,
) -> None:
    """Update the placeholder with the reply. Chunk into thread replies if too long.

    `persona` carries `username` / `icon_*` overrides for the responding
    agent — applied on every `chat_postMessage` and `chat_update` so the
    full reply chain wears the same identity.

    Note: Slack accepts `username` / `icon_*` on both `chat_update` and
    `chat_postMessage`, but only when the bot install has
    `chat:write.customize`. Without that scope, Slack silently ignores
    these fields and falls back to the install's default identity.
    """
    persona = persona or {}
    chunks = _chunk_text(reply)
    try:
        client.chat_update(
            channel=channel_id, ts=placeholder_ts, text=chunks[0], **persona,
        )
    except SlackApiError as e:
        log.warning(
            "slack.chat_update_failed",
            error=e.response.get("error"),
            falling_back="postMessage",
        )
        client.chat_postMessage(
            channel=channel_id, thread_ts=anchor_ts, text=chunks[0], **persona,
        )
    for chunk in chunks[1:]:
        client.chat_postMessage(
            channel=channel_id, thread_ts=anchor_ts, text=chunk, **persona,
        )


# ---------------------------------------------------------------------------
# core orchestration
# ---------------------------------------------------------------------------


def _help_text(routing: RoutingResult, available_slugs: list[str]) -> str:
    """User-visible reply when we have no agent to route to or no prompt."""
    if routing.reason == "no_default" and not available_slugs:
        return (
            "_No agents configured for this workspace. An admin can add one "
            "in Settings._"
        )
    if routing.reason == "no_default":
        listed = ", ".join(f"`{s}`" for s in available_slugs)
        return (
            "_No default agent is set. Either set one in Settings or address "
            f"an agent explicitly: `@Relay <slug> <message>` — available: {listed}._"
        )
    # Empty prompt with a real agent matched (shouldn't usually happen but
    # defensive).
    listed = ", ".join(f"`{s}`" for s in available_slugs)
    return (
        "_I didn't catch a question. Try `@Relay <slug> <message>` — "
        f"available: {listed}._"
    )


def _list_active_slugs(db, *, workspace_id: uuid.UUID) -> list[str]:
    """For the help reply when nothing matched."""
    from relay_api.services.agents import list_agents
    return [a.slug for a in list_agents(db, workspace_id=workspace_id)]


def handle_message(
    *,
    client,
    text: str,
    team_id: str,
    channel_id: str,
    slack_thread_ts: str | None,
) -> None:
    """Drive one user turn end-to-end.

    `slack_thread_ts` is the existing thread to reply IN (for @mentions,
    DMs, threaded follow-ups). For slash commands it's None — we post
    top-level and use the placeholder's own ts as the thread anchor.
    """
    # Post placeholder FIRST so we have a ts for the pin/anchor.
    try:
        placeholder = client.chat_postMessage(
            channel=channel_id,
            thread_ts=slack_thread_ts,
            text="_thinking…_",
        )
    except SlackApiError:
        log.exception("slack.placeholder_failed")
        return

    pin_key_thread_ts = slack_thread_ts or placeholder["ts"]
    anchor_ts = slack_thread_ts or placeholder["ts"]

    with SessionLocal() as db:
        tenant = resolve_tenant(db, team_id=team_id)
        if tenant is None:
            log.info("tenant.unknown_team_id", team_id=team_id)
            # Don't reply — we shouldn't even be hearing from this workspace.
            # Replace the placeholder with a quiet apology message.
            try:
                client.chat_update(
                    channel=channel_id,
                    ts=placeholder["ts"],
                    text="_This workspace isn't connected to Relay anymore._",
                )
            except SlackApiError:
                pass
            return

        routing = route_message(
            db,
            workspace_id=tenant.workspace.id,
            text=text,
            channel_id=channel_id,
            thread_ts=pin_key_thread_ts,
        )
        log.info(
            "routing.resolved",
            reason=routing.reason,
            slug=routing.agent.slug if routing.agent else None,
            workspace_id=str(tenant.workspace.id),
        )

        if routing.agent is None:
            slugs = _list_active_slugs(db, workspace_id=tenant.workspace.id)
            reply = _help_text(routing, slugs)
            try:
                client.chat_update(
                    channel=channel_id,
                    ts=placeholder["ts"],
                    text=reply,
                )
            except SlackApiError:
                log.exception("slack.help_chat_update_failed")
            return

        if not routing.prompt:
            slugs = _list_active_slugs(db, workspace_id=tenant.workspace.id)
            reply = _help_text(routing, slugs)
            try:
                client.chat_update(
                    channel=channel_id, ts=placeholder["ts"], text=reply
                )
            except SlackApiError:
                pass
            return

        if tenant.anthropic_key is None:
            reply = (
                "_This workspace needs an Anthropic API key. An admin can add "
                "one in Settings._"
            )
            try:
                client.chat_update(
                    channel=channel_id, ts=placeholder["ts"], text=reply
                )
            except SlackApiError:
                pass
            return

        # Update placeholder with the chosen agent name + apply the persona
        # override now that we know which agent will answer.
        persona = _persona_kwargs(routing.agent)
        display_label = (
            routing.agent.slack_display_name or routing.agent.slug
        )
        try:
            client.chat_update(
                channel=channel_id,
                ts=placeholder["ts"],
                text=f"_{display_label} is thinking…_",
                **persona,
            )
        except SlackApiError:
            pass

        # Invoke CMA.
        existing_session_id = (
            routing.pinned_thread.last_session_id
            if routing.pinned_thread is not None
            else None
        )

        try:
            reply, session_id = invoke_agent(
                anthropic_key=tenant.anthropic_key,
                agent=routing.agent,
                prompt=routing.prompt,
                existing_session_id=existing_session_id,
            )
        except Exception as e:
            log.exception("cma.invoke_failed", slug=routing.agent.slug)
            reply = (
                f"_(agent {routing.agent.slug} errored: "
                f"`{type(e).__name__}: {e}`)_"
            )
            _post_reply(
                client,
                channel_id=channel_id,
                placeholder_ts=placeholder["ts"],
                anchor_ts=anchor_ts,
                reply=reply,
                persona=persona,
            )
            return

        # Persist thread pin
        upsert_thread_pin(
            db,
            workspace_id=tenant.workspace.id,
            channel_id=channel_id,
            thread_ts=pin_key_thread_ts,
            agent=routing.agent,
            session_id=session_id,
        )

        # Audit log entry — one row per Slack message routed.
        db.add(AuditLog(
            workspace_id=tenant.workspace.id,
            actor_user_id=None,  # Slack-originated; no Relay user
            event_type="agent.message_routed",
            subject_type="agent",
            subject_id=routing.agent.id,
            metadata_json={
                "slug": routing.agent.slug,
                "reason": routing.reason,
                "channel_id": channel_id,
                "thread_ts": pin_key_thread_ts,
                "session_id": session_id,
                "is_first_turn": existing_session_id is None,
            },
        ))

        db.commit()

    # Outside the DB session: send the actual reply to Slack.
    _post_reply(
        client,
        channel_id=channel_id,
        placeholder_ts=placeholder["ts"],
        anchor_ts=anchor_ts,
        reply=reply,
        persona=persona,
    )


# ---------------------------------------------------------------------------
# handler registration
# ---------------------------------------------------------------------------


def register_handlers(app: App) -> None:
    """Wire the Slack-Bolt event handlers to the orchestrator above."""

    @app.event("app_mention")
    def on_app_mention(event, body, client):
        team_id = body.get("team_id") or (body.get("team") or {}).get("id")
        if not team_id:
            log.warning("event.no_team_id", event_type="app_mention")
            return
        channel_id = event["channel"]
        thread_ts = event.get("thread_ts") or event["ts"]
        handle_message(
            client=client,
            text=event.get("text", ""),
            team_id=team_id,
            channel_id=channel_id,
            slack_thread_ts=thread_ts,
        )

    @app.event("message")
    def on_message(event, body, client):
        # Ignore the bot's own messages + other bots.
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return
        team_id = body.get("team_id") or (body.get("team") or {}).get("id")
        if not team_id:
            log.warning("event.no_team_id", event_type="message")
            return

        # DMs — always respond.
        if event.get("channel_type") == "im":
            channel_id = event["channel"]
            thread_ts = event.get("thread_ts") or event["ts"]
            handle_message(
                client=client,
                text=event.get("text", ""),
                team_id=team_id,
                channel_id=channel_id,
                slack_thread_ts=thread_ts,
            )
            return

        # Channel messages — only respond inside an already-pinned thread.
        thread_ts = event.get("thread_ts")
        if not thread_ts:
            return
        channel_id = event["channel"]

        with SessionLocal() as db:
            tenant = resolve_tenant(db, team_id=team_id)
            if tenant is None:
                return
            from sqlalchemy import select
            from relay_api.db.models import SlackThread
            pinned = db.execute(
                select(SlackThread).where(
                    SlackThread.workspace_id == tenant.workspace.id,
                    SlackThread.channel_id == channel_id,
                    SlackThread.thread_ts == thread_ts,
                )
            ).scalar_one_or_none()
            if pinned is None:
                return

        handle_message(
            client=client,
            text=event.get("text", ""),
            team_id=team_id,
            channel_id=channel_id,
            slack_thread_ts=thread_ts,
        )

    @app.command(settings.RELAY_SLACK_SLASH_COMMAND)
    def on_slash(ack, command, client):
        ack()
        team_id = command.get("team_id")
        if not team_id:
            log.warning("event.no_team_id", event_type="slash")
            return
        handle_message(
            client=client,
            text=command.get("text", ""),
            team_id=team_id,
            channel_id=command["channel_id"],
            slack_thread_ts=None,  # slash commands post top-level
        )
