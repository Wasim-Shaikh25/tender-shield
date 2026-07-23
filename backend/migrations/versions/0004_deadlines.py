"""deadlines table (org-scoped, RLS on PostgreSQL)

Revision ID: 0004_deadlines
Revises: 0003_clauses
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0004_deadlines"
down_revision: str | None = "0003_clauses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deadlines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), sa.ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_quote", sa.String(), nullable=True),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_deadlines_org_id", "deadlines", ["org_id"])
    op.create_index("ix_deadlines_opportunity_id", "deadlines", ["opportunity_id"])

    # Denormalized deadline anchors on the opportunity for the board countdown.
    op.add_column("opportunities", sa.Column("submission_due", sa.DateTime(timezone=True), nullable=True))
    op.add_column("opportunities", sa.Column("clarification_due", sa.DateTime(timezone=True), nullable=True))

    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements("deadlines"):
            op.execute(stmt)


def downgrade() -> None:
    op.drop_column("opportunities", "clarification_due")
    op.drop_column("opportunities", "submission_due")
    op.drop_table("deadlines")
