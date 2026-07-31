"""outcomes + express tables (TS-215, TS-208)

Task: TS-215, TS-208
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3f1c8d92e10"
down_revision: str | None = "ce0cebf8a285"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WORKSPACE_TABLES = (
    "oc_bid_outcomes",
    "oc_risk_materialization",
    "ex_sessions",
    "ex_purchases",
    "ex_documents",
)


def _enable_rls(table: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY workspace_isolation ON {table} "
        "USING (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid) "
        "WITH CHECK (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "oc_bid_outcomes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("quoted_value_minor", sa.BigInteger(), nullable=True),
        sa.Column("l1_value_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("bidder_count", sa.Integer(), nullable=True),
        sa.Column("decline_reason", sa.String(), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_oc_bid_outcomes_opportunity_id"),
        "oc_bid_outcomes",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oc_bid_outcomes_workspace_id"),
        "oc_bid_outcomes",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "oc_risk_materialization",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=False),
        sa.Column("materialized", sa.Boolean(), nullable=False),
        sa.Column("impact_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("narrative", sa.String(), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_oc_risk_materialization_finding_id"),
        "oc_risk_materialization",
        ["finding_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oc_risk_materialization_opportunity_id"),
        "oc_risk_materialization",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oc_risk_materialization_workspace_id"),
        "oc_risk_materialization",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "ex_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("tier", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("acknowledgment", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ex_sessions_token"), "ex_sessions", ["token"], unique=True)
    op.create_index(
        op.f("ix_ex_sessions_workspace_id"), "ex_sessions", ["workspace_id"], unique=False
    )

    op.create_table(
        "ex_purchases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_order_id", sa.String(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
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
        op.f("ix_ex_purchases_session_id"), "ex_purchases", ["session_id"], unique=False
    )
    op.create_index(
        op.f("ix_ex_purchases_workspace_id"), "ex_purchases", ["workspace_id"], unique=False
    )

    op.create_table(
        "ex_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
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
        op.f("ix_ex_documents_session_id"), "ex_documents", ["session_id"], unique=False
    )
    op.create_index(
        op.f("ix_ex_documents_workspace_id"), "ex_documents", ["workspace_id"], unique=False
    )

    for table in _WORKSPACE_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    op.drop_index(op.f("ix_ex_documents_workspace_id"), table_name="ex_documents")
    op.drop_index(op.f("ix_ex_documents_session_id"), table_name="ex_documents")
    op.drop_table("ex_documents")
    op.drop_index(op.f("ix_ex_purchases_workspace_id"), table_name="ex_purchases")
    op.drop_index(op.f("ix_ex_purchases_session_id"), table_name="ex_purchases")
    op.drop_table("ex_purchases")
    op.drop_index(op.f("ix_ex_sessions_workspace_id"), table_name="ex_sessions")
    op.drop_index(op.f("ix_ex_sessions_token"), table_name="ex_sessions")
    op.drop_table("ex_sessions")
    op.drop_index(
        op.f("ix_oc_risk_materialization_workspace_id"), table_name="oc_risk_materialization"
    )
    op.drop_index(
        op.f("ix_oc_risk_materialization_opportunity_id"), table_name="oc_risk_materialization"
    )
    op.drop_index(
        op.f("ix_oc_risk_materialization_finding_id"), table_name="oc_risk_materialization"
    )
    op.drop_table("oc_risk_materialization")
    op.drop_index(op.f("ix_oc_bid_outcomes_workspace_id"), table_name="oc_bid_outcomes")
    op.drop_index(op.f("ix_oc_bid_outcomes_opportunity_id"), table_name="oc_bid_outcomes")
    op.drop_table("oc_bid_outcomes")
