"""user lockout columns

Per-account lockout (R-002 §C.3, TS-094): capped, time-boxed backoff on
repeated failed logins.

Revision ID: 2cf9d68a748b
Revises: ae76edba3a7a
Create Date: 2026-07-28 06:59:45.071820
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '2cf9d68a748b'
down_revision: str | None = 'ae76edba3a7a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'users', sa.Column('failed_logins', sa.Integer(), nullable=False, server_default='0')
    )
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_logins')
