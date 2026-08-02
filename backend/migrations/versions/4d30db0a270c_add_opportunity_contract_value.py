"""add_opportunity_contract_value

Revision ID: 4d30db0a270c
Revises: b2cc5dbfbbd6
Create Date: 2026-08-02 04:07:16.950320
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4d30db0a270c"
down_revision: str | None = "b2cc5dbfbbd6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "opportunities",
        sa.Column("contract_value_minor", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "opportunities",
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
    )


def downgrade() -> None:
    op.drop_column("opportunities", "currency")
    op.drop_column("opportunities", "contract_value_minor")
