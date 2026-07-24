"""baselines table (org-scoped, RLS on PostgreSQL) — Phase-2 baseline lock

Revision ID: 0010_baselines
Revises: 0009_mfa
Create Date: 2026-07-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0010_baselines"
down_revision: str | None = "0009_mfa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "baselines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column(
            "opportunity_id",
            sa.Uuid(),
            sa.ForeignKey("opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="tender"),
        sa.Column("content_sha256", sa.String(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("sealed_by", sa.Uuid(), nullable=True),
        sa.Column("sealed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("opportunity_id", "version", name="uq_baselines_opp_version"),
    )
    op.create_index("ix_baselines_org_id", "baselines", ["org_id"])
    op.create_index("ix_baselines_opportunity_id", "baselines", ["opportunity_id"])

    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements("baselines"):
            op.execute(stmt)


def downgrade() -> None:
    op.drop_table("baselines")
