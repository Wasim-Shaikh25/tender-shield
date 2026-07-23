"""audit_log table (org-scoped, RLS on PostgreSQL; append-only)

Revision ID: 0006_audit
Revises: 0005_findings
Create Date: 2026-07-23

Append-only by convention + grant: production revokes UPDATE/DELETE on this
table from the app role. The migration only creates it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0006_audit"
down_revision: str | None = "0005_findings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("object_type", sa.String(), nullable=True),
        sa.Column("object_id", sa.Uuid(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_log_org_id", "audit_log", ["org_id"])

    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements("audit_log"):
            op.execute(stmt)


def downgrade() -> None:
    op.drop_table("audit_log")
