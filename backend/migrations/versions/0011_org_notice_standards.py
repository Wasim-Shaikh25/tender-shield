"""org_notice_standards table (org-scoped, RLS on PostgreSQL) — custom standards

Revision ID: 0011_org_notice_standards
Revises: 0010_baselines
Create Date: 2026-07-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0011_org_notice_standards"
down_revision: str | None = "0010_baselines"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "org_notice_standards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False, server_default="prevail"),
        sa.Column("categories", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", name="uq_org_notice_standards_org"),
    )
    op.create_index("ix_org_notice_standards_org_id", "org_notice_standards", ["org_id"])

    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements("org_notice_standards"):
            op.execute(stmt)


def downgrade() -> None:
    op.drop_table("org_notice_standards")
