"""make chat session opportunity optional

Revision ID: 0c2f0e860d39
Revises: 5617d7dc8440
Create Date: 2026-07-30 19:15:19.923441
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0c2f0e860d39'
down_revision: str | None = '5617d7dc8440'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('chat_sessions') as batch_op:
        batch_op.alter_column('opportunity_id',
                              existing_type=sa.CHAR(length=32),
                              nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('chat_sessions') as batch_op:
        batch_op.alter_column('opportunity_id',
                              existing_type=sa.CHAR(length=32),
                              nullable=False)
