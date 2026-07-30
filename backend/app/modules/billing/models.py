"""Billing-owned tables (Doc §3.2, §16.5).

- `usage_events` tracks metered consumption per user account (workspace_id is
  retained for attribution but the plan limit is account-wide).
- `payment_log` is the append-only financial ledger per user account.
- `webhook_events` is a global idempotency ledger.
- `plan_history` records every user account plan change.
- `invoices` are customer-visible GST invoices per user account.
- `coupon` stores discount codes that can be applied at checkout.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_BigId = BigInteger().with_variant(Integer, "sqlite")


class UsageEvent(Base):
    __tablename__ = "usage_events"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    event: Mapped[str] = mapped_column(String, nullable=False)  # review_started|review_paid|...
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PaymentLog(Base):
    __tablename__ = "payment_log"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
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


class WebhookEvent(Base):
    """Global idempotency ledger — a processed provider event id is a no-op on replay."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_webhook_provider_event_id"),
    )
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Invoice(Base):
    """Customer-visible GST invoices generated from paid events."""

    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
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


class PlanHistory(Base):
    """Audit of user account plan changes so users and admins can see billing history."""

    __tablename__ = "plan_history"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    old_plan: Mapped[str] = mapped_column(String, nullable=False)
    new_plan: Mapped[str] = mapped_column(String, nullable=False)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Coupon(Base):
    """Discount codes generated by super-admins and applied at checkout."""

    __tablename__ = "coupons"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    discount_type: Mapped[str] = mapped_column(
        String, nullable=False, default="percent"  # percent | fixed
    )
    discount_value: Mapped[int] = mapped_column(Integer, nullable=False)
    # For `percent`, value is in whole percent (e.g. 15 = 15%).
    # For `fixed`, value is in minor units (paise).
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uses_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
