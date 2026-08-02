"""add finding facts column

Revision ID: 1dc30cc78449
Revises: 6cce3c3fb917
Create Date: 2026-08-02 05:23:32.735368
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1dc30cc78449"
down_revision: str | Sequence[str] | None = "6cce3c3fb917"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("facts", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("findings", "facts")
