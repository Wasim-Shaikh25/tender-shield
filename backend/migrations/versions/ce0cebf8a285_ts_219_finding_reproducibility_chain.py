"""ts_219_finding_reproducibility_chain

Revision ID: ce0cebf8a285
Revises: f0d5a28efb7f
Create Date: 2026-07-31 17:10:31.707223
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'ce0cebf8a285'
down_revision: str | None = 'f0d5a28efb7f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("rulepack_version", sa.String(), nullable=True))
    op.add_column("findings", sa.Column("model_id", sa.String(), nullable=True))
    op.add_column("findings", sa.Column("prompt_hash", sa.String(), nullable=True))
    op.add_column("findings", sa.Column("document_hash", sa.String(), nullable=True))
    op.add_column("findings", sa.Column("engine_version", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("findings", "engine_version")
    op.drop_column("findings", "document_hash")
    op.drop_column("findings", "prompt_hash")
    op.drop_column("findings", "model_id")
    op.drop_column("findings", "rulepack_version")
