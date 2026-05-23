"""add workspaces.cma_default_environment_id

Revision ID: c4d3e2b1a098
Revises: b9c2e1f74a30
Create Date: 2026-05-22

Workspace-level "last used CMA environment" hint. The AgentDialog's
environment picker reads this to pre-select a default; new agent saves
write the chosen environment_id back here. No FK to a Relay-side
environments table because we don't have one — environments are
Anthropic-side resources, identified by string ID.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d3e2b1a098"
down_revision: Union[str, None] = "b9c2e1f74a30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("cma_default_environment_id", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "cma_default_environment_id")
