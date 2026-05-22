"""add agent personas — slack_display_name + slack_icon_url

Revision ID: b9c2e1f74a30
Revises: 416554badf76
Create Date: 2026-05-22

Per-agent display name and icon for Slack `chat.postMessage` overrides.
Unique partial index on (workspace_id, lower(slack_display_name)) so
two active agents in the same workspace can't both claim the same
displayed identity in Slack.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9c2e1f74a30"
down_revision: Union[str, None] = "416554badf76"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("slack_display_name", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("slack_icon_url", sa.Text(), nullable=True),
    )
    # One display_name per workspace among active agents with one set.
    # case-insensitive to match Slack's behavior.
    op.execute(
        "CREATE UNIQUE INDEX ix_agents_workspace_display_name_active "
        "ON agents (workspace_id, lower(slack_display_name)) "
        "WHERE archived_at IS NULL AND slack_display_name IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_agents_workspace_display_name_active")
    op.drop_column("agents", "slack_icon_url")
    op.drop_column("agents", "slack_display_name")
