"""add report_templates

Revision ID: d7203b5c7f0a
Revises: bfe694cd3af1
Create Date: 2026-08-02 11:24:59.694171
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "d7203b5c7f0a"
down_revision: str | Sequence[str] | None = "bfe694cd3af1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements(table):
            op.execute(stmt)


def upgrade() -> None:
    op.create_table(
        "report_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("primary_color", sa.String(), nullable=True),
        sa.Column("accent_color", sa.String(), nullable=True),
        sa.Column("logo_url", sa.String(), nullable=True),
        sa.Column("watermark_text", sa.String(), nullable=True),
        sa.Column("footer_text", sa.String(), nullable=True),
        sa.Column("report_title", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_report_templates_workspace_id"),
        "report_templates",
        ["workspace_id"],
        unique=False,
    )
    _rls("report_templates")


def downgrade() -> None:
    op.drop_index(
        op.f("ix_report_templates_workspace_id"), table_name="report_templates"
    )
    op.drop_table("report_templates")
