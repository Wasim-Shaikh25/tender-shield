"""add baselines version unique constraint

Revision ID: 6dd2ea16bfc9
Revises: d56668489ef4
Create Date: 2026-08-02 08:23:12.587302
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "6dd2ea16bfc9"
down_revision: str | Sequence[str] | None = "d56668489ef4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    # Prevent concurrent freezes from assigning the same version to an opportunity.
    op.create_unique_constraint(
        "uq_baselines_opportunity_version",
        "baselines",
        ["opportunity_id", "version"],
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.drop_constraint("uq_baselines_opportunity_version", "baselines", type_="unique")
