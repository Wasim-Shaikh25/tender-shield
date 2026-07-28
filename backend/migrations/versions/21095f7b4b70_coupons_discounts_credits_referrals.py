"""coupons discounts credits referrals

Adds the discounting mechanism the product had zero of before this (R-006,
TS-090): coupons + an append-only redemption ledger, a prepaid credit
ledger, and referral tracking. Workspace gains referral_code/trial_ends_at/
had_trial/comp_expires_at for the trial and pilot-comp mechanisms (R-006
§B.8/B.9).

`referral_codes` is deliberately NOT RLS-protected (same precedent as
`payment_intents`): a signing-up user who is not yet a member of any
workspace must be able to resolve someone else's referral code, which the
RLS-protected `workspaces` table's compound predicate would otherwise hide.
This was found the hard way — an initial version of this feature resolved
referral codes via a plain `workspaces` query and, under real Postgres with
FORCE RLS, silently found nothing for every cross-tenant signup (0 rows ever
written to `referrals`, 0 credits ever granted).

`coupon_redemptions` and `credits` are `WorkspaceScopedMixin` tables, so they
must carry RLS (CLAUDE.md's non-negotiable org-isolation invariant). This
surfaced a real, previously-latent bug in the RLS-hardening migration
(ae76edba3a7a): it is a ONE-TIME snapshot of `WORKSPACE_SCOPED_TABLES` at the
time it ran, not a self-maintaining mechanism — every `WorkspaceScopedMixin`
table added in a LATER migration silently gets no RLS at all unless that
migration explicitly enables it itself (running the full chain from scratch
against real Postgres, `ae76edba3a7a` tried to `ALTER TABLE
coupon_redemptions ...` before this migration had even created the table,
proving the snapshot is stale the moment a new scoped table is added after
it). Every future WorkspaceScopedMixin table's own migration must do this.

Revision ID: 21095f7b4b70
Revises: e4587e477606
Create Date: 2026-07-28 13:27:56.509044
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = '21095f7b4b70'
down_revision: str | None = 'e4587e477606'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BigId = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
_NEW_SCOPED_TABLES = ("coupon_redemptions", "credits")


def upgrade() -> None:
    op.add_column(
        "payment_intents",
        sa.Column("credit_applied_minor", sa.BigInteger(), nullable=False, server_default="0"),
    )

    op.create_table(
        "coupons",
        sa.Column("id", _BigId, autoincrement=True, nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("applies_to", sa.JSON(), nullable=False),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("max_per_workspace", sa.Integer(), nullable=False),
        sa.Column("redeemed_count", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("campaign", sa.String(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_coupons_code"), "coupons", ["code"])

    op.create_table(
        "coupon_redemptions",
        sa.Column("id", _BigId, autoincrement=True, nullable=False),
        sa.Column("coupon_id", _BigId, nullable=False),
        sa.Column("payment_intent_id", sa.Uuid(), nullable=True),
        sa.Column("discount_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "redeemed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_intent_id"),
    )
    op.create_index(op.f("ix_coupon_redemptions_coupon_id"), "coupon_redemptions", ["coupon_id"])
    op.create_index(
        op.f("ix_coupon_redemptions_workspace_id"), "coupon_redemptions", ["workspace_id"]
    )

    op.create_table(
        "credits",
        sa.Column("id", _BigId, autoincrement=True, nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("ref_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_credits_workspace_id"), "credits", ["workspace_id"])

    op.create_table(
        "referrals",
        sa.Column("id", _BigId, autoincrement=True, nullable=False),
        sa.Column("referrer_workspace_id", sa.Uuid(), nullable=False),
        sa.Column("referred_workspace_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("reward_minor", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referred_workspace_id"),
    )
    op.create_index(
        op.f("ix_referrals_referrer_workspace_id"), "referrals", ["referrer_workspace_id"]
    )

    op.create_table(
        "referral_codes",
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("owner_email_domain", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("workspace_id"),
    )

    op.add_column("workspaces", sa.Column("referral_code", sa.String(), nullable=True))
    with op.batch_alter_table("workspaces") as batch:
        batch.create_unique_constraint("uq_workspaces_referral_code", ["referral_code"])
    op.add_column(
        "workspaces", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "workspaces", sa.Column("had_trial", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "workspaces", sa.Column("comp_expires_at", sa.DateTime(timezone=True), nullable=True)
    )

    if op.get_bind().dialect.name == "postgresql":
        for table in _NEW_SCOPED_TABLES:
            for stmt in rls_statements(table):
                op.execute(stmt)


def downgrade() -> None:
    op.drop_column("workspaces", "comp_expires_at")
    op.drop_column("workspaces", "had_trial")
    op.drop_column("workspaces", "trial_ends_at")
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_constraint("uq_workspaces_referral_code", type_="unique")
    op.drop_column("workspaces", "referral_code")

    op.drop_table("referral_codes")

    op.drop_index(op.f("ix_referrals_referrer_workspace_id"), table_name="referrals")
    op.drop_table("referrals")

    op.drop_index(op.f("ix_credits_workspace_id"), table_name="credits")
    op.drop_table("credits")

    op.drop_index(op.f("ix_coupon_redemptions_workspace_id"), table_name="coupon_redemptions")
    op.drop_index(op.f("ix_coupon_redemptions_coupon_id"), table_name="coupon_redemptions")
    op.drop_table("coupon_redemptions")

    op.drop_index(op.f("ix_coupons_code"), table_name="coupons")
    op.drop_table("coupons")

    op.drop_column("payment_intents", "credit_applied_minor")
