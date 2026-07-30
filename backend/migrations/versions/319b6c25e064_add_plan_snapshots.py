"""add plan_snapshots

Revision ID: 319b6c25e064
Revises: c7dac720f0e6
Create Date: 2026-07-30 17:04:39.684504
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "319b6c25e064"
down_revision: str | None = "c7dac720f0e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plan_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("dashboard", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_plan_snapshots_opportunity_id"),
        "plan_snapshots",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_plan_snapshots_user_id"),
        "plan_snapshots",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_plan_snapshots_workspace_id"),
        "plan_snapshots",
        ["workspace_id"],
        unique=False,
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE plan_snapshots ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE plan_snapshots FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY workspace_isolation ON plan_snapshots "
            "USING (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid) "
            "WITH CHECK (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS workspace_isolation ON plan_snapshots")
        op.execute("ALTER TABLE plan_snapshots DISABLE ROW LEVEL SECURITY")

    op.drop_index(op.f("ix_plan_snapshots_workspace_id"), table_name="plan_snapshots")
    op.drop_index(op.f("ix_plan_snapshots_user_id"), table_name="plan_snapshots")
    op.drop_index(op.f("ix_plan_snapshots_opportunity_id"), table_name="plan_snapshots")
    op.drop_table("plan_snapshots")
