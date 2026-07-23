"""artifacts table (org-scoped, RLS on PostgreSQL)

Revision ID: 0007_artifacts
Revises: 0006_audit
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0007_artifacts"
down_revision: str | None = "0006_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), sa.ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("model_meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("opportunity_id", "kind", "version", name="uq_artifact_version"),
    )
    op.create_index("ix_artifacts_org_id", "artifacts", ["org_id"])
    op.create_index("ix_artifacts_opportunity_id", "artifacts", ["opportunity_id"])

    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements("artifacts"):
            op.execute(stmt)


def downgrade() -> None:
    op.drop_table("artifacts")
