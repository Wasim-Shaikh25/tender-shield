"""add chat message type and dashboard fields

Revision ID: 5617d7dc8440
Revises: 319b6c25e064
Create Date: 2026-07-30 18:52:35.327523
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '5617d7dc8440'
down_revision: str | None = '319b6c25e064'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('chat_messages', sa.Column('message_type', sa.String(), nullable=False, server_default='text'))
    op.add_column('chat_messages', sa.Column('dashboard', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('chat_messages', 'dashboard')
    op.drop_column('chat_messages', 'message_type')
