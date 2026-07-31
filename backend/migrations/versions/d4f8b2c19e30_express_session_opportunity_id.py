"""Add express session opportunity_id for teaser pipeline (TS-210)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f8b2c19e30"
down_revision: str | None = "b7e4a1c93f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ex_sessions",
        sa.Column("opportunity_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f("ix_ex_sessions_opportunity_id"),
        "ex_sessions",
        ["opportunity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ex_sessions_opportunity_id"), table_name="ex_sessions")
    op.drop_column("ex_sessions", "opportunity_id")
