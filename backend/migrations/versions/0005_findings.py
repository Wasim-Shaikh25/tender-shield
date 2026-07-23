"""findings table (org-scoped, RLS on PostgreSQL)

Revision ID: 0005_findings
Revises: 0004_deadlines
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0005_findings"
down_revision: str | None = "0004_deadlines"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "findings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), sa.ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("producer", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("detail", sa.String(), nullable=False, server_default=""),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_quote", sa.String(), nullable=True),
        sa.Column("affected_trades", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("suggested_action", sa.String(), nullable=True),
        sa.Column("pattern_id", sa.String(), nullable=True),
        sa.Column("pattern_version", sa.String(), nullable=True),
        sa.Column("amount_exposure", sa.Numeric(16, 2), nullable=True),
        sa.Column("review_status", sa.String(), nullable=False, server_default="proposed"),
        sa.Column("review_note", sa.String(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
    )
    op.create_index("ix_findings_org_id", "findings", ["org_id"])
    op.create_index("ix_findings_opportunity_id", "findings", ["opportunity_id"])
    op.create_index("ix_findings_producer", "findings", ["producer"])

    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements("findings"):
            op.execute(stmt)


def downgrade() -> None:
    op.drop_table("findings")
