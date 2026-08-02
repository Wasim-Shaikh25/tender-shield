"""add drawing tables

Revision ID: 50d3654327f1
Revises: 6dd2ea16bfc9
Create Date: 2026-08-02 10:23:46.894144
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "50d3654327f1"
down_revision: str | Sequence[str] | None = "6dd2ea16bfc9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements(table):
            op.execute(stmt)


def upgrade() -> None:
    op.create_table(
        "drawings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("drawing_number", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("revision", sa.String(), nullable=True),
        sa.Column("revision_date", sa.String(), nullable=True),
        sa.Column("discipline", sa.String(), nullable=True),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("title_block", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(), nullable=False, server_default="current"),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["drawings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_drawings_drawing_number"), "drawings", ["drawing_number"], unique=False)
    op.create_index(op.f("ix_drawings_opportunity_id"), "drawings", ["opportunity_id"], unique=False)
    op.create_index(op.f("ix_drawings_supersedes_id"), "drawings", ["supersedes_id"], unique=False)
    op.create_index(op.f("ix_drawings_workspace_id"), "drawings", ["workspace_id"], unique=False)
    _rls("drawings")

    op.create_table(
        "drawing_comparisons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("current_drawing_id", sa.Uuid(), nullable=False),
        sa.Column("previous_drawing_id", sa.Uuid(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("changed_pages", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("changed_regions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["current_drawing_id"], ["drawings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["previous_drawing_id"], ["drawings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_drawing_comparisons_current_drawing_id"), "drawing_comparisons", ["current_drawing_id"], unique=False)
    op.create_index(op.f("ix_drawing_comparisons_opportunity_id"), "drawing_comparisons", ["opportunity_id"], unique=False)
    op.create_index(op.f("ix_drawing_comparisons_previous_drawing_id"), "drawing_comparisons", ["previous_drawing_id"], unique=False)
    op.create_index(op.f("ix_drawing_comparisons_workspace_id"), "drawing_comparisons", ["workspace_id"], unique=False)
    _rls("drawing_comparisons")


def downgrade() -> None:
    op.drop_table("drawing_comparisons")
    op.drop_table("drawings")
