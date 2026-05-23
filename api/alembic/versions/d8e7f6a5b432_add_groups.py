"""add groups + memberships + agent_groups (with default-group backfill)

Revision ID: d8e7f6a5b432
Revises: c4d3e2b1a098
Create Date: 2026-05-23

Simple positive-grant access control: groups have user members and
agent members; a user can access an agent iff they share at least one
group. Every workspace gets a default group at creation time
(snapshot of display_name), and every new user / agent auto-joins it.

Backfill on upgrade:
  - one default group per existing workspace (name = display_name)
  - membership rows for every active user → their workspace's default
  - agent_groups rows for every active agent → their workspace's default

No deny rules, no hierarchy.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e7f6a5b432"
down_revision: Union[str, None] = "c4d3e2b1a098"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_groups_workspace_name_active "
        "ON groups (workspace_id, lower(name)) "
        "WHERE archived_at IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_groups_workspace_default_active "
        "ON groups (workspace_id) "
        "WHERE is_default AND archived_at IS NULL"
    )

    op.create_table(
        "group_memberships",
        sa.Column(
            "group_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("group_id", "user_id"),
    )
    op.create_index(
        "ix_group_memberships_user", "group_memberships", ["user_id"]
    )

    op.create_table(
        "agent_groups",
        sa.Column(
            "group_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("group_id", "agent_id"),
    )
    op.create_index(
        "ix_agent_groups_agent", "agent_groups", ["agent_id"]
    )

    # ---- Backfill ---------------------------------------------------
    # For each existing workspace: create one default group, named from
    # the workspace's display_name (truncated to 64 chars). Then add all
    # of that workspace's active users and active agents to it.
    #
    # Postgres CTEs keep this in one pass — no Python iteration over
    # rows. Safe to re-run after a rollback (idempotent — guards on
    # existence of a default group).
    op.execute(
        """
        WITH new_groups AS (
            INSERT INTO groups (workspace_id, name, is_default)
            SELECT
                w.id,
                left(w.display_name, 64),
                true
            FROM workspaces w
            WHERE w.archived_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM groups g
                  WHERE g.workspace_id = w.id
                    AND g.is_default
                    AND g.archived_at IS NULL
              )
            RETURNING id, workspace_id
        ),
        new_memberships AS (
            INSERT INTO group_memberships (group_id, user_id)
            SELECT ng.id, u.id
            FROM new_groups ng
            JOIN users u
              ON u.workspace_id = ng.workspace_id
             AND u.deleted_at IS NULL
            RETURNING 1
        )
        INSERT INTO agent_groups (group_id, agent_id)
        SELECT ng.id, a.id
        FROM new_groups ng
        JOIN agents a
          ON a.workspace_id = ng.workspace_id
         AND a.archived_at IS NULL;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_agent_groups_agent", table_name="agent_groups")
    op.drop_table("agent_groups")
    op.drop_index("ix_group_memberships_user", table_name="group_memberships")
    op.drop_table("group_memberships")
    op.execute("DROP INDEX IF EXISTS ix_groups_workspace_default_active")
    op.execute("DROP INDEX IF EXISTS ix_groups_workspace_name_active")
    op.drop_table("groups")
