"""Tenant resolution: Slack team_id -> workspace + bot token + Anthropic key.

Every incoming Slack event carries a team_id. The bridge:
  1. Looks up the active `workspace_slack_installs` row by team_id
  2. Decrypts the bot token (used by Slack Web API calls)
  3. Looks up the workspace's Anthropic key (used by CMA session creates)

The bot-token lookup happens at TWO points:
  - In Slack-Bolt's `authorize` callback (so client.chat_* calls work)
  - In the event handler (so we can pass it to chat_postMessage explicitly
    if needed) — currently unused; the authorize callback's binding is
    enough

Anthropic key lookup happens at session-create time only — never cached.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from relay_api.db.models import Workspace, WorkspaceSlackInstall
from relay_api.services.anthropic_key import get_plaintext_key
from relay_api.services.slack_install import (
    decrypt_bot_token,
    find_by_team_id,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class TenantContext:
    """Everything the bridge needs about a tenant for one event."""

    workspace: Workspace
    install: WorkspaceSlackInstall
    bot_token: str  # decrypted (xoxb-…)
    anthropic_key: str | None  # decrypted, or None if BYOK not set


def resolve_tenant(
    db: "Session",
    *,
    team_id: str,
) -> TenantContext | None:
    """Return a TenantContext for this Slack team, or None if unknown / inactive.

    `None` is the bridge's signal to drop the event silently (with a log line).
    Unknown team_ids happen during the half-revoked window or if a workspace
    uninstalled mid-flight.
    """
    install = find_by_team_id(db, slack_team_id=team_id)
    if install is None:
        return None

    workspace = db.get(Workspace, install.workspace_id)
    if workspace is None or workspace.archived_at is not None:
        return None

    bot_token = decrypt_bot_token(install)
    anthropic_key = get_plaintext_key(db, workspace_id=workspace.id)

    return TenantContext(
        workspace=workspace,
        install=install,
        bot_token=bot_token,
        anthropic_key=anthropic_key,
    )
