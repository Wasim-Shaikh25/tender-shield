"""rp_correction_proposals table (TS-218).

Revision ID: f3b2a8c91d40
Revises: e8a1c4f92b10
Create Date: 2026-07-31

Task: TS-218
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3b2a8c91d40"
down_revision: str | Sequence[str] | None = "e8a1c4f92b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rp_correction_proposals",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pack_id", sa.String(), nullable=False),
        sa.Column("pattern_id", sa.String(), nullable=False),
        sa.Column("employer_family", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("overlay", sa.JSON(), nullable=False),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_rp_correction_proposals_workspace_id"),
        "rp_correction_proposals",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rp_correction_proposals_pattern_id"),
        "rp_correction_proposals",
        ["pattern_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rp_correction_proposals_employer_family"),
        "rp_correction_proposals",
        ["employer_family"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_rp_correction_proposals_employer_family"), table_name="rp_correction_proposals"
    )
    op.drop_index(
        op.f("ix_rp_correction_proposals_pattern_id"), table_name="rp_correction_proposals"
    )
    op.drop_index(
        op.f("ix_rp_correction_proposals_workspace_id"), table_name="rp_correction_proposals"
    )
    op.drop_table("rp_correction_proposals")
