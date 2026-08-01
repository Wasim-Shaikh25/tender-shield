"""cost codes + mappings tables (TS-240)

Task: TS-240
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4b7c2d91f50"
down_revision: str | None = "d9a3f1c82b40"
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
        "bl_cost_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("variation_category", sa.String(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "opportunity_id", "code", name="uq_bl_cost_codes_code"),
    )
    op.create_index(op.f("ix_bl_cost_codes_opportunity_id"), "bl_cost_codes", ["opportunity_id"])
    op.create_index(op.f("ix_bl_cost_codes_parent_id"), "bl_cost_codes", ["parent_id"])
    op.create_index(op.f("ix_bl_cost_codes_workspace_id"), "bl_cost_codes", ["workspace_id"])
    _enable_rls("bl_cost_codes")

    op.create_table(
        "bl_cost_code_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("cost_code_id", sa.Uuid(), nullable=False),
        sa.Column("boq_src_row", sa.String(), nullable=True),
        sa.Column("finding_id", sa.Uuid(), nullable=True),
        sa.Column("description_match", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["cost_code_id"], ["bl_cost_codes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_bl_cost_code_mappings_cost_code_id"),
        "bl_cost_code_mappings",
        ["cost_code_id"],
    )
    op.create_index(
        op.f("ix_bl_cost_code_mappings_finding_id"),
        "bl_cost_code_mappings",
        ["finding_id"],
    )
    op.create_index(
        op.f("ix_bl_cost_code_mappings_opportunity_id"),
        "bl_cost_code_mappings",
        ["opportunity_id"],
    )
    op.create_index(
        op.f("ix_bl_cost_code_mappings_workspace_id"),
        "bl_cost_code_mappings",
        ["workspace_id"],
    )
    _enable_rls("bl_cost_code_mappings")


def downgrade() -> None:
    op.drop_index(op.f("ix_bl_cost_code_mappings_workspace_id"), table_name="bl_cost_code_mappings")
    op.drop_index(op.f("ix_bl_cost_code_mappings_opportunity_id"), table_name="bl_cost_code_mappings")
    op.drop_index(op.f("ix_bl_cost_code_mappings_finding_id"), table_name="bl_cost_code_mappings")
    op.drop_index(op.f("ix_bl_cost_code_mappings_cost_code_id"), table_name="bl_cost_code_mappings")
    op.drop_table("bl_cost_code_mappings")
    op.drop_index(op.f("ix_bl_cost_codes_workspace_id"), table_name="bl_cost_codes")
    op.drop_index(op.f("ix_bl_cost_codes_parent_id"), table_name="bl_cost_codes")
    op.drop_index(op.f("ix_bl_cost_codes_opportunity_id"), table_name="bl_cost_codes")
    op.drop_table("bl_cost_codes")
