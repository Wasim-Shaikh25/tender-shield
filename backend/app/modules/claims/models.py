"""Claims-owned tables (TS-258)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class Claim(Base, WorkspaceScopedMixin):
    _tablename_ = "claims"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    change_event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    baseline_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    claim_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    claim_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    recovered_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ClaimChronologyEntry(Base, WorkspaceScopedMixin):
    _tablename_ = "claim_chronology_entries"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_type: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    source_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_quote: Mapped[str | None] = mapped_column(String, nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    custody_chain: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ClaimEvidenceChecklistItem(Base, WorkspaceScopedMixin):
    _tablename_ = "claim_evidence_checklist_items"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[str] = mapped_column(String, nullable=False)
    required: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    present: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    evidence_record_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    override_note: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (UniqueConstraint("claim_id", "item_type"),)


class ClaimQuantumLineItem(Base, WorkspaceScopedMixin):
    _tablename_ = "claim_quantum_line_items"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    rate_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    daywork_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daywork_rate_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ClaimDelayEvent(Base, WorkspaceScopedMixin):
    _tablename_ = "claim_delay_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    claim_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("claims.id", ondelete="SET NULL"), nullable=True
    )
    change_event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False)
    programme_activity: Mapped[str | None] = mapped_column(String, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_quote: Mapped[str | None] = mapped_column(String, nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ClaimResponse(Base, WorkspaceScopedMixin):
    _tablename_ = "claim_responses"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    response_kind: Mapped[str] = mapped_column(String, nullable=False)
    received_at: Mapped[date] = mapped_column(Date, nullable=False)
    due_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    responder: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ClaimNegotiation(Base, WorkspaceScopedMixin):
    _tablename_ = "claim_negotiations"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    offered_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    counter_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    recorded_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ClaimSettlement(Base, WorkspaceScopedMixin):
    _tablename_ = "claim_settlements"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    settled_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    recorded_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ClaimDraft(Base, WorkspaceScopedMixin):
    _tablename_ = "claim_drafts"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    draft_kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    body: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
