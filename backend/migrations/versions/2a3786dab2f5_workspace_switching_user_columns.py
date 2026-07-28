"""workspace switching user columns

Adds User.default_workspace_id/last_workspace_id (R-011, TS-100) — the
deterministic login-workspace resolution order (default -> last used ->
oldest membership) needs somewhere to persist the first two. Neither is a
foreign key: the referenced workspace may be one the user has since lost
membership of (a normal state — resolution falls through to the next
candidate), not a data-integrity error.

Revision ID: 2a3786dab2f5
Revises: 21095f7b4b70
Create Date: 2026-07-28 17:20:34.972453
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '2a3786dab2f5'
down_revision: str | None = '21095f7b4b70'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("default_workspace_id", sa.Uuid(), nullable=True))
    op.add_column("users", sa.Column("last_workspace_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_workspace_id")
    op.drop_column("users", "default_workspace_id")
