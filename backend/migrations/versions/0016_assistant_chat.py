"""chat_sessions and chat_messages tables (org-scoped, RLS on PostgreSQL) —
assistant conversation/session persistence (TS-069).

Revision ID: 0016_assistant_chat
Revises: 0015_invoices
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.db import rls_statements

revision: str = "0016_assistant_chat"
down_revision: str | None = "0015_invoices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_chat_sessions_org_id", "chat_sessions", ["org_id"])
    op.create_index("ix_chat_sessions_opportunity_id", "chat_sessions", ["opportunity_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("grounded", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chat_messages_org_id", "chat_messages", ["org_id"])
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])

    if op.get_bind().dialect.name == "postgresql":
        for stmt in rls_statements("chat_sessions"):
            op.execute(stmt)
        for stmt in rls_statements("chat_messages"):
            op.execute(stmt)


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
