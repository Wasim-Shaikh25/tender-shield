"""BillingService — metering + webhook truth (Doc §7, §15). Consumes auth's
org-admin capability; never imports auth. The webhook is the only thing that
activates a plan or credits a paid review."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.billing.models import Invoice, PaymentLog, UsageEvent, WebhookEvent
from app.modules.billing.plans import Grant, PaywallError, authorize
from app.modules.billing.webhook import verify_signature, verify_stripe_signature


class BillingService:
    def __init__(self, session: Session, *, workspace_factory=None):
        self.s = session
        self._workspace_factory = workspace_factory

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

    def record_usage(self, workspace_id, event: str, ref_id=None) -> None:
        self.s.add(
            UsageEvent(
                workspace_id=uuid.UUID(str(workspace_id)),
                event=event,
                ref_id=uuid.UUID(str(ref_id)) if ref_id else None,
            )
        )
        self.s.commit()

    def authorize_review(self, workspace_id) -> Grant:
        """Meter a review at processing start (Doc §7). Raises PaywallError with
        an upsell payload when blocked."""
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
            self.record_usage(workspace_id, "review_started")
        elif grant.kind == "plan":
            self.record_usage(workspace_id, "review_started")
        # paygo: nothing recorded until the webhook confirms payment
        return grant

    def status(self, workspace_id) -> dict:
        workspace = self._workspaces().get(workspace_id)
        return {
            "plan": workspace.plan if workspace else None,
            "free_review_used": workspace.free_review_used if workspace else None,
            "reviews_this_month": self._month_reviews(workspace_id),
        }

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

    # ---- webhook: the only billing truth (Doc §15.5) ----------------------
    def process_razorpay_webhook(self, raw_body: bytes, signature: str, secret: str) -> dict:
        # 1) log receipt BEFORE trusting anything (fraud/debug trail, §16.5)
        verified = verify_signature(raw_body, signature, secret)
        try:
            evt = json.loads(raw_body)
        except (ValueError, json.JSONDecodeError):
            evt = {}
        event_id = evt.get("id", "")
        notes = _extract_notes(evt)
        workspace_id = notes.get("workspace_id")

        self._log(
            workspace_id,
            "razorpay",
            event_id,
            evt.get("event", "unknown"),
            status="verified" if verified else "failed",
            raw=evt,
        )
        if not verified:
            return {"ok": False, "reason": "bad_signature"}

        # 2) idempotency — a replayed event id is a no-op
        if event_id and self.s.scalar(
            select(WebhookEvent).where(WebhookEvent.provider_event_id == event_id)
        ):
            return {"ok": True, "duplicate": True}

        # 3) apply effect
        typ = evt.get("event")
        amount = _extract_amount(evt)
        if typ == "order.paid" and workspace_id:
            self.record_usage(workspace_id, "review_paid", ref_id=notes.get("opportunity_id"))
            if amount:
                self.create_invoice(
                    workspace_id,
                    amount_minor=amount,
                    provider="razorpay",
                    provider_invoice_id=event_id,
                    raw=evt,
                    status="paid",
                )
        elif typ == "subscription.charged" and workspace_id:
            self._workspaces().set_plan(workspace_id, notes.get("plan", "pro"))
            if amount:
                self.create_invoice(
                    workspace_id,
                    amount_minor=amount,
                    provider="razorpay",
                    provider_invoice_id=event_id,
                    raw=evt,
                    status="paid",
                )
        elif typ == "subscription.activated" and workspace_id:
            self._workspaces().set_plan(workspace_id, notes.get("plan", "pro"))
        elif typ in ("subscription.halted", "subscription.cancelled") and workspace_id:
            self._workspaces().set_plan(workspace_id, "free")

        if event_id:
            self.s.add(
                WebhookEvent(
                    workspace_id=uuid.UUID(str(workspace_id)) if workspace_id else uuid.UUID(int=0),
                    provider="razorpay",
                    provider_event_id=event_id,
                )
            )
        self.s.commit()
        return {"ok": True, "applied": typ}

    def process_stripe_webhook(self, raw_body: bytes, signature: str, secret: str) -> dict:
        evt = verify_stripe_signature(raw_body, signature, secret)
        event_id = evt.get("id", "") if isinstance(evt, dict) else ""
        event_type = evt.get("type", "unknown") if isinstance(evt, dict) else "unknown"
        status = "verified" if evt else "failed"
        self._log(None, "stripe", event_id, event_type, status=status, raw=evt)
        if not evt:
            return {"ok": False, "reason": "bad_signature"}

        # Idempotency: replays are no-ops
        if event_id and self.s.scalar(
            select(WebhookEvent).where(WebhookEvent.provider_event_id == event_id)
        ):
            return {"ok": True, "duplicate": True}

        data = evt.get("data", {}) if isinstance(evt, dict) else {}
        obj = data.get("object", {}) if isinstance(data, dict) else {}
        metadata = obj.get("metadata", {}) if isinstance(obj, dict) else {}
        workspace_id = metadata.get("workspace_id")

        if event_type == "checkout.session.completed" and workspace_id:
            amount = obj.get("amount_total")
            currency = obj.get("currency", "INR").upper()
            kind = metadata.get("kind", "paygo")
            if kind == "paygo":
                self.record_usage(
                    workspace_id, "review_paid", ref_id=metadata.get("opportunity_id")
                )
                if amount:
                    self.create_invoice(
                        workspace_id,
                        amount_minor=int(amount),
                        currency=currency,
                        provider="stripe",
                        provider_invoice_id=obj.get("id") or event_id,
                        raw=evt,
                        status="paid",
                    )
            elif kind == "subscription":
                self._workspaces().set_plan(workspace_id, metadata.get("plan", "pro"))
                if amount:
                    self.create_invoice(
                        workspace_id,
                        amount_minor=int(amount),
                        currency=currency,
                        provider="stripe",
                        provider_invoice_id=obj.get("id") or event_id,
                        raw=evt,
                        status="paid",
                    )

        if event_id:
            self.s.add(
                WebhookEvent(
                    workspace_id=uuid.UUID(str(workspace_id)) if workspace_id else uuid.UUID(int=0),
                    provider="stripe",
                    provider_event_id=event_id,
                )
            )
        self.s.commit()
        return {"ok": True, "applied": event_type}

    def _log(self, workspace_id, provider, event_id, event_type, *, status, raw):
        self.s.add(
            PaymentLog(
                workspace_id=uuid.UUID(str(workspace_id)) if workspace_id else uuid.UUID(int=0),
                provider=provider,
                provider_event_id=event_id or None,
                event_type=event_type,
                status=status,
                raw=raw,
            )
        )
        self.s.commit()


def _extract_notes(evt: dict) -> dict:
    """Razorpay puts our notes on the entity inside payload.<type>.entity.notes."""
    payload = evt.get("payload", {})
    for wrapper in payload.values():
        entity = wrapper.get("entity", {}) if isinstance(wrapper, dict) else {}
        if "notes" in entity and isinstance(entity["notes"], dict):
            return entity["notes"]
    return {}


def _extract_amount(evt: dict) -> int | None:
    """Best-effort amount in minor units from a Razorpay payment event."""
    payload = evt.get("payload", {})
    for wrapper in payload.values():
        entity = wrapper.get("entity", {}) if isinstance(wrapper, dict) else {}
        amt = entity.get("amount")
        if isinstance(amt, (int, str)):
            try:
                return int(amt)
            except ValueError:
                continue
    return None
