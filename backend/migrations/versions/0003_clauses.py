"""clauses table (org-scoped, RLS on PostgreSQL)

Revision ID: 0003_clauses
Revises: 0002_ingestion
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0003_clauses"
down_revision: str | None = "0002_ingestion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clauses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), sa.ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("clause_ref", sa.String(), nullable=True),
        sa.Column("heading", sa.String(), nullable=True),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("page_from", sa.Integer(), nullable=True),
        sa.Column("page_to", sa.Integer(), nullable=True),
        sa.Column("cross_refs", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_clauses_org_id", "clauses", ["org_id"])
    op.create_index("ix_clauses_document_id", "clauses", ["document_id"])
    op.create_index("ix_clauses_opportunity_id", "clauses", ["opportunity_id"])

    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements("clauses"):
            op.execute(stmt)


def downgrade() -> None:
    op.drop_table("clauses")
