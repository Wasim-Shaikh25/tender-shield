"""convert findings amount_exposure to minor units

Revision ID: f5c03761fb0c
Revises: 3bfb4b682a86
Create Date: 2026-07-30 08:15:56.318289
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f5c03761fb0c"
down_revision: str | None = "3bfb4b682a86"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_major_to_minor = "UPDATE findings SET amount_exposure = COALESCE(amount_exposure, 0) * 100 WHERE amount_exposure IS NOT NULL"
_minor_to_major = "UPDATE findings SET amount_exposure = COALESCE(amount_exposure, 0) / 100.0 WHERE amount_exposure IS NOT NULL"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(_major_to_minor)
        op.alter_column(
            "findings",
            "amount_exposure",
            existing_type=sa.NUMERIC(precision=16, scale=2),
            type_=sa.BigInteger(),
            existing_nullable=True,
            postgresql_using="COALESCE(amount_exposure, 0) * 100",
        )
    else:
        # SQLite does not support ALTER COLUMN TYPE. Alembic's batch alter rebuilds
        # the table; we update values first so existing major-unit amounts become paise.
        op.execute(_major_to_minor)
        with op.batch_alter_table("findings") as batch_op:
            batch_op.alter_column(
                "amount_exposure",
                existing_type=sa.NUMERIC(precision=16, scale=2),
                type_=sa.BigInteger(),
                existing_nullable=True,
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(_minor_to_major)
        op.alter_column(
            "findings",
            "amount_exposure",
            existing_type=sa.BigInteger(),
            type_=sa.NUMERIC(precision=16, scale=2),
            existing_nullable=True,
            postgresql_using="COALESCE(amount_exposure, 0) / 100.0",
        )
    else:
        op.execute(_minor_to_major)
        with op.batch_alter_table("findings") as batch_op:
            batch_op.alter_column(
                "amount_exposure",
                existing_type=sa.BigInteger(),
                type_=sa.NUMERIC(precision=16, scale=2),
                existing_nullable=True,
            )
