"""add claims tables

Revision ID: 00023291b095
Revises: e6f1a8b25c71
Create Date: 2026-08-01 19:34:46.766045
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "00023291b095"
down_revision: str | None = "e6f1a8b25c71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("change_event_id", sa.Uuid(), nullable=True),
        sa.Column("baseline_id", sa.Uuid(), nullable=True),
        sa.Column("claim_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("claim_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("recovered_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by", sa.Uuid(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_claims_baseline_id"), "claims", ["baseline_id"], unique=False)
    op.create_index(op.f("ix_claims_change_event_id"), "claims", ["change_event_id"], unique=False)
    op.create_index(op.f("ix_claims_opportunity_id"), "claims", ["opportunity_id"], unique=False)
    op.create_index(op.f("ix_claims_workspace_id"), "claims", ["workspace_id"], unique=False)

    op.create_table(
        "claim_chronology_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("entry_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("source_kind", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_quote", sa.String(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("custody_chain", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_claim_chronology_entries_claim_id"),
        "claim_chronology_entries",
        ["claim_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_claim_chronology_entries_opportunity_id"),
        "claim_chronology_entries",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_claim_chronology_entries_workspace_id"),
        "claim_chronology_entries",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "claim_delay_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=True),
        sa.Column("change_event_id", sa.Uuid(), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("delay_days", sa.Integer(), nullable=False),
        sa.Column("programme_activity", sa.String(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_quote", sa.String(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_claim_delay_events_change_event_id"),
        "claim_delay_events",
        ["change_event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_claim_delay_events_opportunity_id"),
        "claim_delay_events",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_claim_delay_events_workspace_id"),
        "claim_delay_events",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "claim_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("draft_kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("body", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_claim_drafts_claim_id"), "claim_drafts", ["claim_id"], unique=False
    )
    op.create_index(
        op.f("ix_claim_drafts_workspace_id"), "claim_drafts", ["workspace_id"], unique=False
    )

    op.create_table(
        "claim_evidence_checklist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("item_type", sa.String(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("present", sa.Boolean(), nullable=False),
        sa.Column("evidence_record_ids", sa.JSON(), nullable=False),
        sa.Column("override_note", sa.String(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id", "item_type"),
    )
    op.create_index(
        op.f("ix_claim_evidence_checklist_items_claim_id"),
        "claim_evidence_checklist_items",
        ["claim_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_claim_evidence_checklist_items_workspace_id"),
        "claim_evidence_checklist_items",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "claim_negotiations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("offered_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("counter_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("recorded_by", sa.Uuid(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_claim_negotiations_claim_id"),
        "claim_negotiations",
        ["claim_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_claim_negotiations_workspace_id"),
        "claim_negotiations",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "claim_quantum_line_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("cost_code_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("rate_minor", sa.BigInteger(), nullable=False),
        sa.Column("daywork_days", sa.Integer(), nullable=True),
        sa.Column("daywork_rate_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_claim_quantum_line_items_claim_id"),
        "claim_quantum_line_items",
        ["claim_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_claim_quantum_line_items_workspace_id"),
        "claim_quantum_line_items",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "claim_responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("response_kind", sa.String(), nullable=False),
        sa.Column("received_at", sa.Date(), nullable=False),
        sa.Column("due_at", sa.Date(), nullable=True),
        sa.Column("responder", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_claim_responses_claim_id"), "claim_responses", ["claim_id"], unique=False
    )
    op.create_index(
        op.f("ix_claim_responses_workspace_id"),
        "claim_responses",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "claim_settlements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("settled_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id"),
    )
    op.create_index(
        op.f("ix_claim_settlements_workspace_id"),
        "claim_settlements",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_claim_settlements_workspace_id"), table_name="claim_settlements")
    op.drop_table("claim_settlements")
    op.drop_index(op.f("ix_claim_responses_workspace_id"), table_name="claim_responses")
    op.drop_index(op.f("ix_claim_responses_claim_id"), table_name="claim_responses")
    op.drop_table("claim_responses")
    op.drop_index(
        op.f("ix_claim_quantum_line_items_workspace_id"), table_name="claim_quantum_line_items"
    )
    op.drop_index(
        op.f("ix_claim_quantum_line_items_claim_id"), table_name="claim_quantum_line_items"
    )
    op.drop_table("claim_quantum_line_items")
    op.drop_index(
        op.f("ix_claim_negotiations_workspace_id"), table_name="claim_negotiations"
    )
    op.drop_index(op.f("ix_claim_negotiations_claim_id"), table_name="claim_negotiations")
    op.drop_table("claim_negotiations")
    op.drop_index(
        op.f("ix_claim_evidence_checklist_items_workspace_id"),
        table_name="claim_evidence_checklist_items",
    )
    op.drop_index(
        op.f("ix_claim_evidence_checklist_items_claim_id"),
        table_name="claim_evidence_checklist_items",
    )
    op.drop_table("claim_evidence_checklist_items")
    op.drop_index(op.f("ix_claim_drafts_workspace_id"), table_name="claim_drafts")
    op.drop_index(op.f("ix_claim_drafts_claim_id"), table_name="claim_drafts")
    op.drop_table("claim_drafts")
    op.drop_index(op.f("ix_claim_delay_events_workspace_id"), table_name="claim_delay_events")
    op.drop_index(
        op.f("ix_claim_delay_events_opportunity_id"), table_name="claim_delay_events"
    )
    op.drop_index(
        op.f("ix_claim_delay_events_change_event_id"), table_name="claim_delay_events"
    )
    op.drop_table("claim_delay_events")
    op.drop_index(
        op.f("ix_claim_chronology_entries_workspace_id"), table_name="claim_chronology_entries"
    )
    op.drop_index(
        op.f("ix_claim_chronology_entries_opportunity_id"), table_name="claim_chronology_entries"
    )
    op.drop_index(
        op.f("ix_claim_chronology_entries_claim_id"), table_name="claim_chronology_entries"
    )
    op.drop_table("claim_chronology_entries")
    op.drop_index(op.f("ix_claims_workspace_id"), table_name="claims")
    op.drop_index(op.f("ix_claims_opportunity_id"), table_name="claims")
    op.drop_index(op.f("ix_claims_change_event_id"), table_name="claims")
    op.drop_index(op.f("ix_claims_baseline_id"), table_name="claims")
    op.drop_table("claims")
