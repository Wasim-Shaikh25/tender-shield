"""change inbox addresses + inbound emails (TS-247)

Task: TS-247
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6f1a8b25c71"
down_revision: str | None = "d5e0f7a14b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("change_inbox_addresses", "change_inbound_emails")


def _enable_rls(table: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY workspace_isolation ON {table} "
        "USING (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid) "
        "WITH CHECK (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "change_inbox_addresses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("address_token", sa.String(), nullable=False),
        sa.Column("forward_address", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("address_token"),
    )
    op.create_index(
        op.f("ix_change_inbox_addresses_opportunity_id"),
        "change_inbox_addresses",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_change_inbox_addresses_workspace_id"),
        "change_inbox_addresses",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "change_inbound_emails",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("inbox_address_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("from_address", sa.String(), nullable=True),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("body_plain", sa.String(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "message_id"),
    )
    op.create_index(
        op.f("ix_change_inbound_emails_inbox_address_id"),
        "change_inbound_emails",
        ["inbox_address_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_change_inbound_emails_opportunity_id"),
        "change_inbound_emails",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_change_inbound_emails_workspace_id"),
        "change_inbound_emails",
        ["workspace_id"],
        unique=False,
    )

    for table in _TABLES:
        _enable_rls(table)


def downgrade() -> None:
    op.drop_index(op.f("ix_change_inbound_emails_workspace_id"), table_name="change_inbound_emails")
    op.drop_index(
        op.f("ix_change_inbound_emails_opportunity_id"), table_name="change_inbound_emails"
    )
    op.drop_index(
        op.f("ix_change_inbound_emails_inbox_address_id"), table_name="change_inbound_emails"
    )
    op.drop_table("change_inbound_emails")
    op.drop_index(
        op.f("ix_change_inbox_addresses_workspace_id"), table_name="change_inbox_addresses"
    )
    op.drop_index(
        op.f("ix_change_inbox_addresses_opportunity_id"), table_name="change_inbox_addresses"
    )
    op.drop_table("change_inbox_addresses")
