"""drop findings opportunity_id foreign key

Revision ID: 3bfb4b682a86
Revises: 3070be424227
Create Date: 2026-07-30 07:48:56.737090
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '3bfb4b682a86'
down_revision: str | None = '3070be424227'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        inspector = sa.inspect(bind)
        for fk in inspector.get_foreign_keys("findings"):
            if fk.get("referred_table") == "opportunities":
                op.drop_constraint(fk["name"], "findings", type_="foreignkey")
                return
    # SQLite does not support dropping constraints in-place; tests use metadata.create_all.


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_foreign_key(
            "fk_findings_opportunities",
            "findings",
            "opportunities",
            ["opportunity_id"],
            ["id"],
            ondelete="CASCADE",
        )
