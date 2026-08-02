"""add subcontract tables

Revision ID: 3fe9087a4fe0
Revises: dc67e941fd8f
Create Date: 2026-08-02 05:06:17.676675
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "3fe9087a4fe0"
down_revision: str | Sequence[str] | None = "dc67e941fd8f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements(table):
            op.execute(stmt)


def upgrade() -> None:
    op.create_table(
        "subcontracts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("subcontractor_name", sa.String(), nullable=False),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("contract_value_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("notice_buffer_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("postal_buffer_days", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_subcontracts_opportunity_id"), "subcontracts", ["opportunity_id"], unique=False
    )
    op.create_index(
        op.f("ix_subcontracts_workspace_id"), "subcontracts", ["workspace_id"], unique=False
    )

    op.create_table(
        "subcontract_clauses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subcontract_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("source_quote", sa.String(), nullable=True),
        sa.Column("present", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="unchecked"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["subcontract_id"], ["subcontracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_subcontract_clauses_subcontract_id"),
        "subcontract_clauses",
        ["subcontract_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subcontract_clauses_workspace_id"),
        "subcontract_clauses",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "subcontract_scope_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subcontract_id", sa.Uuid(), nullable=False),
        sa.Column("item_text", sa.String(), nullable=False),
        sa.Column("covered", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("source_event_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["source_event_id"], ["change_events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subcontract_id"], ["subcontracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_subcontract_scope_items_subcontract_id"),
        "subcontract_scope_items",
        ["subcontract_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subcontract_scope_items_workspace_id"),
        "subcontract_scope_items",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "subcontract_payment_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subcontract_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("certified_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("parent_payment_status", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["subcontract_id"], ["subcontracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_subcontract_payment_events_subcontract_id"),
        "subcontract_payment_events",
        ["subcontract_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subcontract_payment_events_workspace_id"),
        "subcontract_payment_events",
        ["workspace_id"],
        unique=False,
    )

    for table in (
        "subcontracts",
        "subcontract_clauses",
        "subcontract_scope_items",
        "subcontract_payment_events",
    ):
        _rls(table)


def downgrade() -> None:
    for table in (
        "subcontract_payment_events",
        "subcontract_scope_items",
        "subcontract_clauses",
        "subcontracts",
    ):
        if op.get_bind().dialect.name == "postgresql":
            op.execute(f"DROP POLICY IF EXISTS workspace_isolation ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index(
        op.f("ix_subcontract_payment_events_workspace_id"), table_name="subcontract_payment_events"
    )
    op.drop_index(
        op.f("ix_subcontract_payment_events_subcontract_id"),
        table_name="subcontract_payment_events",
    )
    op.drop_table("subcontract_payment_events")
    op.drop_index(
        op.f("ix_subcontract_scope_items_workspace_id"), table_name="subcontract_scope_items"
    )
    op.drop_index(
        op.f("ix_subcontract_scope_items_subcontract_id"), table_name="subcontract_scope_items"
    )
    op.drop_table("subcontract_scope_items")
    op.drop_index(
        op.f("ix_subcontract_clauses_workspace_id"), table_name="subcontract_clauses"
    )
    op.drop_index(
        op.f("ix_subcontract_clauses_subcontract_id"), table_name="subcontract_clauses"
    )
    op.drop_table("subcontract_clauses")
    op.drop_index(op.f("ix_subcontracts_workspace_id"), table_name="subcontracts")
    op.drop_index(op.f("ix_subcontracts_opportunity_id"), table_name="subcontracts")
    op.drop_table("subcontracts")
