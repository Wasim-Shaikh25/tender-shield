"""document size and content type

Recorded on upload now that the endpoint streams to a size-capped temp file
instead of buffering the whole body (R-003 §B.1, TS-095).

Revision ID: c9ed90a8524f
Revises: 2cf9d68a748b
Create Date: 2026-07-28 07:10:20.754104
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c9ed90a8524f'
down_revision: str | None = '2cf9d68a748b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'documents', sa.Column('size_bytes', sa.Integer(), nullable=False, server_default='0')
    )
    op.add_column('documents', sa.Column('content_type', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'content_type')
    op.drop_column('documents', 'size_bytes')
