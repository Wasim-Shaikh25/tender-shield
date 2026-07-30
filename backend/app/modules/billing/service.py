"""BillingService — metering + webhook truth (Doc §7, §15). Consumes auth's
org-admin capability; never imports auth. The webhook is the only thing that
activates a plan or credits a paid review."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import bind_workspace_context
from app.modules.billing.models import (
    Coupon,
    Invoice,
    PaymentLog,
    PlanHistory,
    UsageEvent,
    WebhookEvent,
)
from app.modules.billing.plans import (
    PAYGO_PRICE_INR_PAISE,
    PLAN_LIMITS,
    SUBSCRIPTION_PRICES,
    Grant,
    PaywallError,
    authorize,
)
from app.modules.billing.webhook import verify_signature, verify_stripe_signature


class BillingService:
    def __init__(self, session: Session, *, workspace_factory=None):
        self.s = session
        self._workspace_factory = workspace_factory

    def _workspaces(self):
        if self._workspace_factory is None:
            raise PaywallError("workspace_unavailable")
        return self._workspace_factory(self.s)

    def _bind_workspace(self, workspace_id):
        """Bind the RLS workspace GUC so webhook writes obey tenant isolation."""
        bind_workspace_context(self.s, workspace_id or uuid.UUID(int=0))

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
        plan = workspace.plan if workspace else "free"
        reviews_this_month = self._month_reviews(workspace_id)
        seats = len(self._workspaces().list_members(workspace_id)) if workspace else 0
        limits = PLAN_LIMITS.get(plan, {})
        return {
            "plan": plan,
            "free_review_used": workspace.free_review_used if workspace else None,
            "reviews_used": reviews_this_month,
            "reviews_limit": limits.get("reviews_month") or limits.get("reviews_total"),
            "seats": seats,
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
        commit: bool = True,
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
        if commit:
            self.s.commit()
        return inv

    # ---- validation helpers -----------------------------------------------
    def _valid_amount(
        self,
        currency: str,
        kind: str,
        plan: str | None,
        amount: int,
        notes: dict | None = None,
    ) -> bool:
        """Return True if the paid amount matches the server-owned price (or coupon discount)."""
        notes = notes or {}
        currency = currency.upper()
        if kind == "paygo":
            expected = PAYGO_PRICE_INR_PAISE
        elif kind == "subscription" and plan:
            expected = SUBSCRIPTION_PRICES.get(currency, {}).get(plan)
        else:
            return True
        if expected is None:
            return True
        coupon_code = notes.get("coupon_code")
        if coupon_code:
            try:
                discounted = self.validate_coupon(coupon_code, expected, currency)
            except ValueError:
                return False
            return amount == discounted
        return amount == expected

    # ---- payment history --------------------------------------------------
    def list_payments(self, workspace_id) -> list[PaymentLog]:
        return list(
            self.s.scalars(
                select(PaymentLog)
                .where(PaymentLog.workspace_id == uuid.UUID(str(workspace_id)))
                .order_by(PaymentLog.at.desc())
            )
        )

    # ---- plan history -----------------------------------------------------
    def list_plan_history(self, workspace_id) -> list[PlanHistory]:
        return list(
            self.s.scalars(
                select(PlanHistory)
                .where(PlanHistory.workspace_id == uuid.UUID(str(workspace_id)))
                .order_by(PlanHistory.created_at.desc())
            )
        )

    def record_plan_change(
        self,
        workspace_id,
        old_plan: str,
        new_plan: str,
        changed_by,
        reason: str | None = None,
        commit: bool = True,
    ) -> PlanHistory:
        entry = PlanHistory(
            workspace_id=uuid.UUID(str(workspace_id)),
            old_plan=old_plan,
            new_plan=new_plan,
            changed_by=uuid.UUID(str(changed_by)) if changed_by else None,
            reason=reason,
        )
        self.s.add(entry)
        if commit:
            self.s.commit()
        return entry

    def set_workspace_plan(
        self,
        workspace_id,
        new_plan: str,
        changed_by,
        reason: str | None = None,
        commit: bool = True,
    ) -> dict:
        """Update the workspace plan and append a plan_history row."""
        ws = self._workspaces().get(workspace_id)
        if ws is None:
            raise PaywallError("no_workspace")
        old_plan = ws.plan
        if old_plan == new_plan:
            return {"plan": new_plan, "previous_plan": old_plan}
        ws.plan = new_plan
        self.record_plan_change(
            workspace_id, old_plan, new_plan, changed_by, reason=reason, commit=False
        )
        if commit:
            self.s.commit()
        return {"plan": new_plan, "previous_plan": old_plan}

    # ---- coupons ----------------------------------------------------------
    def list_coupons(self) -> list[Coupon]:
        return list(self.s.scalars(select(Coupon).order_by(Coupon.created_at.desc())))

    def create_coupon(self, data: dict, created_by=None) -> Coupon:
        coupon = Coupon(
            code=(data["code"]).upper().strip(),
            discount_type=data["discount_type"],
            discount_value=int(data["discount_value"]),
            currency=(data.get("currency") or "INR").upper(),
            max_uses=data.get("max_uses"),
            valid_from=data.get("valid_from"),
            valid_until=data.get("valid_until"),
            active=bool(data.get("active", True)),
            created_by=uuid.UUID(str(created_by)) if created_by else None,
        )
        self.s.add(coupon)
        try:
            self.s.commit()
        except IntegrityError as exc:
            self.s.rollback()
            raise ValueError("coupon_code_exists") from exc
        return coupon

    def get_coupon(self, code: str) -> Coupon | None:
        return self.s.scalar(select(Coupon).where(Coupon.code == code.upper().strip()))

    def delete_coupon(self, code: str) -> None:
        coupon = self.get_coupon(code)
        if coupon is None:
            raise ValueError("no_such_coupon")
        coupon.active = False
        self.s.commit()

    def _validate_coupon(self, coupon: Coupon, amount_minor: int, currency: str) -> int:
        """Validate a coupon and return the discounted amount (no side effects)."""
        if not coupon.active:
            raise ValueError("invalid_coupon")
        now = datetime.now(UTC)
        if coupon.valid_from and now < coupon.valid_from:
            raise ValueError("coupon_not_yet_valid")
        if coupon.valid_until and now > coupon.valid_until:
            raise ValueError("coupon_expired")
        if coupon.max_uses is not None and coupon.uses_count >= coupon.max_uses:
            raise ValueError("coupon_exhausted")
        if coupon.discount_type == "fixed":
            if currency.upper() != (coupon.currency or "INR").upper():
                raise ValueError("coupon_currency_mismatch")
            return max(0, amount_minor - coupon.discount_value)
        if coupon.discount_type == "percent":
            return max(0, int(amount_minor * (1 - coupon.discount_value / 100)))
        raise ValueError("invalid_discount_type")

    def validate_coupon(self, code: str, amount_minor: int, currency: str) -> int:
        """Return discounted amount without consuming a use."""
        coupon = self.get_coupon(code)
        if coupon is None:
            raise ValueError("invalid_coupon")
        return self._validate_coupon(coupon, amount_minor, currency)

    def apply_coupon(self, code: str, amount_minor: int, currency: str) -> tuple[int, Coupon]:
        """Return discounted amount and consume one coupon use."""
        coupon = self.get_coupon(code)
        if coupon is None:
            raise ValueError("invalid_coupon")
        discounted = self._validate_coupon(coupon, amount_minor, currency)
        coupon.uses_count += 1
        self.s.commit()
        return discounted, coupon

    # ---- billing self-service ---------------------------------------------
    def get_billing_settings(self, workspace_id) -> dict:
        return self._workspaces().get_billing_settings(workspace_id)

    def update_billing_settings(self, workspace_id, settings: dict) -> dict:
        ws = self._workspaces().get(workspace_id)
        if ws is None:
            raise PaywallError("no_workspace")
        if ws.country.upper() == "IN":
            gstin = (settings.get("gstin") or "").strip()
            pan = (settings.get("pan") or "").strip()
            if gstin and len(gstin) != 15:
                raise ValueError("invalid_gstin")
            if pan and len(pan) != 10:
                raise ValueError("invalid_pan")
        self._workspaces().set_billing_settings(workspace_id, settings)
        return settings

    def cancel_subscription(self, workspace_id, user_id) -> dict:
        ws = self._workspaces().get(workspace_id)
        if ws is None:
            raise PaywallError("no_workspace")
        old_plan = ws.plan
        if old_plan == "free":
            raise ValueError("already_free")
        ws.plan = "free"
        ws.free_review_used = False
        self.record_plan_change(
            workspace_id,
            old_plan,
            "free",
            user_id,
            reason="subscription_cancelled",
            commit=False,
        )
        self._log(
            workspace_id,
            "internal",
            None,
            "subscription_cancelled",
            status="applied",
            raw={"cancelled_by": str(user_id), "previous_plan": old_plan},
        )
        self.s.commit()
        return {"plan": "free", "previous_plan": old_plan}

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
        self._bind_workspace(workspace_id)

        self._log(
            workspace_id,
            "razorpay",
            event_id,
            evt.get("event", "unknown"),
            status="verified" if verified else "failed",
            raw=evt,
        )
        if not verified:
            self.s.commit()
            return {"ok": False, "reason": "bad_signature"}

        # 2) validate amount against server-owned price table
        typ = evt.get("event")
        amount = _extract_amount(evt)
        currency = _extract_currency(evt)
        kind = notes.get("kind", "paygo")
        plan = notes.get("plan")
        if amount is not None and not self._valid_amount(currency, kind, plan, amount, notes=notes):
            self._log(
                workspace_id,
                "razorpay",
                event_id,
                typ or "unknown",
                status="amount_mismatch",
                raw=evt,
            )
            self.s.commit()
            return {"ok": False, "reason": "amount_mismatch"}

        # 3) idempotency: claim the event marker atomically as part of the effect tx
        if event_id and not self._claim_event_id(workspace_id, event_id, "razorpay"):
            self.s.commit()
            return {"ok": True, "duplicate": True}

        # 4) apply effect
        if typ == "order.paid" and workspace_id:
            self.record_usage(
                workspace_id, "review_paid", ref_id=notes.get("opportunity_id"), commit=False
            )
            if amount:
                self.create_invoice(
                    workspace_id,
                    amount_minor=amount,
                    provider="razorpay",
                    provider_invoice_id=event_id,
                    raw=evt,
                    status="paid",
                    commit=False,
                )
        elif typ == "subscription.charged" and workspace_id:
            self.set_workspace_plan(
                workspace_id,
                notes.get("plan", "pro"),
                changed_by=None,
                reason="razorpay_subscription_charged",
                commit=False,
            )
            if amount:
                self.create_invoice(
                    workspace_id,
                    amount_minor=amount,
                    provider="razorpay",
                    provider_invoice_id=event_id,
                    raw=evt,
                    status="paid",
                    commit=False,
                )
        elif typ == "subscription.activated" and workspace_id:
            self.set_workspace_plan(
                workspace_id,
                notes.get("plan", "pro"),
                changed_by=None,
                reason="razorpay_subscription_activated",
                commit=False,
            )
        elif typ in ("subscription.halted", "subscription.cancelled") and workspace_id:
            self.set_workspace_plan(
                workspace_id,
                "free",
                changed_by=None,
                reason=f"razorpay_{typ.split('.')[-1]}",
                commit=False,
            )

        self.s.commit()
        ws = str(workspace_id) if workspace_id else None
        return {"ok": True, "applied": typ, "workspace_id": ws}

    def process_stripe_webhook(self, raw_body: bytes, signature: str, secret: str) -> dict:
        evt = verify_stripe_signature(raw_body, signature, secret)
        event_id = evt.get("id", "") if isinstance(evt, dict) else ""
        event_type = evt.get("type", "unknown") if isinstance(evt, dict) else "unknown"
        status = "verified" if evt else "failed"
        self._bind_workspace(None)
        self._log(None, "stripe", event_id, event_type, status=status, raw=evt)
        if not evt:
            self.s.commit()
            return {"ok": False, "reason": "bad_signature"}

        data = evt.get("data", {}) if isinstance(evt, dict) else {}
        obj = data.get("object", {}) if isinstance(data, dict) else {}
        metadata = obj.get("metadata", {}) if isinstance(obj, dict) else {}
        workspace_id = metadata.get("workspace_id")
        self._bind_workspace(workspace_id)

        if event_type == "checkout.session.completed" and workspace_id:
            amount = obj.get("amount_total")
            currency = obj.get("currency", "INR").upper()
            kind = metadata.get("kind", "paygo")
            plan = metadata.get("plan")
            if amount is not None and not self._valid_amount(
                currency, kind, plan, int(amount), notes=metadata
            ):
                self._log(
                    workspace_id,
                    "stripe",
                    event_id,
                    event_type,
                    status="amount_mismatch",
                    raw=evt,
                )
                self.s.commit()
                return {"ok": False, "reason": "amount_mismatch"}

            # Idempotency: claim the event marker atomically as part of the effect tx
            if event_id and not self._claim_event_id(workspace_id, event_id, "stripe"):
                self.s.commit()
                return {"ok": True, "duplicate": True}

            if kind == "paygo":
                self.record_usage(
                    workspace_id, "review_paid", ref_id=metadata.get("opportunity_id"), commit=False
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
                        commit=False,
                    )
            elif kind == "subscription":
                self.set_workspace_plan(
                    workspace_id,
                    plan or "pro",
                    changed_by=None,
                    reason="stripe_subscription_checkout",
                    commit=False,
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
                        commit=False,
                    )

        self.s.commit()
        ws = str(workspace_id) if workspace_id else None
        return {"ok": True, "applied": event_type, "workspace_id": ws}

    def _log(self, workspace_id, provider, event_id, event_type, *, status, raw):
        """Append a payment_log row. Callers commit."""
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

    def _claim_event_id(self, workspace_id, event_id: str, provider: str) -> bool:
        """Insert a webhook event idempotency marker; return True if this is a new event.

        Uses a savepoint so an existing event only rolls back the marker insert,
        not the rest of the transaction (e.g. the payment_log row).
        """
        if not event_id:
            return True
        try:
            with self.s.begin_nested():
                self.s.add(
                    WebhookEvent(
                        workspace_id=uuid.UUID(str(workspace_id))
                        if workspace_id
                        else uuid.UUID(int=0),
                        provider=provider,
                        provider_event_id=event_id,
                    )
                )
                self.s.flush()
        except IntegrityError:
            return False
        return True


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


def _extract_currency(evt: dict) -> str:
    """Best-effort currency from a Razorpay payment event; defaults to INR."""
    payload = evt.get("payload", {})
    for wrapper in payload.values():
        entity = wrapper.get("entity", {}) if isinstance(wrapper, dict) else {}
        currency = entity.get("currency")
        if isinstance(currency, str):
            return currency.upper()
    return "INR"



