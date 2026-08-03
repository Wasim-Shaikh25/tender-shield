"""add chat_message suggested_followups

Revision ID: eb74933d1c9d
Revises: a50a314e2702
Create Date: 2026-08-03 13:16:17.685309
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'eb74933d1c9d'
down_revision: str | None = 'a50a314e2702'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column(
            "suggested_followups",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "suggested_followups")
