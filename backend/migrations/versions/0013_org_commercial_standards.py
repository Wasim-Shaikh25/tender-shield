"""org_commercial_standards table (org-scoped, RLS on PostgreSQL) — firm policy
thresholds used to flag standard_violation findings.

Revision ID: 0013_org_commercial_standards
Revises: 0012_review_explain
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0013_org_commercial_standards"
down_revision: str | None = "0012_review_explain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "org_commercial_standards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("operator", sa.String(), nullable=False, server_default="gt"),
        sa.Column("threshold", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit", sa.String(), nullable=False, server_default="percent"),
        sa.Column("applies_to", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("org_id", "key", name="uq_org_commercial_standards_org_key"),
    )
    op.create_index("ix_org_commercial_standards_org_id", "org_commercial_standards", ["org_id"])

    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements("org_commercial_standards"):
            op.execute(stmt)


def downgrade() -> None:
    op.drop_table("org_commercial_standards")
