"""BillingService — metering + webhook truth (Doc §7, §15). Consumes auth's
workspace-admin capability; never imports auth. The webhook is the only thing
that activates a plan or credits a paid review."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import bind_workspace_context
from app.modules.billing.models import (
    UNATTRIBUTED_WORKSPACE,
    Invoice,
    PaymentIntent,
    PaymentLog,
    UsageEvent,
    WebhookEvent,
)
from app.modules.billing.plans import (
    CURRENCY_BY_COUNTRY,
    Grant,
    PaywallError,
    authorize,
    price_for,
)
from app.modules.billing.providers.base import OrderRequest


class BillingService:
    def __init__(self, session: Session, *, workspace_factory=None, provider_factory=None):
        self.s = session
        self._workspace_factory = workspace_factory
        # Callable[[country: str], PaymentProvider | None] — resolved lazily
        # because create_checkout doesn't know the workspace's country (which
        # picks Razorpay vs Stripe, R-005 §A) until it has already looked the
        # workspace up. Defaults to "no provider configured" everywhere.
        self._provider_factory = provider_factory or (lambda country: None)

    def _workspaces(self):
        if self._workspace_factory is None:
            raise PaywallError("workspace_unavailable")
        return self._workspace_factory(self.s)

    def _month_reviews(self, workspace_id) -> int:
        start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return (
            self.s.scalar(
                select(func.count(UsageEvent.id)).where(
                    UsageEvent.workspace_id == uuid.UUID(str(workspace_id)),
                    UsageEvent.event == "review_started",
                    UsageEvent.created_at >= start,
                )
            )
            or 0
        )

    def record_usage(self, workspace_id, event: str, ref_id=None, *, commit: bool = True) -> None:
        self.s.add(
            UsageEvent(
                workspace_id=uuid.UUID(str(workspace_id)),
                event=event,
                ref_id=uuid.UUID(str(ref_id)) if ref_id else None,
            )
        )
        if commit:
            self.s.commit()

    def _already_metered(self, workspace_id, opportunity_id) -> bool:
        """Doc §7 B1: a review is metered at processing start; re-processing
        an already-metered opportunity (e.g. after an addendum) is free — an
        addendum must never cost a second review, or customers stop uploading
        addenda, which is the exact failure the product exists to prevent."""
        return (
            self.s.scalar(
                select(UsageEvent.id)
                .where(
                    UsageEvent.workspace_id == uuid.UUID(str(workspace_id)),
                    UsageEvent.event == "review_started",
                    UsageEvent.ref_id == uuid.UUID(str(opportunity_id)),
                )
                .limit(1)
            )
            is not None
        )

    def _lock(self, workspace_id) -> None:
        """Serialise metering per workspace (Doc §7 B2, R-004 §A.4) so two
        concurrent review starts cannot both observe free_review_used=False
        and both spend the single free review. pg_advisory_xact_lock releases
        automatically at the end of the current transaction — a no-op on
        SQLite, where tests are effectively single-threaded against one
        connection anyway.
        """
        if self.s.get_bind().dialect.name != "postgresql":
            return
        key = int(uuid.UUID(str(workspace_id)).int & 0x7FFFFFFFFFFFFFFF)
        self.s.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})

    def authorize_review(self, workspace_id, opportunity_id=None) -> Grant:
        """Meter a review at processing start (Doc §7). Raises PaywallError with
        an upsell payload when blocked.

        The lock, the free-review write, and the usage-event write all happen
        in ONE transaction (single commit at the end) — splitting them across
        separate commits would release the advisory lock before the write it
        exists to protect, which is exactly the bug this replaces (R-004 §A.4).
        """
        if opportunity_id is not None and self._already_metered(workspace_id, opportunity_id):
            return Grant(kind="already_metered")

        self._lock(workspace_id)
        workspace = self._workspaces().get(workspace_id)
        if workspace is None:
            raise PaywallError("no_workspace")
        grant = authorize(
            plan=workspace.plan,
            free_review_used=workspace.free_review_used,
            reviews_this_month=self._month_reviews(workspace_id),
        )
        if grant.kind == "free_first_review":
            self._workspaces().mark_free_review_used(workspace_id)
            self.record_usage(workspace_id, "review_started", ref_id=opportunity_id, commit=False)
        elif grant.kind == "plan":
            self.record_usage(workspace_id, "review_started", ref_id=opportunity_id, commit=False)
        # paygo: nothing recorded until the webhook confirms payment
        self.s.commit()
        return grant

    def export_entitlement(self, workspace_id) -> dict:
        """Whether this workspace's exports carry the free-tier watermark
        (Doc §7, R-004 §B). Free plan → watermarked, always, including
        re-exports of the one free review — the watermark is the ONLY thing
        distinguishing free output from paid output (the free review is
        deliberately a complete review, Doc §706), so it can never be a
        client-controlled choice. Any paid plan → clean.
        """
        workspace = self._workspaces().get(workspace_id)
        return {"watermark": bool(workspace and workspace.plan == "free")}

    def status(self, workspace_id) -> dict:
        workspace = self._workspaces().get(workspace_id)
        return {
            "plan": workspace.plan if workspace else None,
            "plan_status": workspace.plan_status if workspace else None,
            "grace_until": workspace.grace_until.isoformat()
            if workspace and workspace.grace_until
            else None,
            "free_review_used": workspace.free_review_used if workspace else None,
            "reviews_this_month": self._month_reviews(workspace_id),
        }

    # ---- checkout: real orders, server-side price/plan binding (R-005 §B) -

    def create_checkout(
        self, workspace_id, *, kind: str, plan: str, opportunity_id=None, coupon_code=None
    ) -> dict:
        """Creates a payment_intents row BEFORE contacting the provider, and
        resolves price from PRICES_MINOR server-side — the client selects
        WHICH plan, never what it costs (R-005 §B.1-B.2). The provider round-
        trips only an opaque `intent_id`; nothing about the eventual grant is
        ever read back from provider `notes`.
        """
        workspace = self._workspaces().get(workspace_id)
        if workspace is None:
            raise PaywallError("no_workspace")
        provider = self._provider_factory(workspace.country)
        if provider is None:
            raise PaywallError("payment_provider_unavailable")

        currency = CURRENCY_BY_COUNTRY.get(workspace.country, "INR")
        list_amount = price_for(plan, currency)  # raises PaywallError("unknown_plan")
        # Coupons (R-006) and GST (R-007) are not wired to checkout yet —
        # discount/tax are computed but always zero until those tasks land.
        discount_minor = 0
        tax_minor = 0
        amount_minor = list_amount - discount_minor + tax_minor

        idempotency_key = _checkout_idempotency_key(workspace_id, kind, plan, opportunity_id)
        existing = self.s.scalar(
            select(PaymentIntent).where(PaymentIntent.idempotency_key == idempotency_key)
        )
        if existing is not None and existing.status in ("created", "pending"):
            # A retry within the same window (e.g. a network blip) reopens the
            # SAME order rather than creating a duplicate (R-005 A9).
            return _checkout_response(existing)

        intent = PaymentIntent(
            workspace_id=uuid.UUID(str(workspace_id)),
            kind=kind,
            plan=plan,
            opportunity_id=uuid.UUID(str(opportunity_id)) if opportunity_id else None,
            list_amount_minor=list_amount,
            discount_minor=discount_minor,
            tax_minor=tax_minor,
            amount_minor=amount_minor,
            currency=currency,
            coupon_code=coupon_code,
            provider=provider.name,
            idempotency_key=idempotency_key,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        self.s.add(intent)
        self.s.flush()  # obtain intent.id for the order's notes

        handle = provider.create_order(
            OrderRequest(
                workspace_id=str(workspace_id),
                amount_minor=amount_minor,
                currency=currency,
                kind=kind,
                plan=plan,
                opportunity_id=opportunity_id,
                idempotency_key=idempotency_key,
                notes={"intent_id": str(intent.id)},  # opaque reference ONLY
            )
        )
        intent.provider_order_id = handle.order_id
        intent.checkout_payload = handle.checkout_payload
        intent.status = "pending"
        self.s.commit()
        return _checkout_response(intent)

    def get_intent_status(self, workspace_id, intent_id) -> dict:
        """Ownership check happens HERE, in application code — PaymentIntent
        carries no RLS (see the model's own docstring for why)."""
        intent = self.s.scalar(
            select(PaymentIntent).where(PaymentIntent.id == uuid.UUID(intent_id))
        )
        if intent is None or str(intent.workspace_id) != str(workspace_id):
            return {"status": "not_found"}
        return {"status": intent.status, "amount_minor": intent.amount_minor}

    # ---- invoices ---------------------------------------------------------
    def list_invoices(self, workspace_id) -> list[Invoice]:
        return list(
            self.s.scalars(
                select(Invoice)
                .where(Invoice.workspace_id == uuid.UUID(str(workspace_id)))
                .order_by(Invoice.created_at.desc())
            )
        )

    def create_invoice(
        self,
        workspace_id,
        *,
        amount_minor: int,
        currency: str = "INR",
        provider: str = "manual",
        provider_invoice_id: str | None = None,
        raw: dict | None = None,
        status: str = "pending",
    ) -> Invoice:
        inv = Invoice(
            workspace_id=uuid.UUID(str(workspace_id)),
            invoice_number=uuid.uuid4().hex,  # temporary; replaced with INV- id after flush
            amount_minor=amount_minor,
            currency=currency,
            provider=provider,
            provider_invoice_id=provider_invoice_id,
            raw=raw or {},
            status=status,
        )
        self.s.add(inv)
        self.s.flush()  # obtain id
        inv.invoice_number = f"INV-{inv.id:06d}"
        if status == "paid":
            inv.paid_at = datetime.now(UTC)
        self.s.commit()
        return inv

    # ---- webhook: the only billing truth (Doc §15.5, R-005 §C) ------------
    def process_webhook(self, raw_body: bytes, signature: str) -> dict:
        """Verify → log → dedupe → apply, in that order (Doc §16.5). The
        grant is always resolved from the payment_intents row the event
        references, never from provider `notes` directly (R-005 §B.3) —
        `notes` carries only an opaque `intent_id` used to FIND that row.
        """
        provider = self._provider_factory("IN")  # this route is Razorpay-only (India) for v1
        if provider is None:
            return {"ok": False, "reason": "provider_unavailable"}

        verified = provider.verify_webhook(raw_body, signature)
        event = provider.parse_event(raw_body)
        intent = self._intent_for(event.reference_id) if verified else None
        log_workspace = intent.workspace_id if intent else UNATTRIBUTED_WORKSPACE

        # 1) log receipt BEFORE trusting anything — durable regardless of what
        # happens next; _log commits internally (Doc §16.5).
        bind_workspace_context(self.s, log_workspace)
        self._log(
            log_workspace,
            event.provider,
            event.event_id,
            event.type,
            status="verified" if verified else "failed",
            raw=event.raw,
            amount_minor=event.amount_minor,
            currency=event.currency,
        )
        if not verified:
            return {"ok": False, "reason": "bad_signature"}

        # 2) idempotency via a unique-constraint insert, not check-then-act
        # (R-005 §C.2) — a body-hash fallback means an event with no id can't
        # be replayed indefinitely either.
        dedupe_key = event.event_id or f"sha256:{hashlib.sha256(raw_body).hexdigest()}"
        try:
            self.s.add(
                WebhookEvent(
                    workspace_id=log_workspace,
                    provider=event.provider,
                    provider_event_id=dedupe_key,
                )
            )
            self.s.flush()
        except IntegrityError:
            self.s.rollback()
            return {"ok": True, "duplicate": True}

        # 3) apply effect — only for events tied to a resolvable intent
        if intent is None:
            self.s.commit()
            return {"ok": True, "applied": None}

        handler = _HANDLERS.get(event.type)
        if handler is not None:
            handler(self, intent, event)
        self.s.commit()
        return {"ok": True, "applied": event.type if handler else None}

    def _intent_for(self, reference_id: str | None) -> PaymentIntent | None:
        if not reference_id:
            return None
        try:
            intent_uuid = uuid.UUID(str(reference_id))
        except ValueError:
            return None
        return self.s.scalar(select(PaymentIntent).where(PaymentIntent.id == intent_uuid))

    def _on_payment_succeeded(self, intent: PaymentIntent, event) -> None:
        """A paygo payment, a subscription's first activation, or a renewal
        charge succeeded — all three carry a payment amount to verify, so all
        three go through the SAME amount check. (subscription.activated was
        previously a separate handler that skipped this check entirely — an
        underpaid subscription activation still granted the plan. Caught by
        test_webhook_amount_mismatch_grants_nothing, which sends
        subscription.activated specifically.)
        """
        if event.amount_minor is not None and event.amount_minor != intent.amount_minor:
            # Underpayment/overpayment: log, do not grant. This is the check
            # whose absence let a customer pay for one plan and receive
            # another (R-005 §B.1, §C.3 A3/A4).
            self._log(
                intent.workspace_id,
                event.provider,
                event.event_id,
                event.type,
                status="amount_mismatch",
                raw=event.raw,
                amount_minor=event.amount_minor,
                currency=event.currency,
            )
            intent.status = "amount_mismatch"
            return
        intent.status = "paid"
        if intent.kind == "subscription":
            self._workspaces().set_plan(intent.workspace_id, intent.plan)
            self._workspaces().set_plan_status(
                intent.workspace_id,
                "active",
                grace_until=None,
                provider_subscription_id=_subscription_id(event.raw),
            )
        else:
            self.record_usage(intent.workspace_id, "review_paid", ref_id=intent.opportunity_id)
        self.create_invoice(
            intent.workspace_id,
            amount_minor=intent.amount_minor,
            currency=intent.currency,
            provider=event.provider,
            provider_invoice_id=event.event_id,
            raw=event.raw,
            status="paid",
        )

    def _on_payment_failed(self, intent: PaymentIntent, event) -> None:
        intent.status = "failed"

    _GRACE_DAYS = 7

    def _on_subscription_past_due(self, intent: PaymentIntent, event) -> None:
        """Never delete data on non-payment (specs/modules/billing.md B8).
        Downgrade is deferred by _GRACE_DAYS; during grace the workspace keeps
        full access. Contractors often pay by NEFT on their own cycle — an
        instant downgrade loses accounts that would have paid a few days late.
        """
        self._workspaces().set_plan_status(
            intent.workspace_id,
            "past_due",
            grace_until=datetime.now(UTC) + timedelta(days=self._GRACE_DAYS),
        )

    def _on_subscription_cancelled(self, intent: PaymentIntent, event) -> None:
        self._workspaces().set_plan(intent.workspace_id, "free")
        self._workspaces().set_plan_status(intent.workspace_id, "cancelled", grace_until=None)

    def _on_refund(self, intent: PaymentIntent, event) -> None:
        intent.status = "refunded"
        if intent.kind == "subscription":
            self._workspaces().set_plan(intent.workspace_id, "free")
            self._workspaces().set_plan_status(intent.workspace_id, "cancelled", grace_until=None)
        else:
            self.record_usage(intent.workspace_id, "review_refunded", ref_id=intent.opportunity_id)
        # GST credit note issuance is R-007/TS-096 — not wired here yet.

    def _log(
        self,
        workspace_id,
        provider,
        event_id,
        event_type,
        *,
        status,
        raw,
        amount_minor: int | None = None,
        currency: str | None = None,
    ):
        self.s.add(
            PaymentLog(
                workspace_id=uuid.UUID(str(workspace_id)),
                provider=provider,
                provider_event_id=event_id or None,
                event_type=event_type,
                amount_minor=amount_minor,
                currency=currency,
                status=status,
                raw=raw,
            )
        )
        self.s.commit()


# Dispatch table: Razorpay's own event names (already namespaced sensibly, so
# no translation layer is invented for a single-provider v1 — R-005 §C.3).
# Everything not listed here is logged (via _log, above) but not applied —
# e.g. subscription.pending/completed/updated, dispute.created: acknowledged,
# not yet acted on.
_HANDLERS = {
    "order.paid": BillingService._on_payment_succeeded,
    "subscription.charged": BillingService._on_payment_succeeded,
    "subscription.activated": BillingService._on_payment_succeeded,
    "payment.failed": BillingService._on_payment_failed,
    "subscription.halted": BillingService._on_subscription_past_due,
    "subscription.cancelled": BillingService._on_subscription_cancelled,
    "refund.processed": BillingService._on_refund,
}


def _subscription_id(raw_event: dict) -> str | None:
    return raw_event.get("payload", {}).get("subscription", {}).get("entity", {}).get("id")


def _checkout_idempotency_key(workspace_id, kind: str, plan: str, opportunity_id) -> str:
    """Deterministic within a coarse time bucket so a client retry (e.g. after
    a network blip) reopens the same order instead of creating a duplicate,
    while a genuinely new purchase later still gets a fresh key. Bucket width
    matches the intent's own 30-minute expiry."""
    bucket = int(datetime.now(UTC).timestamp() // 1800)
    return f"{workspace_id}:{kind}:{plan}:{opportunity_id or '-'}:{bucket}"


def _checkout_response(intent: PaymentIntent) -> dict:
    return {
        "intent_id": str(intent.id),
        "provider": intent.provider,
        "order_id": intent.provider_order_id,
        "amount_minor": intent.amount_minor,
        "currency": intent.currency,
        "breakdown": {
            "list": intent.list_amount_minor,
            "discount": intent.discount_minor,
            "tax": intent.tax_minor,
            "total": intent.amount_minor,
        },
        "checkout": intent.checkout_payload,
    }
