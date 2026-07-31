"""merge pricing-intel and assistant-optional-opportunity heads

Revision ID: f0d5a28efb7f
Revises: 06867937ef52, 0c2f0e860d39
Create Date: 2026-07-31 16:27:05.784418
"""
from __future__ import annotations

from collections.abc import Sequence

revision: str = 'f0d5a28efb7f'
down_revision: str | None = ('06867937ef52', '0c2f0e860d39')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
