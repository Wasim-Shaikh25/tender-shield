"""BillingService — metering + webhook truth (Doc §7, §15). Consumes auth's
org-admin capability; never imports auth. The webhook is the only thing that
activates a plan or credits a paid review."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.billing.models import PaymentLog, UsageEvent, WebhookEvent
from app.modules.billing.plans import Grant, PaywallError, authorize
from app.modules.billing.webhook import verify_signature


class BillingService:
    def __init__(self, session: Session, *, orgs_factory=None):
        self.s = session
        self._orgs_factory = orgs_factory

    def _orgs(self):
        if self._orgs_factory is None:
            raise PaywallError("orgs_unavailable")
        return self._orgs_factory(self.s)

    def _month_reviews(self, org_id) -> int:
        start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return (
            self.s.scalar(
                select(func.count(UsageEvent.id)).where(
                    UsageEvent.org_id == uuid.UUID(str(org_id)),
                    UsageEvent.event == "review_started",
                    UsageEvent.created_at >= start,
                )
            )
            or 0
        )

    def record_usage(self, org_id, event: str, ref_id=None) -> None:
        self.s.add(
            UsageEvent(
                org_id=uuid.UUID(str(org_id)),
                event=event,
                ref_id=uuid.UUID(str(ref_id)) if ref_id else None,
            )
        )
        self.s.commit()

    def authorize_review(self, org_id) -> Grant:
        """Meter a review at processing start (Doc §7). Raises PaywallError with
        an upsell payload when blocked."""
        org = self._orgs().get(org_id)
        if org is None:
            raise PaywallError("no_org")
        grant = authorize(
            plan=org.plan,
            free_review_used=org.free_review_used,
            reviews_this_month=self._month_reviews(org_id),
        )
        if grant.kind == "free_first_review":
            self._orgs().mark_free_review_used(org_id)
            self.record_usage(org_id, "review_started")
        elif grant.kind == "plan":
            self.record_usage(org_id, "review_started")
        # paygo: nothing recorded until the webhook confirms payment
        return grant

    def status(self, org_id) -> dict:
        org = self._orgs().get(org_id)
        return {
            "plan": org.plan if org else None,
            "free_review_used": org.free_review_used if org else None,
            "reviews_this_month": self._month_reviews(org_id),
        }

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
        org_id = notes.get("org_id")

        self._log(org_id, "razorpay", event_id, evt.get("event", "unknown"),
                  status="verified" if verified else "failed", raw=evt)
        if not verified:
            return {"ok": False, "reason": "bad_signature"}

        # 2) idempotency — a replayed event id is a no-op
        if event_id and self.s.scalar(
            select(WebhookEvent).where(WebhookEvent.provider_event_id == event_id)
        ):
            return {"ok": True, "duplicate": True}

        # 3) apply effect
        typ = evt.get("event")
        if typ == "order.paid" and org_id:
            self.record_usage(org_id, "review_paid", ref_id=notes.get("opportunity_id"))
        elif typ in ("subscription.activated", "subscription.charged") and org_id:
            self._orgs().set_plan(org_id, notes.get("plan", "pro"))
        elif typ in ("subscription.halted", "subscription.cancelled") and org_id:
            self._orgs().set_plan(org_id, "free")

        if event_id:
            self.s.add(
                WebhookEvent(
                    org_id=uuid.UUID(str(org_id)) if org_id else uuid.UUID(int=0),
                    provider="razorpay",
                    provider_event_id=event_id,
                )
            )
        self.s.commit()
        return {"ok": True, "applied": typ}

    def _log(self, org_id, provider, event_id, event_type, *, status, raw):
        self.s.add(
            PaymentLog(
                org_id=uuid.UUID(str(org_id)) if org_id else uuid.UUID(int=0),
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
