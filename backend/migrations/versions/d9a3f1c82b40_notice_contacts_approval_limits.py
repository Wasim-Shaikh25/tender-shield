"""notice contacts + approval limits (TS-238, TS-239)

Task: TS-238, TS-239
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9a3f1c82b40"
down_revision: str | None = "c8d4e2f91a30"
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
        "bl_notice_contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("notice_type", sa.String(), nullable=False),
        sa.Column("party", sa.String(), nullable=False),
        sa.Column("role_label", sa.String(), nullable=True),
        sa.Column("authorized_representative", sa.String(), nullable=True),
        sa.Column("postal_address", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("required_content", sa.JSON(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "opportunity_id", "notice_type", name="uq_bl_notice_contacts_type"),
    )
    op.create_index(
        op.f("ix_bl_notice_contacts_notice_type"),
        "bl_notice_contacts",
        ["notice_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bl_notice_contacts_opportunity_id"),
        "bl_notice_contacts",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bl_notice_contacts_workspace_id"),
        "bl_notice_contacts",
        ["workspace_id"],
        unique=False,
    )
    _enable_rls("bl_notice_contacts")

    op.create_table(
        "auth_approval_limits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("min_role", sa.String(), nullable=False),
        sa.Column("max_amount_minor", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "action", name="uq_auth_approval_limits_action"),
    )
    op.create_index(
        op.f("ix_auth_approval_limits_action"),
        "auth_approval_limits",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_approval_limits_workspace_id"),
        "auth_approval_limits",
        ["workspace_id"],
        unique=False,
    )
    _enable_rls("auth_approval_limits")


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_approval_limits_workspace_id"), table_name="auth_approval_limits")
    op.drop_index(op.f("ix_auth_approval_limits_action"), table_name="auth_approval_limits")
    op.drop_table("auth_approval_limits")
    op.drop_index(op.f("ix_bl_notice_contacts_workspace_id"), table_name="bl_notice_contacts")
    op.drop_index(op.f("ix_bl_notice_contacts_opportunity_id"), table_name="bl_notice_contacts")
    op.drop_index(op.f("ix_bl_notice_contacts_notice_type"), table_name="bl_notice_contacts")
    op.drop_table("bl_notice_contacts")
