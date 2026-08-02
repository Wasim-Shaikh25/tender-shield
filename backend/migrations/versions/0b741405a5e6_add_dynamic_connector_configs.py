"""add dynamic_connector_configs

Revision ID: 0b741405a5e6
Revises: 0f569660f08a
Create Date: 2026-08-02 12:12:37.332722
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0b741405a5e6"
down_revision: str | Sequence[str] | None = "0f569660f08a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements(table):
            op.execute(stmt)


def upgrade() -> None:
    op.create_table(
        "dynamic_connector_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("auth_type", sa.String(), nullable=False),
        sa.Column("auth_config", sa.JSON(), nullable=True),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("pagination", sa.JSON(), nullable=True),
        sa.Column("mappings", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            onupdate=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dynamic_connector_configs_workspace_id"),
        "dynamic_connector_configs",
        ["workspace_id"],
        unique=False,
    )
    _rls("dynamic_connector_configs")


def downgrade() -> None:
    op.drop_index(
        op.f("ix_dynamic_connector_configs_workspace_id"),
        table_name="dynamic_connector_configs",
    )
    op.drop_table("dynamic_connector_configs")
