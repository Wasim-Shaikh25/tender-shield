"""Billing-owned tables (Doc §3.2, §16.5). payment_log is the append-only
financial ledger — it records every webhook (even signature-failed/duplicate)
before acting, so money history can never be lost."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, OrgScopedMixin

_BigId = BigInteger().with_variant(Integer, "sqlite")


class UsageEvent(Base, OrgScopedMixin):
    _tablename_ = "usage_events"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(String, nullable=False)  # review_started|review_paid|...
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PaymentLog(Base, OrgScopedMixin):
    _tablename_ = "payment_log"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)  # razorpay|stripe|internal
    provider_event_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)  # received|verified|applied|failed
    raw: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WebhookEvent(Base, OrgScopedMixin):
    """Idempotency ledger — a processed provider event id is a no-op on replay."""

    _tablename_ = "webhook_events"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Invoice(Base, OrgScopedMixin):
    """Customer-visible GST invoices generated from paid events."""

    _tablename_ = "invoices"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_invoice_id: Mapped[str | None] = mapped_column(String, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
