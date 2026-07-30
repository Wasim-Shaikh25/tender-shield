"""add disclaimer to findings

Revision ID: 857d8c12c3f6
Revises: fae3c9aa47f8
Create Date: 2026-07-30 06:13:02.282201
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '857d8c12c3f6'
down_revision: str | None = 'fae3c9aa47f8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('findings', sa.Column('disclaimer', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('findings', 'disclaimer')
