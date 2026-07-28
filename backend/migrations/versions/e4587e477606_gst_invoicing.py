"""gst invoicing

Wires the GST tax computation in billing/gst.py into real invoices (R-007,
TS-096): tax columns, gap-free per-FY numbering (invoice_sequences), buyer
GST identity on workspaces. `amount_minor` (untaxed placeholder) is replaced
by `base_minor`/`cgst_minor`/`sgst_minor`/`igst_minor`/`round_off_minor`/
`total_minor` so `base + taxes + round_off == total` always holds exactly.

Revision ID: e4587e477606
Revises: e18ffec0675e
Create Date: 2026-07-28 12:30:24.674760
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e4587e477606'
down_revision: str | None = 'e18ffec0675e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BigId = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "invoice_sequences",
        sa.Column("fy", sa.String(), nullable=False),
        sa.Column("last_seq", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("fy"),
    )

    op.add_column("invoices", sa.Column("fy", sa.String(), nullable=True))
    op.add_column("invoices", sa.Column("seq", sa.Integer(), nullable=True))
    op.add_column(
        "invoices",
        sa.Column("doc_type", sa.String(), nullable=False, server_default="invoice"),
    )
    op.add_column("invoices", sa.Column("original_invoice_id", _BigId, nullable=True))
    op.add_column("invoices", sa.Column("base_minor", sa.BigInteger(), nullable=True))
    op.add_column(
        "invoices", sa.Column("cgst_minor", sa.BigInteger(), nullable=False, server_default="0")
    )
    op.add_column(
        "invoices", sa.Column("sgst_minor", sa.BigInteger(), nullable=False, server_default="0")
    )
    op.add_column(
        "invoices", sa.Column("igst_minor", sa.BigInteger(), nullable=False, server_default="0")
    )
    op.add_column(
        "invoices", sa.Column("round_off_minor", sa.BigInteger(), nullable=False, server_default="0")
    )
    op.add_column("invoices", sa.Column("total_minor", sa.BigInteger(), nullable=True))
    op.add_column(
        "invoices",
        sa.Column("sac_code", sa.String(), nullable=False, server_default="998313"),
    )
    op.add_column("invoices", sa.Column("seller_gstin", sa.String(), nullable=True))
    op.add_column("invoices", sa.Column("buyer_gstin", sa.String(), nullable=True))
    op.add_column("invoices", sa.Column("buyer_legal_name", sa.String(), nullable=True))
    op.add_column("invoices", sa.Column("place_of_supply", sa.String(), nullable=True))
    op.add_column("invoices", sa.Column("payment_intent_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_invoices_payment_intent_id"), "invoices", ["payment_intent_id"]
    )

    # Backfill any pre-existing rows (dev/test data only — this table predates
    # a live launch) so the NOT NULL constraints below don't fail: the old
    # untaxed `amount_minor` becomes both the taxable base and the total,
    # with zero tax lines, in a synthetic FY series that can't collide with
    # real post-migration invoice numbers.
    op.execute(
        "UPDATE invoices SET base_minor = amount_minor, total_minor = amount_minor, "
        "fy = 'pre-gst', seq = id WHERE total_minor IS NULL"
    )

    with op.batch_alter_table("invoices") as batch:
        batch.alter_column("fy", nullable=False)
        batch.alter_column("seq", nullable=False)
        batch.alter_column("base_minor", nullable=False)
        batch.alter_column("total_minor", nullable=False)
        batch.drop_column("amount_minor")

    op.add_column("workspaces", sa.Column("legal_name", sa.String(), nullable=True))
    op.add_column("workspaces", sa.Column("gstin", sa.String(), nullable=True))
    op.add_column(
        "workspaces",
        sa.Column("billing_address", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column("workspaces", sa.Column("place_of_supply", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("workspaces", "place_of_supply")
    op.drop_column("workspaces", "billing_address")
    op.drop_column("workspaces", "gstin")
    op.drop_column("workspaces", "legal_name")

    op.add_column("invoices", sa.Column("amount_minor", sa.BigInteger(), nullable=True))
    op.execute("UPDATE invoices SET amount_minor = total_minor")
    with op.batch_alter_table("invoices") as batch:
        batch.alter_column("amount_minor", nullable=False)

    op.drop_index(op.f("ix_invoices_payment_intent_id"), table_name="invoices")
    op.drop_column("invoices", "payment_intent_id")
    op.drop_column("invoices", "place_of_supply")
    op.drop_column("invoices", "buyer_legal_name")
    op.drop_column("invoices", "buyer_gstin")
    op.drop_column("invoices", "seller_gstin")
    op.drop_column("invoices", "sac_code")
    op.drop_column("invoices", "total_minor")
    op.drop_column("invoices", "round_off_minor")
    op.drop_column("invoices", "igst_minor")
    op.drop_column("invoices", "sgst_minor")
    op.drop_column("invoices", "cgst_minor")
    op.drop_column("invoices", "base_minor")
    op.drop_column("invoices", "original_invoice_id")
    op.drop_column("invoices", "doc_type")
    op.drop_column("invoices", "seq")
    op.drop_column("invoices", "fy")

    op.drop_table("invoice_sequences")
