"""add document_class_acls and defined_terms

Revision ID: bfe694cd3af1
Revises: b1b4c6c2de46
Create Date: 2026-08-02 11:13:07.715147
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "bfe694cd3af1"
down_revision: str | Sequence[str] | None = "b1b4c6c2de46"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements(table):
            op.execute(stmt)


def upgrade() -> None:
    op.create_table(
        "document_class_acls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_class", sa.String(), nullable=False),
        sa.Column("min_role", sa.String(), nullable=False, server_default="viewer"),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "document_class"),
    )
    op.create_index(
        op.f("ix_document_class_acls_workspace_id"),
        "document_class_acls",
        ["workspace_id"],
        unique=False,
    )
    _rls("document_class_acls")

    op.create_table(
        "defined_terms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("term", sa.String(), nullable=False),
        sa.Column("definition", sa.String(), nullable=False),
        sa.Column("source_quote", sa.String(), nullable=True),
        sa.Column("source_clause_ref", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_defined_terms_document_id"),
        "defined_terms",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_defined_terms_opportunity_id"),
        "defined_terms",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_defined_terms_workspace_id"),
        "defined_terms",
        ["workspace_id"],
        unique=False,
    )
    _rls("defined_terms")


def downgrade() -> None:
    op.drop_index(op.f("ix_defined_terms_workspace_id"), table_name="defined_terms")
    op.drop_index(op.f("ix_defined_terms_opportunity_id"), table_name="defined_terms")
    op.drop_index(op.f("ix_defined_terms_document_id"), table_name="defined_terms")
    op.drop_table("defined_terms")
    op.drop_index(
        op.f("ix_document_class_acls_workspace_id"), table_name="document_class_acls"
    )
    op.drop_table("document_class_acls")
