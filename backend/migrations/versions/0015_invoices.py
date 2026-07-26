"""invoices table (org-scoped, RLS on PostgreSQL) — customer-visible billing
records generated from paid events (TS-070).

Revision ID: 0015_invoices
Revises: 0014_doc_chunks
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0015_invoices"
down_revision: str | None = "0014_doc_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_number", sa.String(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_invoice_id", sa.String(), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("invoice_number", name="uq_invoices_invoice_number"),
    )
    op.create_index("ix_invoices_org_id", "invoices", ["org_id"])
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"])

    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements("invoices"):
            op.execute(stmt)


def downgrade() -> None:
    op.drop_table("invoices")
