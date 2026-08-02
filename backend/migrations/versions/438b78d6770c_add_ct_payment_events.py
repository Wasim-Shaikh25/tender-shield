"""add ct_payment_events

Revision ID: 438b78d6770c
Revises: 4d30db0a270c
Create Date: 2026-08-02 04:33:18.892322
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "438b78d6770c"
down_revision: str | None = "4d30db0a270c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ct_payment_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("certified_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
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
        op.f("ix_ct_payment_events_opportunity_id"),
        "ct_payment_events",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ct_payment_events_workspace_id"),
        "ct_payment_events",
        ["workspace_id"],
        unique=False,
    )

    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements("ct_payment_events"):
            op.execute(stmt)


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ct_payment_events_workspace_id"), table_name="ct_payment_events"
    )
    op.drop_index(
        op.f("ix_ct_payment_events_opportunity_id"), table_name="ct_payment_events"
    )
    op.drop_table("ct_payment_events")
