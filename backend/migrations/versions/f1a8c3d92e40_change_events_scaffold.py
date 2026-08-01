"""change events, sources, confirmations tables (TS-244)

Task: TS-244
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a8c3d92e40"
down_revision: str | None = "e4b7c2d91f50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("change_events", "change_sources", "change_confirmations")


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
        "change_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("baseline_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("affected_scope", sa.String(), nullable=True),
        sa.Column("confidence_band", sa.String(), nullable=False),
        sa.Column("notice_type", sa.String(), nullable=True),
        sa.Column("trigger_date", sa.Date(), nullable=True),
        sa.Column("notice_deadline", sa.Date(), nullable=True),
        sa.Column("notice_deadline_detail", sa.JSON(), nullable=False),
        sa.Column("impact_links", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_change_events_baseline_id"), "change_events", ["baseline_id"], unique=False
    )
    op.create_index(
        op.f("ix_change_events_opportunity_id"),
        "change_events",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_change_events_workspace_id"), "change_events", ["workspace_id"], unique=False
    )

    op.create_table(
        "change_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("change_event_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_quote", sa.String(), nullable=True),
        sa.Column("external_ref", sa.String(), nullable=True),
        sa.Column("text_preview", sa.String(), nullable=True),
        sa.Column("sha256", sa.String(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["change_event_id"], ["change_events.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_change_sources_change_event_id"),
        "change_sources",
        ["change_event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_change_sources_opportunity_id"),
        "change_sources",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_change_sources_workspace_id"), "change_sources", ["workspace_id"], unique=False
    )

    op.create_table(
        "change_confirmations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("change_event_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("confirmed_by", sa.Uuid(), nullable=False),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["change_event_id"], ["change_events.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_change_confirmations_change_event_id"),
        "change_confirmations",
        ["change_event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_change_confirmations_opportunity_id"),
        "change_confirmations",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_change_confirmations_workspace_id"),
        "change_confirmations",
        ["workspace_id"],
        unique=False,
    )

    for table in _TABLES:
        _enable_rls(table)


def downgrade() -> None:
    op.drop_index(
        op.f("ix_change_confirmations_workspace_id"), table_name="change_confirmations"
    )
    op.drop_index(
        op.f("ix_change_confirmations_opportunity_id"), table_name="change_confirmations"
    )
    op.drop_index(
        op.f("ix_change_confirmations_change_event_id"), table_name="change_confirmations"
    )
    op.drop_table("change_confirmations")
    op.drop_index(op.f("ix_change_sources_workspace_id"), table_name="change_sources")
    op.drop_index(op.f("ix_change_sources_opportunity_id"), table_name="change_sources")
    op.drop_index(op.f("ix_change_sources_change_event_id"), table_name="change_sources")
    op.drop_table("change_sources")
    op.drop_index(op.f("ix_change_events_workspace_id"), table_name="change_events")
    op.drop_index(op.f("ix_change_events_opportunity_id"), table_name="change_events")
    op.drop_index(op.f("ix_change_events_baseline_id"), table_name="change_events")
    op.drop_table("change_events")
