"""Per-workspace agent registry service.

Replaces v1's `agents.yaml` git-ops flow with a database table the admin
edits via the UI. The bridge reads from this table on each Slack message
to find which CMA agent handles a given slug.

is_default exclusivity: at most one active agent per workspace is the
default. Setting `is_default=True` on agent A clears it on any other
active agent in the same workspace (in the same transaction).

25-agent cap: counted as active (archived_at IS NULL) agents only.
Archived agents don't take a seat.
"""
from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from relay_api.core.config import settings
from relay_api.db.models import Agent

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_MAX_SLUG_LEN = 64
_MAX_DISPLAY_NAME_LEN = 30


class AgentError(Exception):
    """Expected agent-CRUD failures. `code` for UI branching."""

    def __init__(self, message: str, *, code: str = "invalid"):
        super().__init__(message)
        self.code = code


def _now() -> datetime:
    return datetime.now(UTC)


def _validate_slug(slug: str) -> str:
    slug = slug.strip().lower()
    if not slug or len(slug) > _MAX_SLUG_LEN:
        raise AgentError(
            f"slug must be 1–{_MAX_SLUG_LEN} chars",
            code="invalid_slug",
        )
    if not _SLUG_RE.match(slug):
        raise AgentError(
            "slug must start with a letter and contain only lowercase "
            "letters, digits, and hyphens",
            code="invalid_slug",
        )
    return slug


def count_active_agents(db: Session, *, workspace_id: uuid.UUID) -> int:
    return int(
        db.execute(
            select(func.count(Agent.id))
            .where(Agent.workspace_id == workspace_id)
            .where(Agent.archived_at.is_(None))
        ).scalar_one()
    )


def list_agents(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    include_archived: bool = False,
) -> list[Agent]:
    """Workspace agents, oldest-first. Active-only by default."""
    stmt = (
        select(Agent)
        .where(Agent.workspace_id == workspace_id)
        .order_by(Agent.created_at)
    )
    if not include_archived:
        stmt = stmt.where(Agent.archived_at.is_(None))
    return list(db.execute(stmt).scalars())


def get_agent_by_id(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> Agent | None:
    return db.execute(
        select(Agent)
        .where(Agent.id == agent_id)
        .where(Agent.workspace_id == workspace_id)
    ).scalar_one_or_none()


def get_agent_by_slug(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    slug: str,
) -> Agent | None:
    """Bridge's lookup path on each incoming Slack message."""
    return db.execute(
        select(Agent)
        .where(Agent.workspace_id == workspace_id)
        .where(Agent.slug == slug.lower())
        .where(Agent.archived_at.is_(None))
    ).scalar_one_or_none()


def find_default_agent(
    db: Session,
    *,
    workspace_id: uuid.UUID,
) -> Agent | None:
    """Default agent for untagged Slack messages, or None if no default
    is set (bridge handles that with a user-visible error message)."""
    return db.execute(
        select(Agent)
        .where(Agent.workspace_id == workspace_id)
        .where(Agent.is_default.is_(True))
        .where(Agent.archived_at.is_(None))
    ).scalar_one_or_none()


def _clear_default(db: Session, *, workspace_id: uuid.UUID) -> None:
    """Clear is_default on every active agent in the workspace.

    Used before setting a new default — partial unique index would otherwise
    reject the conflict at flush time.
    """
    db.execute(
        update(Agent)
        .where(Agent.workspace_id == workspace_id)
        .where(Agent.is_default.is_(True))
        .where(Agent.archived_at.is_(None))
        .values(is_default=False)
    )


def _check_display_name_available(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    display_name: str,
    exclude_agent_id: uuid.UUID | None = None,
) -> None:
    """Raise AgentError("slack_display_name_in_use") if another active agent in
    this workspace already uses this Slack display name (case-insensitive)."""
    if not display_name:
        return
    stmt = (
        select(Agent.id)
        .where(Agent.workspace_id == workspace_id)
        .where(Agent.archived_at.is_(None))
        .where(func.lower(Agent.slack_display_name) == display_name.lower())
    )
    if exclude_agent_id is not None:
        stmt = stmt.where(Agent.id != exclude_agent_id)
    if db.execute(stmt).first() is not None:
        raise AgentError(
            f"another active agent already uses the display name "
            f"{display_name!r} in this workspace",
            code="slack_display_name_in_use",
        )


def create_agent(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    slug: str,
    anthropic_agent_id: str,
    environment_id: str,
    description: str | None = None,
    is_default: bool = False,
    slack_display_name: str | None = None,
    slack_icon_url: str | None = None,
) -> Agent:
    """Create an agent. Caller commits.

    Raises AgentError on:
        invalid_slug                  — fails the slug regex
        slug_in_use                   — workspace already has an active agent with this slug
        agent_limit_reached           — workspace at the 25-agent cap
        slack_display_name_in_use     — another active agent has this Slack name
    """
    slug = _validate_slug(slug)
    anthropic_agent_id = anthropic_agent_id.strip()
    environment_id = environment_id.strip()
    if not anthropic_agent_id:
        raise AgentError("anthropic_agent_id required", code="invalid")
    if not environment_id:
        raise AgentError("environment_id required", code="invalid")

    # Cap check
    active = count_active_agents(db, workspace_id=workspace_id)
    cap = settings.RELAY_AGENTS_PER_WORKSPACE
    if active >= cap:
        raise AgentError(
            f"workspace is at the {cap}-agent limit (Enterprise unlocks more)",
            code="agent_limit_reached",
        )

    # Slug uniqueness — check explicitly so we can return a clean error
    # rather than relying on the partial unique index throwing IntegrityError.
    existing = get_agent_by_slug(db, workspace_id=workspace_id, slug=slug)
    if existing is not None:
        raise AgentError(
            f"an active agent named {slug!r} already exists in this workspace",
            code="slug_in_use",
        )

    # Display-name uniqueness (independent of slug — they're different identifiers).
    if slack_display_name:
        _check_display_name_available(
            db, workspace_id=workspace_id, display_name=slack_display_name
        )

    # If this one is the default, clear any existing default first.
    if is_default:
        _clear_default(db, workspace_id=workspace_id)

    agent = Agent(
        workspace_id=workspace_id,
        slug=slug,
        anthropic_agent_id=anthropic_agent_id,
        environment_id=environment_id,
        description=description,
        is_default=is_default,
        slack_display_name=slack_display_name,
        slack_icon_url=slack_icon_url,
    )
    db.add(agent)
    db.flush()
    return agent


def update_agent(
    db: Session,
    *,
    agent: Agent,
    slug: str | None = None,
    anthropic_agent_id: str | None = None,
    environment_id: str | None = None,
    description: str | None = None,
    is_default: bool | None = None,
    fields_set: set[str] | None = None,
    slack_display_name: str | None = None,
    slack_icon_url: str | None = None,
) -> Agent:
    """Update fields. Pass `None` for legacy fields to leave them unchanged.

    For Slack persona fields (`slack_display_name`, `slack_icon_url`) the
    "leave unchanged vs clear" distinction matters — passing `None`
    explicitly should *clear* the column, while omitting the key entirely
    should leave it alone. The route passes `fields_set` (a set of field
    names actually present in the inbound request body) to disambiguate.

    Raises AgentError on slug collisions or invalid slug shape.
    """
    if agent.archived_at is not None:
        raise AgentError("cannot edit an archived agent", code="archived")

    fs = fields_set if fields_set is not None else set()

    if slug is not None:
        new_slug = _validate_slug(slug)
        if new_slug != agent.slug:
            collision = get_agent_by_slug(
                db, workspace_id=agent.workspace_id, slug=new_slug
            )
            if collision is not None and collision.id != agent.id:
                raise AgentError(
                    f"an active agent named {new_slug!r} already exists",
                    code="slug_in_use",
                )
            agent.slug = new_slug

    if anthropic_agent_id is not None:
        v = anthropic_agent_id.strip()
        if not v:
            raise AgentError("anthropic_agent_id cannot be empty", code="invalid")
        agent.anthropic_agent_id = v

    if environment_id is not None:
        v = environment_id.strip()
        if not v:
            raise AgentError("environment_id cannot be empty", code="invalid")
        agent.environment_id = v

    if description is not None:
        agent.description = description.strip() or None

    if is_default is not None:
        if is_default and not agent.is_default:
            _clear_default(db, workspace_id=agent.workspace_id)
        agent.is_default = bool(is_default)

    # Persona fields use the present-in-request sentinel.
    if "slack_display_name" in fs:
        if slack_display_name:
            _check_display_name_available(
                db,
                workspace_id=agent.workspace_id,
                display_name=slack_display_name,
                exclude_agent_id=agent.id,
            )
        agent.slack_display_name = slack_display_name or None

    if "slack_icon_url" in fs:
        agent.slack_icon_url = slack_icon_url or None

    db.flush()
    return agent


def archive_agent(db: Session, *, agent: Agent) -> None:
    """Soft-delete the agent. Active threads pinned to it will continue to
    work for their current session but will route to the default agent on
    new messages."""
    if agent.archived_at is not None:
        return
    agent.archived_at = _now()
    # An archived agent shouldn't keep its default flag — frees the slot
    # for another agent to claim default.
    agent.is_default = False
    db.flush()
