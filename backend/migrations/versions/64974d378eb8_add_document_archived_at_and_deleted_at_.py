"""add document archived_at and deleted_at columns

Revision ID: 64974d378eb8
Revises: 0b741405a5e6
Create Date: 2026-08-02 14:52:32.972213
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '64974d378eb8'
down_revision: str | None = '0b741405a5e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('documents', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'deleted_at')
    op.drop_column('documents', 'archived_at')
