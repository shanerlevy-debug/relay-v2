"""Slack event handlers — forked from v1's bridge.py, tenant-scoped.

Four event surfaces:
  app_mention   @Relay <slug> ... in a channel
  message       DMs to the bot, and threaded follow-ups in channels
                (gated on a pinned thread to avoid responding to all chatter)
  command       /relay ... slash command
                  - with text  -> route immediately (same as @mention)
                  - empty      -> open the "Ask an agent" modal
  view          relay_invoke_modal submission -> route the modal's pick

The handlers themselves are sync (Slack-Bolt's default — runs in a thread
pool). Each opens a fresh DB session and resolves the tenant first.
"""
from __future__ import annotations

import json
import uuid

from slack_bolt import App
from slack_sdk.errors import SlackApiError

from relay_api.core.config import settings
from relay_api.core.logging import get_logger
from relay_api.db.models import AuditLog
from relay_api.db.session import SessionLocal
from relay_api.services.groups import check_slack_user_agent_access

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


# ---------------------------------------------------------------------------
# "Ask an agent" modal — opened when /relay is run with no text. Keeps the
# discoverability win (pick from a list) without fighting Slack's static
# slash-command model. The submitted view fires off the same handle_message
# pipeline as a /relay <agent> <prompt> invocation.
# ---------------------------------------------------------------------------

MODAL_CALLBACK_ID = "relay_invoke_modal"
MODAL_AGENT_BLOCK = "agent_block"
MODAL_AGENT_ACTION = "agent_select"
MODAL_PROMPT_BLOCK = "prompt_block"
MODAL_PROMPT_ACTION = "prompt_input"


def _truncate(s: str, n: int) -> str:
    """Slack plain_text fields have hard char caps. Truncate with an ellipsis."""
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"


def _build_modal(*, agents: list, channel_id: str, team_id: str) -> dict:
    """Build the Block Kit view JSON for the agent-picker modal.

    `agents` is a list of Agent rows from list_agents() — already filtered to
    active and ordered. We cap at the first 100 to stay under Slack's
    static_select limit (well above our 25-agent ceiling, but defensive).
    """
    options = []
    for a in agents[:100]:
        display = a.slack_display_name or a.slug
        # 75-char hard cap on plain_text inside an option.
        if a.slack_display_name and a.slack_display_name.lower() != a.slug.lower():
            label = _truncate(f"{display}  ·  {a.slug}", 75)
        else:
            label = _truncate(display, 75)
        options.append({
            "text": {"type": "plain_text", "text": label},
            "value": a.slug,
        })

    return {
        "type": "modal",
        "callback_id": MODAL_CALLBACK_ID,
        # Carries channel_id back through the submit roundtrip — Slack
        # doesn't preserve the slash command's channel context otherwise.
        "private_metadata": json.dumps({
            "channel_id": channel_id,
            "team_id": team_id,
        }),
        "title": {"type": "plain_text", "text": "Ask an agent"},
        "submit": {"type": "plain_text", "text": "Send"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": MODAL_AGENT_BLOCK,
                "label": {"type": "plain_text", "text": "Agent"},
                "element": {
                    "type": "static_select",
                    "action_id": MODAL_AGENT_ACTION,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Pick an agent…",
                    },
                    "options": options,
                },
            },
            {
                "type": "input",
                "block_id": MODAL_PROMPT_BLOCK,
                "label": {"type": "plain_text", "text": "Message"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": MODAL_PROMPT_ACTION,
                    "multiline": True,
                    "max_length": 3000,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "what would you like to ask?",
                    },
                },
            },
        ],
    }


def _build_empty_modal(*, message: str) -> dict:
    """Fallback view when the workspace has no active agents — shows a
    helpful message instead of an empty select. Closes back into Slack."""
    return {
        "type": "modal",
        "callback_id": MODAL_CALLBACK_ID + "_noop",
        "title": {"type": "plain_text", "text": "Ask an agent"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            },
        ],
    }


def handle_message(
    *,
    client,
    text: str,
    team_id: str,
    channel_id: str,
    slack_thread_ts: str | None,
    slack_user_id: str | None = None,
) -> None:
    """Drive one user turn end-to-end.

    `slack_thread_ts` is the existing thread to reply IN (for @mentions,
    DMs, threaded follow-ups). For slash commands it's None — we post
    top-level and the placeholder's own ts becomes the thread anchor.

    Order matters for Slack persona overrides: `chat.update` does NOT
    change the displayed username / icon of a message that's already been
    posted (Slack only honors username/icon at `chat.postMessage` time).
    So we resolve routing FIRST and post the placeholder under the
    agent's persona; the subsequent chat.update for the real reply
    inherits that identity automatically.
    """
    with SessionLocal() as db:
        tenant = resolve_tenant(db, team_id=team_id)
        if tenant is None:
            log.info("tenant.unknown_team_id", team_id=team_id)
            # Disconnected workspace — post a one-shot apology. No
            # placeholder dance since we have nothing to update.
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=slack_thread_ts,
                    text="_This workspace isn't connected to Relay anymore._",
                )
            except SlackApiError:
                pass
            return

        # Pre-resolve routing so we can post the placeholder under the
        # right persona. thread_ts for the route lookup: if the caller
        # gave us one we use it; otherwise (slash command) we don't have
        # a thread yet, so we look up by the channel + a synthetic key
        # the router treats as "no pin exists." Real pins only happen
        # for app_mentions / DMs / threaded follow-ups, all of which
        # have a non-None slack_thread_ts.
        routing = route_message(
            db,
            workspace_id=tenant.workspace.id,
            text=text,
            channel_id=channel_id,
            thread_ts=slack_thread_ts or "",
        )
        log.info(
            "routing.resolved",
            reason=routing.reason,
            slug=routing.agent.slug if routing.agent else None,
            workspace_id=str(tenant.workspace.id),
        )

        # Early-exit error / help paths — post as a single new message,
        # no placeholder/update cycle.
        if routing.agent is None or not routing.prompt:
            slugs = _list_active_slugs(db, workspace_id=tenant.workspace.id)
            reply = _help_text(routing, slugs)
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=slack_thread_ts,
                    text=reply,
                )
            except SlackApiError:
                log.exception("slack.help_post_failed")
            return

        if tenant.anthropic_key is None:
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=slack_thread_ts,
                    text=(
                        "_This workspace needs an Anthropic API key. "
                        "An admin can add one in Settings._"
                    ),
                )
            except SlackApiError:
                pass
            return

        # Access check — three-state. Different denial copy for
        # unregistered (point at Sign in with Slack) vs registered-but-
        # no-group (ask admin to add to a group).
        decision = check_slack_user_agent_access(
            db,
            workspace_id=tenant.workspace.id,
            slack_user_id=slack_user_id,
            agent_id=routing.agent.id,
        )
        if not decision.allowed:
            display_label = (
                routing.agent.slack_display_name or routing.agent.slug
            )
            if decision.reason == "unregistered":
                signin_url = (
                    f"{settings.RELAY_APP_BASE_URL.rstrip('/')}"
                    "/api/oauth/slack-signin/start"
                )
                deny_text = (
                    "_You need a Relay account to use this. "
                    f"<{signin_url}|Sign in with Slack> first, "
                    "or ask an admin to invite you._"
                )
            elif decision.reason == "agent_no_groups":
                deny_text = (
                    f"_*{display_label}* isn't in any group right now — "
                    "an admin needs to add it to one before anyone can "
                    "reach it._"
                )
            else:  # no_group_access
                deny_text = (
                    f"_You don't have access to *{display_label}*. "
                    "Ask an admin to add you to a group that includes it._"
                )
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=slack_thread_ts,
                    text=deny_text,
                )
            except SlackApiError:
                pass
            log.info(
                "access.denied",
                reason=decision.reason,
                workspace_id=str(tenant.workspace.id),
                slack_user_id=slack_user_id,
                agent_id=str(routing.agent.id),
                slug=routing.agent.slug,
            )
            return

        # Happy path — agent + prompt + key all present. Post the
        # placeholder UNDER the agent's persona so subsequent
        # chat.update inherits the identity.
        persona = _persona_kwargs(routing.agent)
        display_label = (
            routing.agent.slack_display_name or routing.agent.slug
        )
        try:
            placeholder = client.chat_postMessage(
                channel=channel_id,
                thread_ts=slack_thread_ts,
                text=f"_{display_label} is thinking…_",
                **persona,
            )
        except SlackApiError:
            log.exception("slack.placeholder_failed")
            return

        pin_key_thread_ts = slack_thread_ts or placeholder["ts"]
        anchor_ts = slack_thread_ts or placeholder["ts"]

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
            slack_user_id=event.get("user"),
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
            log.info("message.dm", channel_id=channel_id, team_id=team_id)
            handle_message(
                client=client,
                text=event.get("text", ""),
                team_id=team_id,
                channel_id=channel_id,
                slack_thread_ts=thread_ts,
                slack_user_id=event.get("user"),
            )
            return

        # Channel messages — only respond inside an already-pinned thread.
        thread_ts = event.get("thread_ts")
        if not thread_ts:
            log.debug(
                "message.channel_top_level_ignored",
                channel_id=event.get("channel"),
                team_id=team_id,
            )
            return
        channel_id = event["channel"]

        with SessionLocal() as db:
            tenant = resolve_tenant(db, team_id=team_id)
            if tenant is None:
                log.info(
                    "message.thread_no_tenant",
                    team_id=team_id,
                    channel_id=channel_id,
                    thread_ts=thread_ts,
                )
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
                log.info(
                    "message.thread_not_pinned",
                    workspace_id=str(tenant.workspace.id),
                    channel_id=channel_id,
                    thread_ts=thread_ts,
                )
                return
            log.info(
                "message.thread_pinned_match",
                workspace_id=str(tenant.workspace.id),
                channel_id=channel_id,
                thread_ts=thread_ts,
                pinned_agent_id=str(pinned.agent_id),
            )

        handle_message(
            client=client,
            text=event.get("text", ""),
            team_id=team_id,
            channel_id=channel_id,
            slack_thread_ts=thread_ts,
            slack_user_id=event.get("user"),
        )

    @app.command(settings.RELAY_SLACK_SLASH_COMMAND)
    def on_slash(ack, command, client):
        ack()
        team_id = command.get("team_id")
        if not team_id:
            log.warning("event.no_team_id", event_type="slash")
            return

        text = (command.get("text") or "").strip()

        # With args -> behave as before. The router already handles
        # "<slug> <prompt>" parsing and falls back to default agent.
        if text:
            handle_message(
                client=client,
                text=text,
                team_id=team_id,
                channel_id=command["channel_id"],
                slack_thread_ts=None,  # slash commands post top-level
                slack_user_id=command.get("user_id"),
            )
            return

        # Bare `/relay` — open the picker modal.
        with SessionLocal() as db:
            tenant = resolve_tenant(db, team_id=team_id)
            if tenant is None:
                # Workspace not connected — don't expose any agent list.
                # The mention/DM paths already handle this via a quiet
                # apology; the slash path opens a no-op modal instead.
                try:
                    client.views_open(
                        trigger_id=command["trigger_id"],
                        view=_build_empty_modal(
                            message=(
                                ":warning: This workspace isn't connected to "
                                "Relay anymore."
                            ),
                        ),
                    )
                except SlackApiError:
                    log.exception("slack.views_open_failed", reason="no_tenant")
                return

            from relay_api.services.agents import list_agents
            agents = list_agents(db, workspace_id=tenant.workspace.id)
            if not agents:
                try:
                    client.views_open(
                        trigger_id=command["trigger_id"],
                        view=_build_empty_modal(
                            message=(
                                "No agents in this workspace yet. An admin "
                                "can add one in *<https://relayed.live/agents|"
                                "Relay → Agents>*."
                            ),
                        ),
                    )
                except SlackApiError:
                    log.exception("slack.views_open_failed", reason="no_agents")
                return

            try:
                client.views_open(
                    trigger_id=command["trigger_id"],
                    view=_build_modal(
                        agents=list(agents),
                        channel_id=command["channel_id"],
                        team_id=team_id,
                    ),
                )
            except SlackApiError:
                log.exception("slack.views_open_failed")

    # Modal submission — fired when the user clicks "Send" in the picker.
    # Bolt's @app.view auto-acks; we route as if the user had typed
    # /relay <agent> <prompt> from the original channel.
    @app.view(MODAL_CALLBACK_ID)
    def on_modal_submit(ack, body, view, client):
        ack()  # close the modal immediately; the routing post is async
        try:
            meta = json.loads(view.get("private_metadata") or "{}")
        except json.JSONDecodeError:
            log.warning("modal.bad_private_metadata")
            return
        team_id = meta.get("team_id") or body.get("team", {}).get("id")
        channel_id = meta.get("channel_id")
        if not team_id or not channel_id:
            log.warning("modal.missing_routing_context")
            return

        values = view.get("state", {}).get("values", {}) or {}
        agent_block = values.get(MODAL_AGENT_BLOCK, {})
        prompt_block = values.get(MODAL_PROMPT_BLOCK, {})
        selected = (
            (agent_block.get(MODAL_AGENT_ACTION) or {}).get("selected_option")
            or {}
        )
        slug = (selected.get("value") or "").strip()
        prompt = (
            (prompt_block.get(MODAL_PROMPT_ACTION) or {}).get("value") or ""
        ).strip()

        if not slug or not prompt:
            log.warning("modal.empty_payload", slug_set=bool(slug), prompt_set=bool(prompt))
            return

        # Route as if the user had typed `/relay <slug> <prompt>`. The
        # router resolves the explicit-slug branch and the rest of the
        # placeholder/CMA/post pipeline runs identically.
        invoker_id = (body.get("user") or {}).get("id")
        handle_message(
            client=client,
            text=f"{slug} {prompt}",
            team_id=team_id,
            channel_id=channel_id,
            slack_thread_ts=None,
            slack_user_id=invoker_id,
        )
