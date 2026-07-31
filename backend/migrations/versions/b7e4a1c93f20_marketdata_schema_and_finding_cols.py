"""marketdata corpus schema + express session columns + finding provenance cols.

Task: TS-196, TS-209, TS-294, TS-295
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e4a1c93f20"
down_revision: str | None = "a3f1c8d92e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
        "md_employers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family", sa.String(), nullable=False),
        sa.Column("division", sa.String(), nullable=True),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_md_employers_family"), "md_employers", ["family"], unique=False)

    op.create_table(
        "md_tenders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ocid", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("buyer_name", sa.String(), nullable=False),
        sa.Column("employer_id", sa.Uuid(), nullable=True),
        sa.Column("classification", sa.String(), nullable=False),
        sa.Column("value_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("tender_start", sa.String(), nullable=True),
        sa.Column("tender_end", sa.String(), nullable=True),
        sa.Column("adapter_name", sa.String(), nullable=False),
        sa.Column("adapter_version", sa.String(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("raw_metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_md_tenders_employer_id"), "md_tenders", ["employer_id"], unique=False)
    op.create_index(op.f("ix_md_tenders_ocid"), "md_tenders", ["ocid"], unique=True)

    op.create_table(
        "md_awards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("ocid", sa.String(), nullable=False),
        sa.Column("winner", sa.String(), nullable=False),
        sa.Column("value_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("bidder_count", sa.Integer(), nullable=True),
        sa.Column("award_date", sa.String(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_md_awards_ocid"), "md_awards", ["ocid"], unique=False)
    op.create_index(op.f("ix_md_awards_tender_id"), "md_awards", ["tender_id"], unique=False)

    op.create_table(
        "md_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employer_id", sa.Uuid(), nullable=False),
        sa.Column("family", sa.String(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("aggregates", sa.JSON(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_md_profiles_employer_id"), "md_profiles", ["employer_id"], unique=False)
    op.create_index(op.f("ix_md_profiles_family"), "md_profiles", ["family"], unique=False)

    op.create_table(
        "md_harvest_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("adapter_name", sa.String(), nullable=False),
        sa.Column("adapter_version", sa.String(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("ex_sessions", sa.Column("acknowledgment_version", sa.String(), nullable=False, server_default=""))
    op.add_column("ex_sessions", sa.Column("client_ip", sa.String(), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("ex_sessions", "acknowledgment_version", server_default=None)

    op.add_column("findings", sa.Column("currency", sa.String(), nullable=True))
    op.add_column("findings", sa.Column("document_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_findings_document_id"), "findings", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_findings_document_id"), table_name="findings")
    op.drop_column("findings", "document_id")
    op.drop_column("findings", "currency")
    op.drop_column("ex_sessions", "client_ip")
    op.drop_column("ex_sessions", "acknowledgment_version")
    op.drop_table("md_harvest_runs")
    op.drop_index(op.f("ix_md_profiles_family"), table_name="md_profiles")
    op.drop_index(op.f("ix_md_profiles_employer_id"), table_name="md_profiles")
    op.drop_table("md_profiles")
    op.drop_index(op.f("ix_md_awards_tender_id"), table_name="md_awards")
    op.drop_index(op.f("ix_md_awards_ocid"), table_name="md_awards")
    op.drop_table("md_awards")
    op.drop_index(op.f("ix_md_tenders_ocid"), table_name="md_tenders")
    op.drop_index(op.f("ix_md_tenders_employer_id"), table_name="md_tenders")
    op.drop_table("md_tenders")
    op.drop_index(op.f("ix_md_employers_family"), table_name="md_employers")
    op.drop_table("md_employers")
