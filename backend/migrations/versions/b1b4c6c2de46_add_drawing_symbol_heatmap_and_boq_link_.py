"""add drawing symbol heatmap and boq link tables

Revision ID: b1b4c6c2de46
Revises: 50d3654327f1
Create Date: 2026-08-02 10:36:22.388955
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "b1b4c6c2de46"
down_revision: str | Sequence[str] | None = "50d3654327f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements(table):
            op.execute(stmt)


def upgrade() -> None:
    op.add_column(
        "drawings",
        sa.Column("symbol_suggestions", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "drawings",
        sa.Column("heatmap", sa.JSON(), nullable=False, server_default="{}"),
    )

    op.create_table(
        "drawing_boq_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("drawing_id", sa.Uuid(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("source_quote", sa.Text(), nullable=True),
        sa.Column("item_code", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=True),
        sa.Column("rate_minor", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
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
        sa.ForeignKeyConstraint(["drawing_id"], ["drawings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_drawing_boq_links_drawing_id"), "drawing_boq_links", ["drawing_id"], unique=False)
    op.create_index(op.f("ix_drawing_boq_links_opportunity_id"), "drawing_boq_links", ["opportunity_id"], unique=False)
    op.create_index(op.f("ix_drawing_boq_links_workspace_id"), "drawing_boq_links", ["workspace_id"], unique=False)
    _rls("drawing_boq_links")


def downgrade() -> None:
    op.drop_table("drawing_boq_links")
    op.drop_column("drawings", "symbol_suggestions")
    op.drop_column("drawings", "heatmap")
