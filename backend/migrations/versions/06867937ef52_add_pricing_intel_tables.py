"""add pricing intel tables

Revision ID: 06867937ef52
Revises: 5617d7dc8440
Create Date: 2026-07-31 06:16:04.800656

Hand-trimmed from the autogenerate output: the raw diff also picked up
unrelated SQLite index-naming drift on invoices/payment_log/plan_history/
usage_events/webhook_events/findings from prior migrations. That drift is
pre-existing and out of scope for this change — each module owns its own
migrations (CLAUDE.md §2) — so only the three new pi_* tables are kept here.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "06867937ef52"
down_revision: str | None = "5617d7dc8440"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pi_loadings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=False),
        sa.Column("pattern_id", sa.String(), nullable=False),
        sa.Column("produced", sa.Boolean(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("basis", sa.String(), nullable=True),
        sa.Column("formula", sa.String(), nullable=True),
        sa.Column("rulepack_version", sa.String(), nullable=False),
        sa.Column("inputs_used", sa.JSON(), nullable=False),
        sa.Column("missing_inputs", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pi_loadings_finding_id"), "pi_loadings", ["finding_id"], unique=False
    )
    op.create_index(
        op.f("ix_pi_loadings_opportunity_id"), "pi_loadings", ["opportunity_id"], unique=False
    )
    op.create_index(
        op.f("ix_pi_loadings_workspace_id"), "pi_loadings", ["workspace_id"], unique=False
    )

    op.create_table(
        "pi_rate_matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("src_row", sa.Integer(), nullable=False),
        sa.Column("boq_description", sa.String(), nullable=False),
        sa.Column("boq_unit", sa.String(), nullable=False),
        sa.Column("boq_rate_minor", sa.BigInteger(), nullable=False),
        sa.Column("matched_by", sa.String(), nullable=False),
        sa.Column("schedule_id", sa.String(), nullable=True),
        sa.Column("schedule_code", sa.String(), nullable=True),
        sa.Column("schedule_description", sa.String(), nullable=True),
        sa.Column("schedule_rate_minor", sa.BigInteger(), nullable=True),
        sa.Column("variance_minor", sa.BigInteger(), nullable=True),
        sa.Column("variance_pct", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pi_rate_matches_opportunity_id"),
        "pi_rate_matches",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pi_rate_matches_workspace_id"),
        "pi_rate_matches",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "pi_cashflow_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("monthly", sa.JSON(), nullable=False),
        sa.Column("peak_requirement_minor", sa.BigInteger(), nullable=False),
        sa.Column("peak_month", sa.Integer(), nullable=False),
        sa.Column("total_financing_cost_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pi_cashflow_runs_opportunity_id"),
        "pi_cashflow_runs",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pi_cashflow_runs_workspace_id"),
        "pi_cashflow_runs",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_pi_cashflow_runs_workspace_id"), table_name="pi_cashflow_runs")
    op.drop_index(op.f("ix_pi_cashflow_runs_opportunity_id"), table_name="pi_cashflow_runs")
    op.drop_table("pi_cashflow_runs")

    op.drop_index(op.f("ix_pi_rate_matches_workspace_id"), table_name="pi_rate_matches")
    op.drop_index(op.f("ix_pi_rate_matches_opportunity_id"), table_name="pi_rate_matches")
    op.drop_table("pi_rate_matches")

    op.drop_index(op.f("ix_pi_loadings_workspace_id"), table_name="pi_loadings")
    op.drop_index(op.f("ix_pi_loadings_opportunity_id"), table_name="pi_loadings")
    op.drop_index(op.f("ix_pi_loadings_finding_id"), table_name="pi_loadings")
    op.drop_table("pi_loadings")
