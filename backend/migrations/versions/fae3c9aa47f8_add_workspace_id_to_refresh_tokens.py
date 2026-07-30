"""add workspace_id to refresh_tokens

Revision ID: fae3c9aa47f8
Revises: 6cffa6139050
Create Date: 2026-07-30 05:58:34.160618
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'fae3c9aa47f8'
down_revision: str | None = '6cffa6139050'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('refresh_tokens', sa.Column('workspace_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_refresh_tokens_workspace_id'), 'refresh_tokens', ['workspace_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_refresh_tokens_workspace_id'), table_name='refresh_tokens')
    op.drop_column('refresh_tokens', 'workspace_id')
