"""doc_chunks table (org-scoped, RLS on PostgreSQL) — page-level text chunks for
search/crossref and the assistant (TS-068).

Revision ID: 0014_doc_chunks
Revises: 0013_org_commercial_standards
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0014_doc_chunks"
down_revision: str | None = "0013_org_commercial_standards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "doc_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False, default=1),
        sa.Column("text", sa.String(), nullable=False),
    )
    op.create_index("ix_doc_chunks_org_id", "doc_chunks", ["org_id"])
    op.create_index("ix_doc_chunks_document_id", "doc_chunks", ["document_id"])
    op.create_index("ix_doc_chunks_opportunity_id", "doc_chunks", ["opportunity_id"])

    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements("doc_chunks"):
            op.execute(stmt)


def downgrade() -> None:
    op.drop_table("doc_chunks")
