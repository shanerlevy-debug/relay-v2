"""Slack workspace install service.

Creates / lookups / revokes WorkspaceSlackInstall rows. Encrypts the bot
token via the envelope store at create time; decrypts on demand for the
bridge process.

Powerloom's services/slack_install.py is 608 lines — most of that is
user-token refresh, MCP scope expansion, and OU-scoped permission checks
none of which apply here. Relay's version is ~150 lines and covers:
    create_install     — record a new install (after oauth.v2.access)
    get_active_install — load the current install for a workspace
    decrypt_bot_token  — JIT decrypt for the bridge process
    revoke             — mark inactive (token kept enveloped in case of
                          accidental revoke; row is soft-deleted only)
    find_by_team_id    — bridge's tenant-lookup-from-Slack-event path
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from relay_api.db.models import Workspace, WorkspaceSlackInstall
from relay_api.services.envelope import decrypt, encrypt
from relay_api.services.oauth.slack import SlackInstallExchange


class SlackInstallError(Exception):
    """Expected failures in install/revoke. The `code` field is what the UI
    branches on."""

    def __init__(self, message: str, *, code: str = "invalid"):
        super().__init__(message)
        self.code = code


def create_install(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    exchange: SlackInstallExchange,
) -> WorkspaceSlackInstall:
    """Persist a new Slack install. Caller commits.

    Raises SlackInstallError("team_already_connected") if the Slack team is
    already actively installed on a DIFFERENT workspace. Raises
    SlackInstallError("workspace_has_active_install") if THIS workspace
    already has an active install (revoke it first).
    """
    # Cross-tenant guard: is this Slack team already connected somewhere else?
    other = db.execute(
        select(WorkspaceSlackInstall)
        .where(WorkspaceSlackInstall.slack_team_id == exchange.team_id)
        .where(WorkspaceSlackInstall.revoked_at.is_(None))
        .where(WorkspaceSlackInstall.workspace_id != workspace_id)
    ).scalar_one_or_none()
    if other is not None:
        raise SlackInstallError(
            "This Slack workspace is already connected to a different Relay "
            "account. Revoke it there first, then try again.",
            code="team_already_connected",
        )

    # Self-tenant guard: this workspace might already have an active install.
    own_active = db.execute(
        select(WorkspaceSlackInstall)
        .where(WorkspaceSlackInstall.workspace_id == workspace_id)
        .where(WorkspaceSlackInstall.revoked_at.is_(None))
    ).scalar_one_or_none()
    if own_active is not None:
        raise SlackInstallError(
            "This workspace already has an active Slack install. "
            "Revoke it before reinstalling.",
            code="workspace_has_active_install",
        )

    # Generate the row ID first so envelope encryption can use it as AAD.
    install_id = uuid.uuid4()
    nonce, ct = encrypt(exchange.bot_token, aad=install_id.bytes)

    row = WorkspaceSlackInstall(
        id=install_id,
        workspace_id=workspace_id,
        slack_team_id=exchange.team_id,
        slack_team_name=exchange.team_name,
        bot_user_id=exchange.bot_user_id,
        app_id=exchange.app_id,
        enterprise_id=exchange.enterprise_id,
        enterprise_name=exchange.enterprise_name,
        bot_token_nonce=nonce,
        bot_token_ct=ct,
        scopes_granted=exchange.bot_scopes_granted,
        installed_by_user_id=user_id,
    )
    db.add(row)

    # Denormalize team_id onto the workspace for the bridge's fast lookup.
    # display_name is also opportunistically updated to the Slack team name —
    # most users will want their workspace name to match their Slack name.
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise SlackInstallError("workspace not found", code="workspace_missing")
    workspace.slack_team_id = exchange.team_id
    # Only auto-update display_name if it was still the signup-time default.
    # Heuristic: if it looks like the user typed something custom (not just
    # the team name), leave it alone. v1: just use the Slack team name.
    workspace.display_name = exchange.team_name

    db.flush()
    return row


def get_active_install(
    db: Session,
    *,
    workspace_id: uuid.UUID,
) -> WorkspaceSlackInstall | None:
    """Return the current active install for a workspace, or None."""
    return db.execute(
        select(WorkspaceSlackInstall)
        .where(WorkspaceSlackInstall.workspace_id == workspace_id)
        .where(WorkspaceSlackInstall.revoked_at.is_(None))
    ).scalar_one_or_none()


def find_by_team_id(
    db: Session,
    *,
    slack_team_id: str,
) -> WorkspaceSlackInstall | None:
    """Bridge calls this on every incoming Slack event to find the workspace.

    Indexed scan — `ix_workspace_slack_installs_team_active` covers it.
    """
    return db.execute(
        select(WorkspaceSlackInstall)
        .where(WorkspaceSlackInstall.slack_team_id == slack_team_id)
        .where(WorkspaceSlackInstall.revoked_at.is_(None))
    ).scalar_one_or_none()


def decrypt_bot_token(install: WorkspaceSlackInstall) -> str:
    """Return the plaintext xoxb-… token. JIT — never stored in memory
    longer than the request that needs it."""
    return decrypt(
        nonce=bytes(install.bot_token_nonce),
        ciphertext=bytes(install.bot_token_ct),
        aad=install.id.bytes,
    )


def revoke(
    db: Session,
    *,
    install: WorkspaceSlackInstall,
) -> None:
    """Soft-revoke. The encrypted token row stays for audit; the partial
    unique constraint releases the slack_team_id for future reinstalls.

    Caller is responsible for calling SlackProvider.revoke() if they want
    Slack-side cleanup of the token; that's network I/O and shouldn't be
    in the same critical section as the DB write.
    """
    if install.revoked_at is not None:
        return
    install.revoked_at = datetime.now(UTC)

    # Clear the denormalized team_id on the workspace so reinstall doesn't
    # see stale state.
    workspace = db.get(Workspace, install.workspace_id)
    if workspace is not None:
        workspace.slack_team_id = None

    db.flush()
