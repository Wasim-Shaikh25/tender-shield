"""change_notice_alert_log table (TS-252)

Task: TS-252
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a2b9c4d81e30"
down_revision: str | None = "f1a8c3d92e40"
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
        "change_notice_alert_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("change_event_id", sa.Uuid(), nullable=False),
        sa.Column("alert_day", sa.Integer(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "change_event_id", "alert_day"),
    )
    op.create_index(
        op.f("ix_change_notice_alert_log_change_event_id"),
        "change_notice_alert_log",
        ["change_event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_change_notice_alert_log_opportunity_id"),
        "change_notice_alert_log",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_change_notice_alert_log_user_id"),
        "change_notice_alert_log",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_change_notice_alert_log_workspace_id"),
        "change_notice_alert_log",
        ["workspace_id"],
        unique=False,
    )
    _enable_rls("change_notice_alert_log")


def downgrade() -> None:
    op.drop_index(
        op.f("ix_change_notice_alert_log_workspace_id"), table_name="change_notice_alert_log"
    )
    op.drop_index(
        op.f("ix_change_notice_alert_log_user_id"), table_name="change_notice_alert_log"
    )
    op.drop_index(
        op.f("ix_change_notice_alert_log_opportunity_id"), table_name="change_notice_alert_log"
    )
    op.drop_index(
        op.f("ix_change_notice_alert_log_change_event_id"), table_name="change_notice_alert_log"
    )
    op.drop_table("change_notice_alert_log")
