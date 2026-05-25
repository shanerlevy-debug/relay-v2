"""Group CRUD + membership operations + access check.

Positive-grant access control:
  - A user can talk to an agent iff (∃ group G) (user ∈ G) ∧ (agent ∈ G).
  - "COMPANYNAME" is the default group, one per workspace, name snapshotted
    from workspace.display_name at workspace creation. Never auto-renamed.
  - New users + new agents auto-join the default group via the seeding
    helpers below; the bridge looks up `default_group_for_workspace` when
    a Slack message arrives from a user with no Relay account.

No deny rules. No hierarchy.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from relay_api.core.config import settings
from relay_api.db.models import (
    Agent,
    AgentGroup,
    Group,
    GroupMembership,
    User,
    Workspace,
)

_MAX_NAME_LEN = 64
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _\-]*$")


class GroupError(Exception):
    def __init__(self, message: str, *, code: str = "invalid"):
        super().__init__(message)
        self.code = code


def _validate_name(value: str) -> str:
    """Group names are user-visible. Allow letters / digits / spaces /
    underscores / hyphens — no slashes, slugs, or punctuation that would
    confuse the addressable-name router later (groups aren't addressable
    today but we keep the door open)."""
    value = value.strip()
    if not value:
        raise GroupError("name required", code="invalid_name")
    if len(value) > _MAX_NAME_LEN:
        raise GroupError(
            f"name must be {_MAX_NAME_LEN} characters or fewer",
            code="invalid_name",
        )
    if not _NAME_RE.match(value):
        raise GroupError(
            "name must start with a letter or digit; letters / digits / "
            "spaces / hyphens / underscores only",
            code="invalid_name",
        )
    return value


# ---------------------------------------------------------------------------
# Default group lifecycle
# ---------------------------------------------------------------------------


def create_default_group(
    db: Session,
    *,
    workspace: Workspace,
) -> Group:
    """Insert the workspace's default group, named from display_name.
    Truncated to fit the 64-char column. Called from `services.auth.signup`
    + the Add-to-Slack bootstrap path. Idempotent — returns the existing
    default if one is already present."""
    existing = default_group_for_workspace(db, workspace_id=workspace.id)
    if existing is not None:
        return existing
    name = (workspace.display_name or "Default").strip()[:_MAX_NAME_LEN]
    if not name:
        name = "Default"
    g = Group(
        workspace_id=workspace.id,
        name=name,
        is_default=True,
    )
    db.add(g)
    db.flush()
    return g


def default_group_for_workspace(
    db: Session,
    *,
    workspace_id: uuid.UUID,
) -> Group | None:
    """Active default group for a workspace, or None if absent (shouldn't
    happen in practice — the migration backfills + signup seeds — but
    callers must handle it)."""
    return db.execute(
        select(Group)
        .where(Group.workspace_id == workspace_id)
        .where(Group.is_default.is_(True))
        .where(Group.archived_at.is_(None))
    ).scalar_one_or_none()


def add_user_to_default_group(
    db: Session,
    *,
    user: User,
) -> None:
    """Membership in the workspace's default group. Called from every
    user-creation path. No-ops if no default group exists or the user is
    already a member."""
    default = default_group_for_workspace(db, workspace_id=user.workspace_id)
    if default is None:
        return
    add_user_to_group(db, group=default, user_id=user.id)


def add_agent_to_default_group(
    db: Session,
    *,
    agent: Agent,
) -> None:
    """Same shape as the user version — auto-bucket new agents into the
    workspace's default group at creation time."""
    default = default_group_for_workspace(db, workspace_id=agent.workspace_id)
    if default is None:
        return
    add_agent_to_group(db, group=default, agent_id=agent.id)


# ---------------------------------------------------------------------------
# Group CRUD
# ---------------------------------------------------------------------------


def list_groups(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    include_archived: bool = False,
) -> list[Group]:
    """Workspace groups, oldest-first. Active-only by default. Default
    group always sorts first regardless of created_at."""
    stmt = (
        select(Group)
        .where(Group.workspace_id == workspace_id)
        .order_by(Group.is_default.desc(), Group.created_at)
    )
    if not include_archived:
        stmt = stmt.where(Group.archived_at.is_(None))
    return list(db.execute(stmt).scalars())


def get_group(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    group_id: uuid.UUID,
) -> Group | None:
    return db.execute(
        select(Group)
        .where(Group.id == group_id)
        .where(Group.workspace_id == workspace_id)
    ).scalar_one_or_none()


def create_group(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    name: str,
) -> Group:
    """Create a non-default group. Default groups are created via
    create_default_group only — admins can't manually create a second
    default (partial unique index would reject anyway)."""
    name = _validate_name(name)
    # Case-insensitive collision check among active groups
    collision = db.execute(
        select(Group)
        .where(Group.workspace_id == workspace_id)
        .where(Group.archived_at.is_(None))
        .where(func.lower(Group.name) == name.lower())
    ).scalar_one_or_none()
    if collision is not None:
        raise GroupError(
            f"a group named {name!r} already exists",
            code="name_in_use",
        )
    g = Group(workspace_id=workspace_id, name=name, is_default=False)
    db.add(g)
    db.flush()
    return g


def rename_group(
    db: Session,
    *,
    group: Group,
    name: str,
) -> Group:
    new_name = _validate_name(name)
    if new_name.lower() == group.name.lower():
        group.name = new_name  # case-only change is allowed
        return group
    collision = db.execute(
        select(Group)
        .where(Group.workspace_id == group.workspace_id)
        .where(Group.archived_at.is_(None))
        .where(func.lower(Group.name) == new_name.lower())
        .where(Group.id != group.id)
    ).scalar_one_or_none()
    if collision is not None:
        raise GroupError(
            f"a group named {new_name!r} already exists",
            code="name_in_use",
        )
    group.name = new_name
    return group


def archive_group(
    db: Session,
    *,
    group: Group,
) -> None:
    """Soft-delete a group. Default groups can't be archived — they're the
    fallback for unknown Slack users."""
    if group.is_default:
        raise GroupError(
            "the default group can't be archived",
            code="default_group",
        )
    if group.archived_at is not None:
        return
    group.archived_at = datetime.now(UTC)
    db.flush()


# ---------------------------------------------------------------------------
# Membership operations
# ---------------------------------------------------------------------------


def add_user_to_group(
    db: Session,
    *,
    group: Group,
    user_id: uuid.UUID,
) -> None:
    """Idempotent — re-adding an existing member is a no-op."""
    existing = db.execute(
        select(GroupMembership)
        .where(GroupMembership.group_id == group.id)
        .where(GroupMembership.user_id == user_id)
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(GroupMembership(group_id=group.id, user_id=user_id))


def remove_user_from_group(
    db: Session,
    *,
    group: Group,
    user_id: uuid.UUID,
) -> None:
    """Remove a user's membership. No-op if not a member."""
    existing = db.execute(
        select(GroupMembership)
        .where(GroupMembership.group_id == group.id)
        .where(GroupMembership.user_id == user_id)
    ).scalar_one_or_none()
    if existing is None:
        return
    db.delete(existing)


def add_agent_to_group(
    db: Session,
    *,
    group: Group,
    agent_id: uuid.UUID,
) -> None:
    existing = db.execute(
        select(AgentGroup)
        .where(AgentGroup.group_id == group.id)
        .where(AgentGroup.agent_id == agent_id)
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(AgentGroup(group_id=group.id, agent_id=agent_id))


def remove_agent_from_group(
    db: Session,
    *,
    group: Group,
    agent_id: uuid.UUID,
) -> None:
    existing = db.execute(
        select(AgentGroup)
        .where(AgentGroup.group_id == group.id)
        .where(AgentGroup.agent_id == agent_id)
    ).scalar_one_or_none()
    if existing is None:
        return
    db.delete(existing)


# ---------------------------------------------------------------------------
# Listing helpers — what's in a group, what groups is an X in
# ---------------------------------------------------------------------------


def list_users_in_group(
    db: Session,
    *,
    group: Group,
) -> list[User]:
    return list(
        db.execute(
            select(User)
            .join(GroupMembership, GroupMembership.user_id == User.id)
            .where(GroupMembership.group_id == group.id)
            .where(User.deleted_at.is_(None))
            .order_by(User.created_at)
        ).scalars()
    )


def list_agents_in_group(
    db: Session,
    *,
    group: Group,
) -> list[Agent]:
    return list(
        db.execute(
            select(Agent)
            .join(AgentGroup, AgentGroup.agent_id == Agent.id)
            .where(AgentGroup.group_id == group.id)
            .where(Agent.archived_at.is_(None))
            .order_by(Agent.created_at)
        ).scalars()
    )


def list_groups_for_user(
    db: Session,
    *,
    user_id: uuid.UUID,
) -> list[Group]:
    return list(
        db.execute(
            select(Group)
            .join(GroupMembership, GroupMembership.group_id == Group.id)
            .where(GroupMembership.user_id == user_id)
            .where(Group.archived_at.is_(None))
            .order_by(Group.is_default.desc(), Group.created_at)
        ).scalars()
    )


def list_groups_for_agent(
    db: Session,
    *,
    agent_id: uuid.UUID,
) -> list[Group]:
    return list(
        db.execute(
            select(Group)
            .join(AgentGroup, AgentGroup.group_id == Group.id)
            .where(AgentGroup.agent_id == agent_id)
            .where(Group.archived_at.is_(None))
            .order_by(Group.is_default.desc(), Group.created_at)
        ).scalars()
    )


# ---------------------------------------------------------------------------
# Access check — called by the bridge on every routed message
# ---------------------------------------------------------------------------


AccessReason = Literal[
    "allowed",
    "unregistered",            # no Relay user matches this Slack identity
    "no_group_access",         # registered, but doesn't share a group with the agent
    "agent_no_groups",         # agent isn't in any group; unreachable
]


@dataclass(frozen=True)
class AccessDecision:
    """Result of a per-message access check. The bridge branches on `reason`
    to pick the right denial message — unregistered users get a sign-in
    link, registered-but-not-in-the-right-group users get a different
    nudge ("ask an admin to add you to a group that includes this agent")."""

    allowed: bool
    reason: AccessReason


def check_slack_user_agent_access(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    slack_user_id: str | None,
    agent_id: uuid.UUID,
) -> AccessDecision:
    """Three-state access check. The bridge uses `reason` to pick UX copy.

    Decision tree:
      1. Agent's group set empty → agent_no_groups, deny.
      2. Slack user → matching Relay user lookup:
         - found + group intersection → allowed
         - found + no intersection → no_group_access
         - not found AND RELAY_BOT_REQUIRES_SLACK_LINK → unregistered
         - not found AND permissive (legacy) → treat as default-group member
    """
    agent_group_ids = set(
        db.execute(
            select(AgentGroup.group_id)
            .where(AgentGroup.agent_id == agent_id)
            .join(Group, Group.id == AgentGroup.group_id)
            .where(Group.archived_at.is_(None))
        ).scalars()
    )
    if not agent_group_ids:
        return AccessDecision(False, "agent_no_groups")

    user: User | None = None
    if slack_user_id:
        user = db.execute(
            select(User)
            .where(User.workspace_id == workspace_id)
            .where(User.slack_user_id == slack_user_id)
            .where(User.deleted_at.is_(None))
        ).scalar_one_or_none()

    if user is not None:
        user_group_ids = set(
            db.execute(
                select(GroupMembership.group_id)
                .where(GroupMembership.user_id == user.id)
                .join(Group, Group.id == GroupMembership.group_id)
                .where(Group.archived_at.is_(None))
            ).scalars()
        )
        if user_group_ids & agent_group_ids:
            return AccessDecision(True, "allowed")
        return AccessDecision(False, "no_group_access")

    # Unknown Slack user — branch on the global enforcement toggle.
    if settings.RELAY_BOT_REQUIRES_SLACK_LINK:
        return AccessDecision(False, "unregistered")

    # Permissive (legacy) fallback — treat as default-group member.
    default = default_group_for_workspace(db, workspace_id=workspace_id)
    if default is None:
        return AccessDecision(False, "no_group_access")
    if default.id in agent_group_ids:
        return AccessDecision(True, "allowed")
    return AccessDecision(False, "no_group_access")


def slack_user_can_access_agent(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    slack_user_id: str | None,
    agent_id: uuid.UUID,
) -> bool:
    """Boolean shim — kept for any caller that only needs allow/deny.
    The bridge uses check_slack_user_agent_access directly to get the
    reason code for UX branching."""
    return check_slack_user_agent_access(
        db,
        workspace_id=workspace_id,
        slack_user_id=slack_user_id,
        agent_id=agent_id,
    ).allowed
