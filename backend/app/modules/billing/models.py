"""Billing-owned tables (Doc §3.2, §16.5). payment_log is the append-only
financial ledger — it records every webhook (even signature-failed/duplicate)
before acting, so money history can never be lost."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin

_BigId = BigInteger().with_variant(Integer, "sqlite")

# Billing's own sentinel for "no workspace known yet" (e.g. a webhook event
# whose notes carry no resolvable intent). Deliberately distinct from auth's
# AuthService._NO_WORKSPACE (all-zero UUID) — sharing one sentinel would let a
# workspace-less superadmin session and an orphaned payment_log row collide in
# the same pseudo-workspace (R-005 §C.6).
UNATTRIBUTED_WORKSPACE = uuid.UUID("00000000-0000-0000-0000-0000000000ff")


class UsageEvent(Base, WorkspaceScopedMixin):
    _tablename_ = "usage_events"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(String, nullable=False)  # review_started|review_paid|...
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PaymentLog(Base, WorkspaceScopedMixin):
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


class WebhookEvent(Base, WorkspaceScopedMixin):
    """Idempotency ledger — a processed provider event id is a no-op on replay."""

    _tablename_ = "webhook_events"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PaymentIntent(Base):
    """Server-side record of what was ordered, at what price, for whom
    (R-005 §B.2). The webhook resolves the grant from THIS row, never from
    provider `notes` — client-supplied fields influence nothing after
    creation. This is the fix for: a customer who could previously influence
    their own order's notes could pay for Pro and receive Scale.

    Deliberately NOT WorkspaceScopedMixin / RLS-protected: the webhook must
    look this row up by its opaque id BEFORE it knows which workspace it
    belongs to (that's the whole point of the lookup) — RLS would block the
    very query that discovers the workspace, the same chicken-and-egg problem
    login/refresh have. Same precedent as RefreshToken/PasswordReset: an
    unauthenticated caller presents an opaque, unguessable 128-bit id as its
    own authorization, and application code (never a bare query) is
    responsible for checking workspace ownership wherever a PaymentIntent is
    read from an AUTHENTICATED route (e.g. a future intent-status endpoint).
    """

    __tablename__ = "payment_intents"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # paygo | subscription
    plan: Mapped[str | None] = mapped_column(String, nullable=True)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    list_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Reserved (not yet consumed) at checkout time; the consuming Credit
    # ledger entry is written only on payment success (R-006 §B.2/B.3) — an
    # abandoned checkout must never burn a balance the customer never spent.
    credit_applied_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)  # what we charge
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    coupon_code: Mapped[str | None] = mapped_column(String, nullable=True)  # R-006
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    checkout_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String, nullable=False, default="created")
    # created | pending | paid | failed | expired | refunded | amount_mismatch
    idempotency_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Invoice(Base, WorkspaceScopedMixin):
    """Customer-visible GST invoices/credit notes issued from paid/refunded
    events (R-007). Buyer/seller identity is snapshotted here at issuance —
    never joined from `Workspace` at render time — because an invoice is a
    statutory record of a moment; a later change to the workspace's GSTIN or
    name must never rewrite an already-issued document."""

    _tablename_ = "invoices"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    fy: Mapped[str] = mapped_column(String, nullable=False)  # "2026-27"
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # gap-free, per FY

    doc_type: Mapped[str] = mapped_column(String, nullable=False, default="invoice")
    # invoice | credit_note
    original_invoice_id: Mapped[int | None] = mapped_column(_BigId, nullable=True)

    base_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)  # taxable value
    cgst_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sgst_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    igst_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    round_off_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")

    sac_code: Mapped[str] = mapped_column(String, nullable=False, default="998313")
    seller_gstin: Mapped[str | None] = mapped_column(String, nullable=True)
    buyer_gstin: Mapped[str | None] = mapped_column(String, nullable=True)
    buyer_legal_name: Mapped[str | None] = mapped_column(String, nullable=True)
    place_of_supply: Mapped[str | None] = mapped_column(String, nullable=True)

    payment_intent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_invoice_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    raw: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class InvoiceSequence(Base):
    """One row per financial year. Gap-free numbering (R-007 §B.3) requires
    the sequence to advance inside the SAME transaction that inserts the
    invoice, serialized with `SELECT ... FOR UPDATE` — a Postgres SEQUENCE
    would leak numbers on a rolled-back transaction, which GST's
    consecutive-numbering requirement does not tolerate."""

    __tablename__ = "invoice_sequences"
    fy: Mapped[str] = mapped_column(String, primary_key=True)
    last_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Coupon(Base):
    """Discount definitions (R-006). NOT workspace-scoped — a coupon is a
    global object many workspaces may redeem; restrictions live in the
    columns below, not in RLS."""

    __tablename__ = "coupons"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    # Stored uppercase; lookups uppercase the input so codes are case-insensitive.

    kind: Mapped[str] = mapped_column(String, nullable=False)
    # percent | fixed | free_months | free_reviews
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    # percent: 1..100 · fixed: minor units · free_months/free_reviews: a count
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    # required for kind="fixed" — a fixed rupee discount can't apply to a GBP order

    applies_to: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # {"plans": [...], "kinds": [...], "first_purchase_only": true}

    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_per_workspace: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    redeemed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    campaign: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CouponRedemption(Base, WorkspaceScopedMixin):
    """Append-only redemption ledger — one row per successful application,
    written only when a payment SUCCEEDS, never at quote time, so an
    abandoned checkout never burns a redemption (R-006 §B.2/B.4).
    `payment_intent_id` is unique: a duplicate webhook delivery for the same
    intent hits a unique-constraint violation here (caught, not re-raised)
    instead of double-redeeming, the same idempotency idiom as
    `WebhookEvent` (R-006 §A5)."""

    _tablename_ = "coupon_redemptions"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    coupon_id: Mapped[int] = mapped_column(_BigId, nullable=False, index=True)
    payment_intent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, unique=True)
    discount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Credit(Base, WorkspaceScopedMixin):
    """Prepaid balance ledger: referral rewards, goodwill, refund-to-credit
    (R-006). Consumed before charging a card. The balance is the sum of this
    ledger, never a mutable column — same discipline as `payment_log`/
    `usage_events`: a running total can drift from its history; a ledger
    can't."""

    _tablename_ = "credits"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)  # +granted / -consumed
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    reason: Mapped[str] = mapped_column(String, nullable=False)
    # referral | goodwill | refund | promo | pilot | consumed
    ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Referral(Base):
    """One row per referral RELATIONSHIP (referrer -> referred), created when
    a referred workspace signs up using the referrer's code (R-006 §B.7).
    Deliberately not WorkspaceScopedMixin: a single row is jointly relevant to
    TWO workspaces (referrer and referred), so no single `workspace_id`
    column could be the RLS-scoping key without arbitrarily picking a side —
    both `GET /billing/referral` (referrer's own stats) and the reward
    crediting in `_on_payment_succeeded` (billing's own code, not
    request-scoped) query this directly by workspace id in application code
    instead."""

    __tablename__ = "referrals"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    referrer_workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    referred_workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String, nullable=False)  # the code used, for audit
    status: Mapped[str] = mapped_column(String, nullable=False, default="signed_up")
    # signed_up | rewarded
    reward_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReferralCode(Base):
    """Cross-tenant-resolvable pointer from a referral code to its owning
    workspace (R-006 §B.7).

    Deliberately NOT WorkspaceScopedMixin / RLS-protected — same precedent as
    `PaymentIntent`/`RefreshToken`/`PasswordReset`: a person signing up who is
    not yet a member of ANY workspace must be able to resolve someone else's
    referral code. `Workspace.referral_code` (RLS-protected, same value,
    written alongside this row) remains the referrer's own same-tenant read
    path (`GET /billing/referral`); this table exists only so a stranger's
    signup can look the code up without RLS's compound predicate hiding the
    referrer's `workspaces` row. `owner_email_domain` is snapshotted here too
    so the self-referral check (R-006 §A9) never needs a second cross-tenant
    `Workspace`/`User` read."""

    __tablename__ = "referral_codes"
    code: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, unique=True)
    owner_email_domain: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
