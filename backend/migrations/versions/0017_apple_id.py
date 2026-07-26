"""Add users.apple_id for Sign in with Apple (TS-071).

Revision ID: 0017_apple_id
Revises: 0016_assistant_chat
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_apple_id"
down_revision: str | None = "0016_assistant_chat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("apple_id", sa.String(), nullable=True))
        batch_op.create_unique_constraint("uq_users_apple_id", ["apple_id"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_apple_id", type_="unique")
        batch_op.drop_column("apple_id")
