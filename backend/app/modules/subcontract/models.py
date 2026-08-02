"""Subcontract-owned tables (TS-288, TS-289)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class Subcontract(Base, WorkspaceScopedMixin):
    _tablename_ = "subcontracts"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subcontractor_name: Mapped[str] = mapped_column(String, nullable=False)
    reference: Mapped[str | None] = mapped_column(String, nullable=True)
    contract_value_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    notice_buffer_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    postal_buffer_days: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SubcontractClause(Base, WorkspaceScopedMixin):
    _tablename_ = "subcontract_clauses"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subcontract_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subcontracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    source_quote: Mapped[str | None] = mapped_column(String, nullable=True)
    present: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="unchecked")
    source_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SubcontractScopeItem(Base, WorkspaceScopedMixin):
    _tablename_ = "subcontract_scope_items"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subcontract_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subcontracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_text: Mapped[str] = mapped_column(String, nullable=False)
    covered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("change_events.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SubcontractPaymentEvent(Base, WorkspaceScopedMixin):
    _tablename_ = "subcontract_payment_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subcontract_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subcontracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)  # ra, progress, retention
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    certified_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    parent_payment_status: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
