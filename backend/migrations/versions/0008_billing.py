"""billing tables: usage_events, payment_log, webhook_events

Revision ID: 0008_billing
Revises: 0007_artifacts
Create Date: 2026-07-23

payment_log is the append-only financial ledger (Doc §16.5): production revokes
UPDATE/DELETE on it. All three are org-scoped (RLS on Postgres).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0008_billing"
down_revision: str | None = "0007_artifacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BIGID = sa.BigInteger().with_variant(sa.Integer, "sqlite")
_ORG_SCOPED = ("usage_events", "payment_log", "webhook_events")


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", _BIGID, primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.String(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ref_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_usage_events_org_id", "usage_events", ["org_id"])
    op.create_table(
        "payment_log",
        sa.Column("id", _BIGID, primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_event_id", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_log_org_id", "payment_log", ["org_id"])
    op.create_index("ix_payment_log_event_id", "payment_log", ["provider_event_id"])
    op.create_table(
        "webhook_events",
        sa.Column("id", _BIGID, primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_event_id", sa.String(), nullable=False, unique=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    if op.get_bind().dialect.name == "postgresql":
        for table in _ORG_SCOPED:
            for stmt in rls_statements(table):
                op.execute(stmt)


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("payment_log")
    op.drop_table("usage_events")
