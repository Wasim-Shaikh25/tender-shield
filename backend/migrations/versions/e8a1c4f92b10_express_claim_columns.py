"""express session claim columns

Revision ID: e8a1c4f92b10
Revises: d4f8b2c19e30
Create Date: 2026-07-31

Task: TS-214
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8a1c4f92b10"
down_revision: str | Sequence[str] | None = "d4f8b2c19e30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ex_sessions",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ex_sessions",
        sa.Column("claimed_by_user_id", sa.Uuid(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ex_sessions", "claimed_by_user_id")
    op.drop_column("ex_sessions", "claimed_at")
