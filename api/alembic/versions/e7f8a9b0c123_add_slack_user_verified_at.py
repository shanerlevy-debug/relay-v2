"""add users.slack_user_verified_at

Revision ID: e7f8a9b0c123
Revises: d8e7f6a5b432
Create Date: 2026-05-24

Distinguishes Slack-OIDC-verified bindings (timestamp populated) from
manually-set ones (NULL). Bridge access check uses the column's
presence as the gate for "this user has cryptographic proof of Slack
identity, allow them to use the bot."
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7f8a9b0c123"
down_revision: Union[str, None] = "d8e7f6a5b432"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("slack_user_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "slack_user_verified_at")
