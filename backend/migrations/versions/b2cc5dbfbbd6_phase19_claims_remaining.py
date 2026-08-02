"""phase19_claims_remaining

Revision ID: b2cc5dbfbbd6
Revises: 00023291b095
Create Date: 2026-08-02 03:12:29.087502
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "b2cc5dbfbbd6"
down_revision: str | None = "00023291b095"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # TS-267: claim-level opposing-party marker.
    op.add_column("claims", sa.Column("claimant_party", sa.String(), nullable=True))

    # TS-270: site-evidence metadata (geolocation, quality prompts).
    op.add_column(
        "evidence_records",
        sa.Column("record_metadata", sa.JSON(), nullable=False, server_default="{}"),
    )

    # TS-269: recovered claim value feed to north-star metric.
    op.create_table(
        "oc_claim_recoveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("recovered_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id"),
    )
    op.create_index(
        op.f("ix_oc_claim_recoveries_opportunity_id"),
        "oc_claim_recoveries",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oc_claim_recoveries_workspace_id"),
        "oc_claim_recoveries",
        ["workspace_id"],
        unique=False,
    )

    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements("oc_claim_recoveries"):
            op.execute(stmt)


def downgrade() -> None:
    op.drop_index(
        op.f("ix_oc_claim_recoveries_workspace_id"), table_name="oc_claim_recoveries"
    )
    op.drop_index(
        op.f("ix_oc_claim_recoveries_opportunity_id"), table_name="oc_claim_recoveries"
    )
    op.drop_table("oc_claim_recoveries")
    op.drop_column("evidence_records", "record_metadata")
    op.drop_column("claims", "claimant_party")
