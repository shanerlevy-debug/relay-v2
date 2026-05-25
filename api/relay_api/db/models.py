"""SQLAlchemy ORM models for Relay v2.

Models are added incrementally as features land. Today (week 1 day 2) we
ship the five tables that don't depend on any later lift work:

    workspaces            — one row per tenant Slack workspace
    users                 — workspace members (Slack-mapped after install)
    invites               — tokenized workspace invitations
    audit_log             — append-only event stream (no chain — see plan §10)
    enterprise_requests   — lead-gen capture for limit-hit / SSO / etc.

Coming soon:
    workspace_slack_installs    — week 1 day 4-5, with the Slack OAuth lift
    workspace_anthropic_keys    — week 2 day 4, with BYOK wiring
    agents                      — week 2 day 3
    slack_threads               — week 2 day 4, with bridge multi-tenant rewire

All UUIDs are server-generated via `gen_random_uuid()` (Postgres 13+ built-in;
no `pgcrypto` extension required). Timestamps are timezone-aware. FK behavior
is `ondelete=CASCADE` on workspace_id so a workspace removal cleans up cleanly
(workspaces themselves are rarely deleted, but it's the correct invariant).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    LargeBinary,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from relay_api.db.session import Base

# ---------------------------------------------------------------------------
# workspaces
# ---------------------------------------------------------------------------


class Workspace(Base):
    """One row per tenant Slack workspace.

    `slack_team_id` is the Slack-assigned `T…` identifier. The partial unique
    constraint allows the same team_id to appear twice IF the older row is
    archived — supports clean reinstall on a workspace that was previously
    archived (revoked).
    """

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    slack_team_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # The last CMA environment_id used when adding/editing an agent in
    # this workspace. Used by the AgentDialog's environment picker to
    # pre-select a sensible default for the next agent. Pure UX state —
    # the actual env binding lives on each agent row.
    cma_default_environment_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)

    users: Mapped[list[User]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_workspaces_slack_team_id_active",
            "slack_team_id",
            unique=True,
            postgresql_where=text("archived_at IS NULL AND slack_team_id IS NOT NULL"),
        ),
    )


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------


class User(Base):
    """Workspace member. Created two ways:

    1. The workspace admin signs up via web (email + password). At that point
       `slack_user_id` is null until they install Slack and we see them in an
       event.
    2. An invited teammate accepts an invite link.

    `role` is enforced by CHECK rather than Postgres ENUM — easier to migrate,
    easier to query. v1 has just 'admin' | 'member'; if we ever need a third
    it lands here.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(nullable=True)

    slack_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Set when this user has completed Slack OIDC sign-in. Bridge access
    # check uses presence-of-timestamp as proof of identity for license
    # enforcement. NULL means slack_user_id was set manually or via the
    # Add-to-Slack installer path (still trusted, just not OIDC-verified).
    slack_user_verified_at: Mapped[datetime | None] = mapped_column(nullable=True)

    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text("'member'"),
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="users")

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'member')",
            name="ck_users_role_valid",
        ),
        # One email per workspace (case-insensitive), among non-deleted rows.
        Index(
            "ix_users_workspace_email_active",
            "workspace_id",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        # One Slack user mapping per workspace, among non-deleted rows.
        Index(
            "ix_users_workspace_slack_user_active",
            "workspace_id",
            "slack_user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND slack_user_id IS NOT NULL"),
        ),
    )


# ---------------------------------------------------------------------------
# invites
# ---------------------------------------------------------------------------


class Invite(Base):
    """Outstanding workspace invitation.

    We only store the SHA-256 hash of the invite token, never the token
    itself — the raw token is emailed to the recipient and only their copy
    can be reversed against the hash on accept.
    """

    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)

    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)

    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # null if the system created it (e.g. workspace owner bootstrap)
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'member')",
            name="ck_invites_role_valid",
        ),
        # Fast lookup by token hash (used on accept).
        Index("ix_invites_token_hash", "token_hash", unique=True),
        # Fast lookup for "invites pending for this workspace."
        Index(
            "ix_invites_workspace_pending",
            "workspace_id",
            postgresql_where=text("accepted_at IS NULL"),
        ),
    )


# ---------------------------------------------------------------------------
# audit_log
# ---------------------------------------------------------------------------


class AuditLog(Base):
    """Append-only event stream.

    Powerloom has a hash-chained version with a nightly verifier; Relay
    explicitly does not — see plan §10. INSERT-only + an index on
    (workspace_id, occurred_at DESC) is enough for the audit viewer page.

    `metadata_json` carries event-specific shape (e.g., for
    'workspace.slack_install_completed': {"slack_team_id": "T123",
    "scopes_granted": [...]}). Keep it flat — clients don't deeply walk it.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    metadata_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    occurred_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # Primary access pattern: "show this workspace's audit, newest first."
        Index(
            "ix_audit_log_workspace_occurred",
            "workspace_id",
            text("occurred_at DESC"),
        ),
    )


# ---------------------------------------------------------------------------
# enterprise_requests
# ---------------------------------------------------------------------------


class WorkspaceSlackInstall(Base):
    """One row per Slack workspace install. Bot token stored AES-256-GCM
    enveloped with the row's UUID as AAD.

    The partial unique constraint on `slack_team_id WHERE revoked_at IS NULL`
    guarantees one active install per Slack workspace globally — if a
    customer tries to install a workspace that's already connected to a
    different Relay account, the callback 409s with "revoke there first."

    A second partial unique on `workspace_id WHERE revoked_at IS NULL`
    enforces "one active Slack install per workspace" (the workspace can
    install many times over its lifetime, just not concurrently).
    """

    __tablename__ = "workspace_slack_installs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    slack_team_id: Mapped[str] = mapped_column(String(32), nullable=False)
    slack_team_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bot_user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    app_id: Mapped[str] = mapped_column(String(32), nullable=False)
    enterprise_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    enterprise_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Bot token (xoxb-…). Envelope-encrypted: aad = this row's id.bytes.
    bot_token_nonce: Mapped[bytes] = mapped_column(
        LargeBinary(12), nullable=False
    )
    bot_token_ct: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # Granted scopes, denormalized for audit. Empty array represents "none"
    # but Slack guarantees at least the requested bot scopes on success.
    scopes_granted: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )

    installed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    installed_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        # One active install per Slack workspace, globally.
        Index(
            "ix_workspace_slack_installs_team_active",
            "slack_team_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        # One active Slack install per Relay workspace.
        Index(
            "ix_workspace_slack_installs_workspace_active",
            "workspace_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )


class Agent(Base):
    """Per-workspace agent registry. Replaces v1's agents.yaml git-ops flow.

    Each row maps a workspace-scoped slug ("vanguard", "alfred", …) to an
    Anthropic CMA `agent_…` ID + `environment_…` ID. The bridge looks up
    by (workspace_id, slug) on each incoming Slack message.

    `is_default` flags the agent that handles untagged messages. At most
    one active agent per workspace can be the default (partial unique
    index enforces this).
    """

    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    anthropic_agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Per-agent Slack persona — what the bot looks like when it posts.
    # Both NULL = fall back to the install's default identity ("relay").
    # slack_icon_url is either an `:emoji:` token or an `https://...` URL.
    slack_display_name: Mapped[str | None] = mapped_column(String(30), nullable=True)
    slack_icon_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_default: Mapped[bool] = mapped_column(
        nullable=False,
        server_default=text("false"),
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        # One slug per workspace among active agents. (Reusing a slug
        # after archiving the previous owner is allowed.)
        Index(
            "ix_agents_workspace_slug_active",
            "workspace_id",
            "slug",
            unique=True,
            postgresql_where=text("archived_at IS NULL"),
        ),
        # At most one default agent per workspace among active ones.
        Index(
            "ix_agents_workspace_default_active",
            "workspace_id",
            unique=True,
            postgresql_where=text("is_default AND archived_at IS NULL"),
        ),
    )


class SlackThread(Base):
    """Pin (channel_id, thread_ts) -> agent for thread continuity.

    Bridge writes a row on the first reply in a thread, then reads it on
    every subsequent message in that thread to keep routing to the same
    agent. `last_session_id` is the most recent CMA session ID so the
    agent retains conversational memory across turns.
    """

    __tablename__ = "slack_threads"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    channel_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    thread_ts: Mapped[str] = mapped_column(String(32), primary_key=True)

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    last_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )


class WorkspaceAnthropicKey(Base):
    """BYO Anthropic API key, AES-256-GCM enveloped.

    One row per workspace (PK = workspace_id). Set/replace via UPSERT;
    delete by row removal. The plaintext key is never returned from any
    API endpoint — only `has_key: bool` status. The bridge process reads
    it via direct DB query + decrypt(aad=workspace_id.bytes) just-in-time
    on each CMA session create.
    """

    __tablename__ = "workspace_anthropic_keys"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )

    key_nonce: Mapped[bytes] = mapped_column(LargeBinary(12), nullable=False)
    key_ct: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )


class EnterpriseRequest(Base):
    """Lead-gen capture. Hit one of the deliberate-ceiling features (25-user
    limit, 25-agent limit, SSO, SOC2, custom contract) and the UI records a
    row here + emails Shane. The whole "sales funnel" lives in this table.
    """

    __tablename__ = "enterprise_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    context: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    notified_at: Mapped[datetime | None] = mapped_column(nullable=True)


# ---------------------------------------------------------------------------
# groups (positive-grant access control)
# ---------------------------------------------------------------------------


class Group(Base):
    """A named bag of users and agents inside one workspace.

    Access rule: a user can talk to an agent iff (∃ group G) (user ∈ G) ∧
    (agent ∈ G). No deny rules, no hierarchy — see the design doc Shane
    signed off on. The seed migration creates one `is_default=True` group
    per workspace at upgrade time (named after the workspace's
    display_name, snapshot at creation, never auto-renamed). New users +
    new agents are auto-added to that default group by the service layer.
    """

    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        # Case-insensitive uniqueness on name within the workspace — same
        # shape as agents.slack_display_name. Created in alembic with a
        # functional lower() expression that ORM-level Index can't model
        # directly; the migration is the source of truth.
        # At most one default group per workspace among active rows —
        # also enforced by partial unique index in the migration.
    )


class GroupMembership(Base):
    """Many-to-many edge: user ↔ group.

    Composite PK; FK CASCADE on both sides cleans up automatically when
    a user is deleted or a group is hard-deleted (we soft-delete groups
    via archived_at, so cascade only fires on the rare hard-delete).
    """

    __tablename__ = "group_memberships"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        PrimaryKeyConstraint("group_id", "user_id"),
        Index("ix_group_memberships_user", "user_id"),
    )


class AgentGroup(Base):
    """Many-to-many edge: agent ↔ group.

    Same shape as GroupMembership. An agent always belongs to at least
    one group when active (creation seeds the default group); removing
    the last group from an agent is allowed but makes the agent
    unreachable until at least one membership is re-added.
    """

    __tablename__ = "agent_groups"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        PrimaryKeyConstraint("group_id", "agent_id"),
        Index("ix_agent_groups_agent", "agent_id"),
    )
