"""add rulepack admin tables

Revision ID: 945105123194
Revises: 64974d378eb8
Create Date: 2026-08-03 10:15:14.386877
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '945105123194'
down_revision: str | None = '64974d378eb8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _workspace_guc() -> str:
    return "nullif(current_setting('app.workspace_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "rulepacks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pack_id", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("jurisdiction", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rulepacks_pack_id", "rulepacks", ["pack_id"])
    op.create_index("ix_rulepacks_scope", "rulepacks", ["scope"])
    op.create_index("ix_rulepacks_workspace_id", "rulepacks", ["workspace_id"])

    op.create_table(
        "rulepack_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rulepack_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["rulepack_id"], ["rulepacks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rulepack_files_rulepack_id", "rulepack_files", ["rulepack_id"])
    op.create_index("ix_rulepack_files_workspace_id", "rulepack_files", ["workspace_id"])

    op.create_table(
        "opportunity_rulepacks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("rulepack_id", sa.Uuid(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("applied_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rulepack_id"], ["rulepacks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_opportunity_rulepacks_workspace_id", "opportunity_rulepacks", ["workspace_id"])
    op.create_index("ix_opportunity_rulepacks_opportunity_id", "opportunity_rulepacks", ["opportunity_id"])
    op.create_index("ix_opportunity_rulepacks_rulepack_id", "opportunity_rulepacks", ["rulepack_id"])

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        ws_guc = _workspace_guc()
        # rulepacks: global packs (workspace_id IS NULL) are visible to all workspaces;
        # workspace-scoped packs are isolated to their workspace.
        for table in ("rulepacks", "rulepack_files"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY workspace_or_global_isolation ON {table} "
                f"USING (workspace_id IS NULL OR workspace_id = {ws_guc}) "
                f"WITH CHECK (workspace_id IS NULL OR workspace_id = {ws_guc})"
            )
        # opportunity_rulepacks uses standard workspace isolation.
        op.execute("ALTER TABLE opportunity_rulepacks ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE opportunity_rulepacks FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY workspace_isolation ON opportunity_rulepacks "
            f"USING (workspace_id = {ws_guc}) "
            f"WITH CHECK (workspace_id = {ws_guc})"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ("opportunity_rulepacks", "rulepack_files", "rulepacks"):
            op.execute(f"DROP POLICY IF EXISTS workspace_or_global_isolation ON {table}")
            op.execute(f"DROP POLICY IF EXISTS workspace_isolation ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_table("opportunity_rulepacks")
    op.drop_table("rulepack_files")
    op.drop_table("rulepacks")
