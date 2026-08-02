"""add advisor tables

Revision ID: 6984d8c7fad3
Revises: 3fe9087a4fe0
Create Date: 2026-08-02 05:10:41.456969
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "6984d8c7fad3"
down_revision: str | Sequence[str] | None = "3fe9087a4fe0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements(table):
            op.execute(stmt)


def upgrade() -> None:
    op.create_table(
        "advisor_clients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("billing_rate", sa.String(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_advisor_clients_client_workspace_id"),
        "advisor_clients",
        ["client_workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisor_clients_workspace_id"),
        "advisor_clients",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "advisor_review_queue",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_workspace_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_to", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_advisor_review_queue_client_workspace_id"),
        "advisor_review_queue",
        ["client_workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisor_review_queue_opportunity_id"),
        "advisor_review_queue",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisor_review_queue_workspace_id"),
        "advisor_review_queue",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "advisor_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("client_workspace_id", sa.Uuid(), nullable=True),
        sa.Column("theme", sa.JSON(), nullable=True),
        sa.Column("header_text", sa.Text(), nullable=True),
        sa.Column("footer_text", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_advisor_templates_client_workspace_id"),
        "advisor_templates",
        ["client_workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisor_templates_workspace_id"),
        "advisor_templates",
        ["workspace_id"],
        unique=False,
    )

    for table in ("advisor_clients", "advisor_review_queue", "advisor_templates"):
        _rls(table)


def downgrade() -> None:
    for table in ("advisor_templates", "advisor_review_queue", "advisor_clients"):
        if op.get_bind().dialect.name == "postgresql":
            op.execute(f"DROP POLICY IF EXISTS workspace_isolation ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index(op.f("ix_advisor_templates_workspace_id"), table_name="advisor_templates")
    op.drop_index(
        op.f("ix_advisor_templates_client_workspace_id"), table_name="advisor_templates"
    )
    op.drop_table("advisor_templates")
    op.drop_index(
        op.f("ix_advisor_review_queue_workspace_id"), table_name="advisor_review_queue"
    )
    op.drop_index(
        op.f("ix_advisor_review_queue_opportunity_id"), table_name="advisor_review_queue"
    )
    op.drop_index(
        op.f("ix_advisor_review_queue_client_workspace_id"), table_name="advisor_review_queue"
    )
    op.drop_table("advisor_review_queue")
    op.drop_index(op.f("ix_advisor_clients_workspace_id"), table_name="advisor_clients")
    op.drop_index(
        op.f("ix_advisor_clients_client_workspace_id"), table_name="advisor_clients"
    )
    op.drop_table("advisor_clients")
