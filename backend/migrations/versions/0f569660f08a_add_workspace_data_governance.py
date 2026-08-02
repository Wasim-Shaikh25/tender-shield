"""add workspace_data_governance

Revision ID: 0f569660f08a
Revises: d7203b5c7f0a
Create Date: 2026-08-02 11:54:16.051509
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0f569660f08a"
down_revision: str | Sequence[str] | None = "d7203b5c7f0a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements(table):
            op.execute(stmt)


def upgrade() -> None:
    op.create_table(
        "workspace_data_governance",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("data_region", sa.String(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.Column("archive_after_days", sa.Integer(), nullable=True),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("encryption_at_rest", sa.String(), nullable=False, server_default="none"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id"),
    )
    op.create_index(
        op.f("ix_workspace_data_governance_workspace_id"),
        "workspace_data_governance",
        ["workspace_id"],
        unique=False,
    )
    _rls("workspace_data_governance")


def downgrade() -> None:
    op.drop_index(
        op.f("ix_workspace_data_governance_workspace_id"),
        table_name="workspace_data_governance",
    )
    op.drop_table("workspace_data_governance")
