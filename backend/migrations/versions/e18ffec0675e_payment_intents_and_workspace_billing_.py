"""payment intents and workspace billing lifecycle

Real orders + server-side price/plan binding (R-005 §B, TS-089): the webhook
now resolves the grant from payment_intents, never from provider notes.
payment_intents is deliberately NOT RLS-protected — see its model docstring
for why (same precedent as refresh_tokens/password_resets: an unauthenticated
caller presents an opaque id as its own authorization).

Also adds the workspace billing-lifecycle columns webhook dunning/grace
handling needs (R-005 §C.4, TS-097).

Revision ID: e18ffec0675e
Revises: c9ed90a8524f
Create Date: 2026-07-28 07:50:03.608737
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e18ffec0675e'
down_revision: str | None = 'c9ed90a8524f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BigId = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "payment_intents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("plan", sa.String(), nullable=True),
        sa.Column("opportunity_id", sa.Uuid(), nullable=True),
        sa.Column("list_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("discount_minor", sa.BigInteger(), nullable=False),
        sa.Column("tax_minor", sa.BigInteger(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("coupon_code", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_order_id", sa.String(), nullable=True),
        sa.Column("checkout_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        op.f("ix_payment_intents_workspace_id"), "payment_intents", ["workspace_id"]
    )
    op.create_index(
        op.f("ix_payment_intents_provider_order_id"), "payment_intents", ["provider_order_id"]
    )

    op.add_column("workspaces", sa.Column("plan_status", sa.String(), nullable=False, server_default="active"))
    op.add_column("workspaces", sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workspaces", sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workspaces", sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workspaces", sa.Column("provider_subscription_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("workspaces", "provider_subscription_id")
    op.drop_column("workspaces", "current_period_end")
    op.drop_column("workspaces", "current_period_start")
    op.drop_column("workspaces", "grace_until")
    op.drop_column("workspaces", "plan_status")

    op.drop_index(op.f("ix_payment_intents_provider_order_id"), table_name="payment_intents")
    op.drop_index(op.f("ix_payment_intents_workspace_id"), table_name="payment_intents")
    op.drop_table("payment_intents")
