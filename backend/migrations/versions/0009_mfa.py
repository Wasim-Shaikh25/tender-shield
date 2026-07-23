"""users.mfa_totp_secret (TOTP MFA)

Revision ID: 0009_mfa
Revises: 0008_billing
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_mfa"
down_revision: str | None = "0008_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mfa_totp_secret", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "mfa_totp_secret")
