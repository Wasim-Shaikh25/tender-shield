"""findings: review_reason + explanation (Phase 1.5 extensions)

Revision ID: 0012_review_explain
Revises: 0011_org_notice_standards
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_review_explain"
down_revision: str | None = "0011_org_notice_standards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("review_reason", sa.String(), nullable=True))
    op.add_column("findings", sa.Column("explanation", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("findings", "explanation")
    op.drop_column("findings", "review_reason")
