"""add integration tables manual

Revision ID: dc67e941fd8f
Revises: 438b78d6770c
Create Date: 2026-08-02 04:58:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "dc67e941fd8f"
down_revision: str | Sequence[str] | None = "438b78d6770c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements(table):
            op.execute(stmt)


def upgrade() -> None:
    op.create_table(
        "integration_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=True),
        sa.Column("adapter_kind", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("rate_limit_calls_per_minute", sa.Integer(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="configured"),
        sa.Column("created_by", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integration_sources_adapter_kind"), "integration_sources", ["adapter_kind"], unique=False)
    op.create_index(op.f("ix_integration_sources_opportunity_id"), "integration_sources", ["opportunity_id"], unique=False)
    op.create_index(op.f("ix_integration_sources_workspace_id"), "integration_sources", ["workspace_id"], unique=False)

    op.create_table(
        "integration_sync_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("records_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["integration_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integration_sync_jobs_source_id"), "integration_sync_jobs", ["source_id"], unique=False)
    op.create_index(op.f("ix_integration_sync_jobs_workspace_id"), "integration_sync_jobs", ["workspace_id"], unique=False)

    op.create_table(
        "integration_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_native_id", sa.String(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=True),
        sa.Column("source_path", sa.String(), nullable=True),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["integration_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integration_documents_source_id"), "integration_documents", ["source_id"], unique=False)
    op.create_index(op.f("ix_integration_documents_workspace_id"), "integration_documents", ["workspace_id"], unique=False)

    op.create_table(
        "integration_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_native_id", sa.String(), nullable=False),
        sa.Column("change_event_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["integration_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["change_event_id"], ["change_events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integration_events_source_id"), "integration_events", ["source_id"], unique=False)
    op.create_index(op.f("ix_integration_events_workspace_id"), "integration_events", ["workspace_id"], unique=False)

    op.create_table(
        "integration_schedule_activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("source_native_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("finish_date", sa.Date(), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("predecessors", sa.JSON(), nullable=True),
        sa.Column("linked_change_event_ids", sa.JSON(), nullable=True),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["integration_sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_integration_schedule_activities_opportunity_id"),
        "integration_schedule_activities",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_integration_schedule_activities_source_id"), "integration_schedule_activities", ["source_id"], unique=False
    )
    op.create_index(
        op.f("ix_integration_schedule_activities_workspace_id"),
        "integration_schedule_activities",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "integration_cost_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=True),
        sa.Column("cost_code", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("committed_cost_minor", sa.BigInteger(), nullable=True),
        sa.Column("certified_value_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("source_native_id", sa.String(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["integration_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integration_cost_lines_source_id"), "integration_cost_lines", ["source_id"], unique=False)
    op.create_index(op.f("ix_integration_cost_lines_workspace_id"), "integration_cost_lines", ["workspace_id"], unique=False)

    for table in (
        "integration_sources",
        "integration_sync_jobs",
        "integration_documents",
        "integration_events",
        "integration_schedule_activities",
        "integration_cost_lines",
    ):
        _rls(table)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in (
            "integration_cost_lines",
            "integration_schedule_activities",
            "integration_events",
            "integration_documents",
            "integration_sync_jobs",
            "integration_sources",
        ):
            op.execute(f"DROP POLICY IF EXISTS workspace_isolation ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index(op.f("ix_integration_cost_lines_workspace_id"), table_name="integration_cost_lines")
    op.drop_index(op.f("ix_integration_cost_lines_source_id"), table_name="integration_cost_lines")
    op.drop_table("integration_cost_lines")
    op.drop_index(op.f("ix_integration_schedule_activities_workspace_id"), table_name="integration_schedule_activities")
    op.drop_index(op.f("ix_integration_schedule_activities_source_id"), table_name="integration_schedule_activities")
    op.drop_index(op.f("ix_integration_schedule_activities_opportunity_id"), table_name="integration_schedule_activities")
    op.drop_table("integration_schedule_activities")
    op.drop_index(op.f("ix_integration_events_workspace_id"), table_name="integration_events")
    op.drop_index(op.f("ix_integration_events_source_id"), table_name="integration_events")
    op.drop_table("integration_events")
    op.drop_index(op.f("ix_integration_documents_workspace_id"), table_name="integration_documents")
    op.drop_index(op.f("ix_integration_documents_source_id"), table_name="integration_documents")
    op.drop_table("integration_documents")
    op.drop_index(op.f("ix_integration_sync_jobs_workspace_id"), table_name="integration_sync_jobs")
    op.drop_index(op.f("ix_integration_sync_jobs_source_id"), table_name="integration_sync_jobs")
    op.drop_table("integration_sync_jobs")
    op.drop_index(op.f("ix_integration_sources_workspace_id"), table_name="integration_sources")
    op.drop_index(op.f("ix_integration_sources_opportunity_id"), table_name="integration_sources")
    op.drop_index(op.f("ix_integration_sources_adapter_kind"), table_name="integration_sources")
    op.drop_table("integration_sources")
