"""add rp_rag_suggestions table

Revision ID: a50a314e2702
Revises: 945105123194
Create Date: 2026-08-03 10:54:28.887869
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "a50a314e2702"
down_revision: str | Sequence[str] | None = "945105123194"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rp_rag_suggestions",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rulepack_id", sa.Uuid(), nullable=False),
        sa.Column("source_file_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("proposed_yaml", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.String(), nullable=False),
        sa.Column("source_quote", sa.String(), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["rulepack_id"], ["rulepacks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_file_id"], ["rulepack_files.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_rp_rag_suggestions_workspace_id"),
        "rp_rag_suggestions",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rp_rag_suggestions_rulepack_id"),
        "rp_rag_suggestions",
        ["rulepack_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rp_rag_suggestions_source_file_id"),
        "rp_rag_suggestions",
        ["source_file_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rp_rag_suggestions_status"),
        "rp_rag_suggestions",
        ["status"],
        unique=False,
    )

    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements("rp_rag_suggestions"):
            op.execute(stmt)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS workspace_isolation ON rp_rag_suggestions")
        op.execute("ALTER TABLE rp_rag_suggestions DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        op.f("ix_rp_rag_suggestions_status"), table_name="rp_rag_suggestions"
    )
    op.drop_index(
        op.f("ix_rp_rag_suggestions_source_file_id"), table_name="rp_rag_suggestions"
    )
    op.drop_index(
        op.f("ix_rp_rag_suggestions_rulepack_id"), table_name="rp_rag_suggestions"
    )
    op.drop_index(
        op.f("ix_rp_rag_suggestions_workspace_id"), table_name="rp_rag_suggestions"
    )
    op.drop_table("rp_rag_suggestions")
