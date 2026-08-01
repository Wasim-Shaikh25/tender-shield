"""evidence_records + project_subscriptions tables (TS-254, TS-256)

Task: TS-254, TS-256
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e0f7a14b60"
down_revision: str | None = "a2b9c4d81e30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
        "evidence_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("change_event_id", sa.Uuid(), nullable=False),
        sa.Column("record_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("custody_chain", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evidence_records_change_event_id"),
        "evidence_records",
        ["change_event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evidence_records_opportunity_id"),
        "evidence_records",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evidence_records_workspace_id"),
        "evidence_records",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "project_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("activation_fee_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("provider_order_id", sa.String(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "opportunity_id"),
    )
    op.create_index(
        op.f("ix_project_subscriptions_opportunity_id"),
        "project_subscriptions",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_subscriptions_workspace_id"),
        "project_subscriptions",
        ["workspace_id"],
        unique=False,
    )

    for table in ("evidence_records", "project_subscriptions"):
        _enable_rls(table)


def downgrade() -> None:
    op.drop_index(op.f("ix_project_subscriptions_workspace_id"), table_name="project_subscriptions")
    op.drop_index(
        op.f("ix_project_subscriptions_opportunity_id"), table_name="project_subscriptions"
    )
    op.drop_table("project_subscriptions")
    op.drop_index(op.f("ix_evidence_records_workspace_id"), table_name="evidence_records")
    op.drop_index(op.f("ix_evidence_records_opportunity_id"), table_name="evidence_records")
    op.drop_index(op.f("ix_evidence_records_change_event_id"), table_name="evidence_records")
    op.drop_table("evidence_records")
