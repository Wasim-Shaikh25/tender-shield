"""make users.phone nullable and add auth config toggles

Revision ID: 2dcc5f291455
Revises: 1dc30cc78449
Create Date: 2026-08-02 06:12:15.555120
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '2dcc5f291455'
down_revision: str | None = '1dc30cc78449'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Auth configuration toggles are environment settings, not DB columns.
    # The only schema change is making `users.phone` optional so sign-up can be
    # email-only when mobile verification is disabled.
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table('users', recreate='always') as batch_op:
            batch_op.alter_column('phone', existing_type=sa.VARCHAR(), nullable=True)
    else:
        op.alter_column('users', 'phone', existing_type=sa.VARCHAR(), nullable=True)


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table('users', recreate='always') as batch_op:
            batch_op.alter_column('phone', existing_type=sa.VARCHAR(), nullable=False)
    else:
        op.alter_column('users', 'phone', existing_type=sa.VARCHAR(), nullable=False)
