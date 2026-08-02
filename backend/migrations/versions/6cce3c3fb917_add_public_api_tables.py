"""add public_api tables

Revision ID: 6cce3c3fb917
Revises: 6984d8c7fad3
Create Date: 2026-08-02 05:12:05.725976
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "6cce3c3fb917"
down_revision: str | Sequence[str] | None = "6984d8c7fad3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements(table):
            op.execute(stmt)


def upgrade() -> None:
    op.create_table(
        "public_api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_public_api_keys_key_hash"), "public_api_keys", ["key_hash"], unique=False
    )
    op.create_index(
        op.f("ix_public_api_keys_workspace_id"),
        "public_api_keys",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "public_signature_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("notice_id", sa.Uuid(), nullable=True),
        sa.Column("change_event_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_email", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="docusign_stub"),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="requested"),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_public_signature_requests_change_event_id"),
        "public_signature_requests",
        ["change_event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_public_signature_requests_notice_id"),
        "public_signature_requests",
        ["notice_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_public_signature_requests_opportunity_id"),
        "public_signature_requests",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_public_signature_requests_workspace_id"),
        "public_signature_requests",
        ["workspace_id"],
        unique=False,
    )

    for table in ("public_api_keys", "public_signature_requests"):
        _rls(table)


def downgrade() -> None:
    for table in ("public_signature_requests", "public_api_keys"):
        if op.get_bind().dialect.name == "postgresql":
            op.execute(f"DROP POLICY IF EXISTS workspace_isolation ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index(
        op.f("ix_public_signature_requests_workspace_id"),
        table_name="public_signature_requests",
    )
    op.drop_index(
        op.f("ix_public_signature_requests_opportunity_id"),
        table_name="public_signature_requests",
    )
    op.drop_index(
        op.f("ix_public_signature_requests_notice_id"),
        table_name="public_signature_requests",
    )
    op.drop_index(
        op.f("ix_public_signature_requests_change_event_id"),
        table_name="public_signature_requests",
    )
    op.drop_table("public_signature_requests")
    op.drop_index(
        op.f("ix_public_api_keys_workspace_id"), table_name="public_api_keys"
    )
    op.drop_index(
        op.f("ix_public_api_keys_key_hash"), table_name="public_api_keys"
    )
    op.drop_table("public_api_keys")
