"""watchlist controls table (TS-237)

Task: TS-237
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d4e2f91a30"
down_revision: str | None = "f3b2a8c91d40"
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
        "bl_watchlist_controls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("baseline_id", sa.Uuid(), nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=True),
        sa.Column("obligation_key", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("trigger_text", sa.String(), nullable=True),
        sa.Column("review_cadence", sa.String(), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_quote", sa.String(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["baseline_id"], ["baselines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_bl_watchlist_controls_baseline_id"),
        "bl_watchlist_controls",
        ["baseline_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bl_watchlist_controls_finding_id"),
        "bl_watchlist_controls",
        ["finding_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bl_watchlist_controls_obligation_key"),
        "bl_watchlist_controls",
        ["obligation_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bl_watchlist_controls_opportunity_id"),
        "bl_watchlist_controls",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bl_watchlist_controls_workspace_id"),
        "bl_watchlist_controls",
        ["workspace_id"],
        unique=False,
    )
    _enable_rls("bl_watchlist_controls")


def downgrade() -> None:
    op.drop_index(op.f("ix_bl_watchlist_controls_workspace_id"), table_name="bl_watchlist_controls")
    op.drop_index(op.f("ix_bl_watchlist_controls_opportunity_id"), table_name="bl_watchlist_controls")
    op.drop_index(op.f("ix_bl_watchlist_controls_obligation_key"), table_name="bl_watchlist_controls")
    op.drop_index(op.f("ix_bl_watchlist_controls_finding_id"), table_name="bl_watchlist_controls")
    op.drop_index(op.f("ix_bl_watchlist_controls_baseline_id"), table_name="bl_watchlist_controls")
    op.drop_table("bl_watchlist_controls")
