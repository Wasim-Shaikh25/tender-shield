"""ingestion tables: opportunities, documents (org-scoped, RLS on PostgreSQL)

Revision ID: 0002_ingestion
Revises: 0001_auth
Create Date: 2026-07-23

Both tables are org-scoped, so on PostgreSQL they get the non-negotiable
org-isolation RLS policy (Doc §3.2). SQLite (CI up/down check) has no RLS, so
those statements are skipped there.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0002_ingestion"
down_revision: str | None = "0001_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ORG_SCOPED = ("opportunities", "documents")


def upgrade() -> None:
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("employer", sa.String(), nullable=True),
        sa.Column("employer_family", sa.String(), nullable=True),
        sa.Column("jurisdiction", sa.String(), nullable=False, server_default="IN"),
        sa.Column("contract_form", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="reviewing"),
        sa.Column("rulepack_version", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_opportunities_org_id", "opportunities", ["org_id"])
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), sa.ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False, server_default="other"),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("s3_key", sa.String(), nullable=False, server_default=""),
        sa.Column("sha256", sa.String(), nullable=False, server_default=""),
        sa.Column("pages", sa.Integer(), nullable=True),
        sa.Column("ocr_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("supersedes", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_org_id", "documents", ["org_id"])
    op.create_index("ix_documents_opportunity_id", "documents", ["opportunity_id"])

    if op.get_bind().dialect.name == "postgresql":
        for table in _ORG_SCOPED:
            for stmt in rls_statements(table):
                op.execute(stmt)


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("opportunities")
