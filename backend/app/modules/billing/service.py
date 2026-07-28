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
from app.modules.billing.coupons import CouponError, CouponView
from app.modules.billing.coupons import discount_for as coupon_discount_for
from app.modules.billing.coupons import validate as validate_coupon_rules
from app.modules.billing.entitlements import add_month, as_aware_utc, resolve_entitlements
from app.modules.billing.gst import (
    compute_invoice_from_inclusive_total,
    financial_year,
    invoice_number,
    validate_gstin,
)
from app.modules.billing.models import (
    UNATTRIBUTED_WORKSPACE,
    Coupon,
    CouponRedemption,
    Credit,
    Invoice,
    InvoiceSequence,
    PaymentIntent,
    PaymentLog,
    Referral,
    ReferralCode,
    UsageEvent,
    WebhookEvent,
)
from app.modules.billing.pdf import render_invoice_pdf
from app.modules.billing.plans import (
    CURRENCY_BY_COUNTRY,
    OVERAGE_PRICE_INR_PAISE,
    PAYGO_PRICE_INR_PAISE,
    PLAN_LIMITS,
    Grant,
    PaywallError,
    authorize,
    price_for,
)
from app.modules.billing.providers.base import OrderRequest

_REFERRAL_REWARD_MINOR = 250_000  # ₹2,500 each side — R-006 §B.7, pricing placeholder


class BillingService:
    def __init__(
        self, session: Session, *, workspace_factory=None, provider_factory=None, settings=None
    ):
        self.s = session
        self._workspace_factory = workspace_factory
        # Callable[[country: str], PaymentProvider | None] — resolved lazily
        # because create_checkout doesn't know the workspace's country (which
        # picks Razorpay vs Stripe, R-005 §A) until it has already looked the
        # workspace up. Defaults to "no provider configured" everywhere.
        self._provider_factory = provider_factory or (lambda country: None)
        # Seller GST identity (R-007 §B.1) — configuration, not code.
        self._settings = settings

    def _workspaces(self):
        if self._workspace_factory is None:
            raise PaywallError("workspace_unavailable")
        return self._workspace_factory(self.s)

    def _effective_plan_and_status(self, workspace) -> tuple[str, str]:
        """A trial or comp grant is an OVERLAY on the workspace's real
        `plan`/`plan_status`, computed fresh on every read rather than
        mutating stored state — so there is no scheduled job needed to end
        one (R-006 §B.8/B.9). Comp lapsing reverts to the workspace's actual
        stored plan (which the superadmin `set_comp` call itself set — a
        comp doesn't touch `plan` after expiry, it just stops being honored
        here); a trial NEVER touches `plan` at all, it only grants Pro-level
        access on top of "free" while active.
        """
        now = datetime.now(UTC)
        if (
            workspace.billing_provider == "comp"
            and workspace.comp_expires_at is not None
            and now > as_aware_utc(workspace.comp_expires_at)
        ):
            return "free", "active"
        if (
            workspace.plan == "free"
            and workspace.trial_ends_at is not None
            and now < as_aware_utc(workspace.trial_ends_at)
        ):
            return "pro", "trialing"
        return workspace.plan, workspace.plan_status

    def _period(self, workspace) -> tuple[datetime, datetime]:
        """Quota resets on the billing anniversary when a subscription
        exists, not the calendar month (R-009 §B.2) — a customer subscribing
        on the 28th must not get a near-empty first period followed by a
        full reset three days later. The provider's own period (set from the
        subscription payload on activation) is authoritative; calendar month
        is only a fallback for workspaces with no subscription (free/paygo),
        where no anniversary exists.
        """
        if workspace.current_period_start and workspace.current_period_end:
            return (
                as_aware_utc(workspace.current_period_start),
                as_aware_utc(workspace.current_period_end),
            )
        now = datetime.now(UTC)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, add_month(start)

    def _period_reviews(self, workspace_id, start, end) -> int:
        return (
            self.s.scalar(
                select(func.count(UsageEvent.id)).where(
                    UsageEvent.workspace_id == uuid.UUID(str(workspace_id)),
                    UsageEvent.event == "review_started",
                    UsageEvent.created_at >= start,
                    UsageEvent.created_at < end,
                )
            )
            or 0
        )

    def _topups_in_period(self, workspace_id, start, end) -> int:
        """Unused top-ups expire with the period (R-009 §B.4/A4) — granted
        minus refunded, scoped to THIS period only, never carried forward."""
        granted = (
            self.s.scalar(
                select(func.coalesce(func.sum(UsageEvent.qty), 0)).where(
                    UsageEvent.workspace_id == uuid.UUID(str(workspace_id)),
                    UsageEvent.event == "review_topup_granted",
                    UsageEvent.created_at >= start,
                    UsageEvent.created_at < end,
                )
            )
            or 0
        )
        refunded = (
            self.s.scalar(
                select(func.coalesce(func.sum(UsageEvent.qty), 0)).where(
                    UsageEvent.workspace_id == uuid.UUID(str(workspace_id)),
                    UsageEvent.event == "review_topup_refunded",
                    UsageEvent.created_at >= start,
                    UsageEvent.created_at < end,
                )
            )
            or 0
        )
        return max(granted - refunded, 0)

    def entitlements(self, workspace_id, *, seats_used: int = 0):
        """The one object every consumer (auth's seat check, export's
        watermark decision, this service's own metering) asks — a limit
        cannot be enforced in one module and forgotten in another (R-009
        §B.1). `seats_used` is supplied by the caller because billing may
        not query auth's own `workspace_members`/`invitations` tables
        (CLAUDE.md §2)."""
        workspace = self._workspaces().get(workspace_id)
        if workspace is None:
            raise PaywallError("no_workspace")
        effective_plan, effective_status = self._effective_plan_and_status(workspace)
        start, end = self._period(workspace)
        limits = PLAN_LIMITS.get(effective_plan, {})
        return resolve_entitlements(
            plan=effective_plan,
            plan_status=effective_status,
            seats_included=limits.get("seats", 0),
            reviews_included=limits.get("reviews_month"),
            reviews_used=self._period_reviews(workspace_id, start, end),
            reviews_topup=self._topups_in_period(workspace_id, start, end),
            seats_used=seats_used,
            period_start=start,
            period_end=end,
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

    def _has_paid_review(self, workspace_id, opportunity_id) -> bool:
        """Whether THIS opportunity's paygo review has already been paid for
        (the webhook's `_on_payment_succeeded` records a `review_paid` usage
        event with ref_id=opportunity_id on success). Payment is scoped to the
        opportunity it was checked out for — it can't be spent on a different
        one."""
        if opportunity_id is None:
            return False
        return (
            self.s.scalar(
                select(UsageEvent.id)
                .where(
                    UsageEvent.workspace_id == uuid.UUID(str(workspace_id)),
                    UsageEvent.event == "review_paid",
                    UsageEvent.ref_id == uuid.UUID(str(opportunity_id)),
                )
                .limit(1)
            )
            is not None
        )

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
        effective_plan, effective_status = self._effective_plan_and_status(workspace)
        start, end = self._period(workspace)
        grace_expired = bool(
            effective_status == "past_due"
            and workspace.grace_until is not None
            and datetime.now(UTC) > as_aware_utc(workspace.grace_until)
        )
        grant = authorize(
            plan=effective_plan,
            plan_status=effective_status,
            grace_expired=grace_expired,
            free_review_used=workspace.free_review_used,
            reviews_used=self._period_reviews(workspace_id, start, end),
            reviews_topup=self._topups_in_period(workspace_id, start, end),
            opportunity_id=opportunity_id,
        )
        if grant.kind == "free_first_review":
            self._workspaces().mark_free_review_used(workspace_id)
            self.record_usage(workspace_id, "review_started", ref_id=opportunity_id, commit=False)
        elif grant.kind == "plan":
            self.record_usage(workspace_id, "review_started", ref_id=opportunity_id, commit=False)
        elif grant.requires_payment:
            # `authorize()`'s Grant(requires_payment=True) was, until this fix,
            # advisory only — nothing checked it, so a paygo workspace ran
            # unlimited unpaid reviews (found while wiring the checkout UI,
            # R-008/TS-091). Enforced here against the SAME `review_paid`
            # usage event the webhook already writes on payment success —
            # no new table, no new webhook logic.
            if not self._has_paid_review(workspace_id, opportunity_id):
                raise PaywallError(
                    "paygo_payment_required",
                    {
                        "paygo_price_inr_paise": PAYGO_PRICE_INR_PAISE,
                        "opportunity_id": str(opportunity_id) if opportunity_id else None,
                    },
                )
            self.record_usage(workspace_id, "review_started", ref_id=opportunity_id, commit=False)
        self.s.commit()
        return grant

    def export_entitlement(self, workspace_id) -> dict:
        """Whether this workspace's exports carry the free-tier watermark
        (Doc §7, R-004 §B). Free plan → watermarked, always, including
        re-exports of the one free review — the watermark is the ONLY thing
        distinguishing free output from paid output (the free review is
        deliberately a complete review, Doc §706), so it can never be a
        client-controlled choice. Any paid plan → clean. A trialing workspace
        (R-006 §B.8) gets Pro-equivalent entitlements, including no watermark.
        """
        workspace = self._workspaces().get(workspace_id)
        if workspace is None:
            return {"watermark": False}
        effective_plan, _ = self._effective_plan_and_status(workspace)
        return {"watermark": effective_plan == "free"}

    def status(self, workspace_id, *, seats_used: int | None = None) -> dict:
        workspace = self._workspaces().get(workspace_id)
        if workspace is None:
            return {
                "plan": None,
                "plan_status": None,
                "grace_until": None,
                "free_review_used": None,
                "reviews_this_month": 0,
                "reviews_included": None,
                "reviews_topup": 0,
                "seats_included": None,
                "seats_used": seats_used,
                "period_end": None,
            }
        e = self.entitlements(workspace_id, seats_used=seats_used or 0)
        return {
            # e.plan/e.plan_status are the EFFECTIVE values (trial/comp
            # overlay applied, R-006 §B.8/B.9) — not the raw stored columns.
            "plan": e.plan,
            "plan_status": e.plan_status,
            "grace_until": as_aware_utc(workspace.grace_until).isoformat()
            if workspace.grace_until
            else None,
            "free_review_used": workspace.free_review_used,
            # Kept for existing clients — this is `e.reviews_used`, over the
            # billing-anniversary period now, not a hardcoded calendar month
            # (R-009 §B.2). "this_month" is a legacy field name.
            "reviews_this_month": e.reviews_used,
            "reviews_included": e.reviews_included,
            "reviews_topup": e.reviews_topup,
            "seats_included": e.seats_included,
            "seats_used": seats_used,
            "period_end": e.period_end.isoformat(),
        }

    def set_billing_details(
        self,
        workspace_id,
        *,
        legal_name: str | None,
        gstin: str | None,
        billing_address: dict,
        place_of_supply: str | None,
    ) -> None:
        """GSTIN format/checksum validation happens HERE, before delegating
        to `auth.workspace_factory` — `auth` cannot import billing's `gst.py`
        (CLAUDE.md §2), so the write-side capability trusts its caller the
        same way `set_plan`'s caller is trusted (R-007 §A10: an invalid
        GSTIN is rejected at save time, never persisted then discovered wrong
        at invoice issuance)."""
        if gstin and not validate_gstin(gstin):
            raise PaywallError("invalid_gstin")
        self._workspaces().set_billing_details(
            workspace_id,
            legal_name=legal_name,
            gstin=gstin,
            billing_address=billing_address,
            place_of_supply=place_of_supply,
        )

    # ---- checkout: real orders, server-side price/plan binding (R-005 §B) -

    def _coupon_view(self, coupon: Coupon) -> CouponView:
        return CouponView(
            code=coupon.code,
            kind=coupon.kind,
            value=coupon.value,
            currency=coupon.currency,
            applies_to=coupon.applies_to,
            max_redemptions=coupon.max_redemptions,
            max_per_workspace=coupon.max_per_workspace,
            redeemed_count=coupon.redeemed_count,
            valid_from=as_aware_utc(coupon.valid_from) if coupon.valid_from else None,
            valid_until=as_aware_utc(coupon.valid_until) if coupon.valid_until else None,
            active=coupon.active,
        )

    def _workspace_redemption_count(self, coupon_id, workspace_id) -> int:
        return (
            self.s.scalar(
                select(func.count(CouponRedemption.id)).where(
                    CouponRedemption.coupon_id == coupon_id,
                    CouponRedemption.workspace_id == uuid.UUID(str(workspace_id)),
                )
            )
            or 0
        )

    def _is_first_purchase(self, workspace_id) -> bool:
        return (
            self.s.scalar(
                select(Invoice.id).where(
                    Invoice.workspace_id == uuid.UUID(str(workspace_id)),
                    Invoice.doc_type == "invoice",
                    Invoice.status == "paid",
                )
            )
            is None
        )

    def _resolve_coupon(
        self, workspace_id, code: str, *, plan: str, kind: str, currency: str
    ) -> tuple[Coupon, int]:
        """Shared by the quote endpoint and checkout so validation can never
        drift between "what we quoted" and "what we charged" (R-006 §B.1/B.2).
        Returns the Coupon row and its discount in minor units."""
        coupon = self.s.scalar(select(Coupon).where(Coupon.code == code.upper()))
        if coupon is None:
            raise CouponError("coupon_not_found")
        validate_coupon_rules(
            self._coupon_view(coupon),
            plan=plan,
            kind=kind,
            currency=currency,
            now=datetime.now(UTC),
            workspace_redemptions=self._workspace_redemption_count(coupon.id, workspace_id),
            is_first_purchase=self._is_first_purchase(workspace_id),
        )
        list_amount = price_for(plan, currency)
        return coupon, coupon_discount_for(self._coupon_view(coupon), list_amount)

    def validate_coupon(self, workspace_id, code: str, *, plan: str, kind: str) -> dict:
        """`POST /coupons/validate` — a QUOTE, writes nothing (R-006 §B.2).
        Invalid codes return a `{"valid": false, "code_reason": ...}` shape
        rather than raising, so a validation endpoint that 400s on the
        expected path doesn't turn into an enumeration oracle by status code.
        """
        workspace = self._workspaces().get(workspace_id)
        if workspace is None:
            raise PaywallError("no_workspace")
        currency = CURRENCY_BY_COUNTRY.get(workspace.country, "INR")
        try:
            list_amount = price_for(plan, currency)
            coupon, discount_minor = self._resolve_coupon(
                workspace_id, code, plan=plan, kind=kind, currency=currency
            )
        except (CouponError, PaywallError) as exc:
            return {"valid": False, "code_reason": exc.code}
        gst = compute_invoice_from_inclusive_total(
            number="",
            total_minor=list_amount - discount_minor,
            buyer_gstin=workspace.gstin,
            seller_state_code=self._settings.seller_state_code if self._settings else "27",
        )
        return {
            "valid": True,
            "code": coupon.code,
            "kind": coupon.kind,
            "value": coupon.value,
            "list_amount_minor": list_amount,
            "discount_minor": discount_minor,
            "credit_applied_minor": 0,  # informational preview only — see create_checkout
            "tax_minor": (list_amount - discount_minor) - gst.base_minor,
            "total_minor": list_amount - discount_minor,
            "currency": currency,
        }

    def credit_balance(self, workspace_id, currency: str = "INR") -> int:
        """Sum of the ledger, never a mutable column (R-006, same discipline
        as `payment_log`/`usage_events`). `int(...)`: Postgres's SUM() over a
        BigInteger column returns NUMERIC, which psycopg maps to
        `Decimal` — SQLite's SUM returns a plain int, so this silently
        returned a Decimal only under real Postgres, poisoning
        `credit_applied_minor`/`amount_minor` arithmetic downstream with a
        type that `json.dumps` (the order's checkout_payload) can't
        serialize. Found via an e2e run against real Postgres."""
        from sqlalchemy import or_

        return int(
            self.s.scalar(
                select(func.coalesce(func.sum(Credit.amount_minor), 0)).where(
                    Credit.workspace_id == uuid.UUID(str(workspace_id)),
                    Credit.currency == currency,
                    or_(Credit.expires_at.is_(None), Credit.expires_at > func.now()),
                )
            )
            or 0
        )

    def list_credits(self, workspace_id) -> list[Credit]:
        return list(
            self.s.scalars(
                select(Credit)
                .where(Credit.workspace_id == uuid.UUID(str(workspace_id)))
                .order_by(Credit.created_at.desc())
            )
        )

    # ---- referrals (R-006 §B.7) --------------------------------------------

    def record_referral_signup(
        self, referrer_workspace_id, referred_workspace_id, code: str
    ) -> None:
        """Called from `auth.signup` via the `billing.record_referral_signup`
        capability — the self-referral domain check already happened in auth
        (which owns the User/Workspace data needed for it). `referred_
        workspace_id` is unique on `Referral`, so a workspace can only ever
        be referred once; caught, not re-raised, matching this codebase's
        idempotent-insert idiom."""
        try:
            self.s.add(
                Referral(
                    referrer_workspace_id=uuid.UUID(str(referrer_workspace_id)),
                    referred_workspace_id=uuid.UUID(str(referred_workspace_id)),
                    code=code,
                    status="signed_up",
                )
            )
            self.s.commit()
        except IntegrityError:
            self.s.rollback()

    def get_referral(self, workspace_id) -> dict:
        code = self._workspaces().get_or_create_referral_code(workspace_id)
        self._register_referral_code_pointer(workspace_id, code)
        rows = list(
            self.s.scalars(
                select(Referral).where(
                    Referral.referrer_workspace_id == uuid.UUID(str(workspace_id))
                )
            )
        )
        return {
            "code": code,
            "stats": {
                "signed_up": len(rows),
                "rewarded": sum(1 for r in rows if r.status == "rewarded"),
            },
        }

    def _register_referral_code_pointer(self, workspace_id, code: str) -> None:
        """Mirrors the code onto billing's own non-RLS `referral_codes` table
        so a stranger's signup can resolve it (R-006 §B.7 — see the table's
        docstring and this migration's note for why `Workspace.referral_code`
        alone can't serve that lookup). Idempotent: `workspace_id` is unique,
        so a second call for the same workspace (the code never changes once
        generated) is a no-op via the unique-constraint/IntegrityError idiom
        used elsewhere in this module."""
        existing = self.s.scalar(
            select(ReferralCode).where(ReferralCode.workspace_id == uuid.UUID(str(workspace_id)))
        )
        if existing is not None:
            return
        try:
            self.s.add(
                ReferralCode(
                    code=code,
                    workspace_id=uuid.UUID(str(workspace_id)),
                    owner_email_domain=self._workspaces().owner_email_domain(workspace_id),
                )
            )
            self.s.commit()
        except IntegrityError:
            self.s.rollback()

    def resolve_referral_code(self, code: str) -> dict | None:
        """The `billing.resolve_referral_code` capability consumed by auth's
        signup flow — resolves through the non-RLS `referral_codes` table
        precisely because the caller (a person signing up, not yet a member
        of any workspace) cannot see the referrer's RLS-protected `workspaces`
        row (R-006 §B.7)."""
        row = self.s.scalar(select(ReferralCode).where(ReferralCode.code == code.upper()))
        if row is None:
            return None
        return {"workspace_id": row.workspace_id, "owner_email_domain": row.owner_email_domain}

    # ---- superadmin: coupons, credits, comp (R-006 §API) -------------------

    def create_coupon(
        self,
        *,
        code: str,
        kind: str,
        value: int,
        currency: str | None = None,
        applies_to: dict | None = None,
        max_redemptions: int | None = None,
        max_per_workspace: int = 1,
        valid_from=None,
        valid_until=None,
        campaign: str | None = None,
        created_by=None,
    ) -> Coupon:
        coupon = Coupon(
            code=code.upper(),
            kind=kind,
            value=value,
            currency=currency,
            applies_to=applies_to or {},
            max_redemptions=max_redemptions,
            max_per_workspace=max_per_workspace,
            valid_from=valid_from,
            valid_until=valid_until,
            campaign=campaign,
            created_by=uuid.UUID(str(created_by)) if created_by else None,
        )
        self.s.add(coupon)
        self.s.commit()
        return coupon

    def list_coupons(self) -> list[Coupon]:
        return list(self.s.scalars(select(Coupon).order_by(Coupon.created_at.desc())))

    def update_coupon(
        self, code: str, *, active: bool | None = None, max_redemptions: int | None = None
    ) -> Coupon:
        coupon = self.s.scalar(select(Coupon).where(Coupon.code == code.upper()))
        if coupon is None:
            raise PaywallError("coupon_not_found")
        if active is not None:
            coupon.active = active
        if max_redemptions is not None:
            coupon.max_redemptions = max_redemptions
        self.s.commit()
        return coupon

    def grant_credit(
        self,
        workspace_id,
        *,
        amount_minor: int,
        currency: str = "INR",
        reason: str,
        expires_at=None,
    ) -> Credit:
        credit = Credit(
            workspace_id=uuid.UUID(str(workspace_id)),
            amount_minor=amount_minor,
            currency=currency,
            reason=reason,
            expires_at=expires_at,
        )
        self.s.add(credit)
        self.s.commit()
        return credit

    def comp_workspace(self, workspace_id, *, plan: str, expires_at=None) -> None:
        self._workspaces().set_comp(workspace_id, plan=plan, expires_at=expires_at)

    def start_trial(self, workspace_id, *, days: int = 14):
        return self._workspaces().start_trial(workspace_id, days=days)

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
        if kind == "topup":
            # A top-up's plan/price is the workspace's OWN current
            # subscription — never client-selected (R-009 §B.4). Only pro/
            # scale have an overage price; anything else can't buy a top-up.
            plan = workspace.plan
            list_amount = OVERAGE_PRICE_INR_PAISE.get(plan)
            if list_amount is None:
                raise PaywallError("topups_not_available_for_plan")
        else:
            list_amount = price_for(plan, currency)  # raises PaywallError("unknown_plan")

        # Order of operations (R-006 §B.3): list -> discount -> credits -> tax.
        # Discount applies to the base; GST is computed on the discounted
        # amount, which is the legally correct order (tax follows
        # consideration). free_months/free_reviews coupons never reduce
        # price (§B.5) — discount_for() already returns 0 for those kinds.
        discount_minor = 0
        if coupon_code and kind != "topup":  # a top-up isn't a coupon-eligible purchase kind
            _coupon, discount_minor = self._resolve_coupon(
                workspace_id, coupon_code, plan=plan, kind=kind, currency=currency
            )
        after_discount = list_amount - discount_minor
        # Credit is a PREVIEW here (informational + reduces what's charged);
        # the consuming ledger entry is only written on payment SUCCESS
        # (_on_payment_succeeded), matching "quote != redeem" (§B.2) applied
        # to credit consumption too — an abandoned checkout must not burn a
        # balance the customer never actually spent.
        credit_applied_minor = min(self.credit_balance(workspace_id, currency), after_discount)
        amount_minor = after_discount - credit_applied_minor
        # PRICES_MINOR is GST-inclusive (R-007) — tax_minor is the informational
        # breakdown of how much of `amount_minor` is tax, not an addend; the
        # SAME split is used again at invoice issuance (`issue_invoice`) against
        # this exact `amount_minor`, so the two can never diverge.
        tax_minor = 0
        if self._settings is not None and amount_minor > 0:
            gst_preview = compute_invoice_from_inclusive_total(
                number="",
                total_minor=amount_minor,
                buyer_gstin=workspace.gstin,
                seller_state_code=self._settings.seller_state_code,
            )
            tax_minor = amount_minor - gst_preview.base_minor

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
            credit_applied_minor=credit_applied_minor,
            tax_minor=tax_minor,
            amount_minor=amount_minor,
            currency=currency,
            coupon_code=coupon_code.upper() if coupon_code else None,
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

    def get_invoice_pdf(self, workspace_id, invoice_id: int) -> bytes | None:
        """Rendered on demand (see pdf.py's module docstring for why nothing
        is pre-rendered/stored). `Invoice` carries RLS like every other
        workspace-scoped table, but the explicit `workspace_id` filter here
        matches this service's existing double-check convention (e.g.
        `list_invoices`) rather than relying on RLS alone (R-007 §A9)."""
        settings = self._seller_settings()
        inv = self.s.scalar(
            select(Invoice).where(
                Invoice.id == invoice_id, Invoice.workspace_id == uuid.UUID(str(workspace_id))
            )
        )
        if inv is None:
            return None
        return render_invoice_pdf(
            inv,
            seller_legal_name=settings.seller_legal_name,
            seller_address=settings.seller_address,
        )

    def _next_seq(self, fy: str) -> int:
        """Serializes issuance per FY so the sequence advances in the SAME
        transaction as the invoice insert (R-007 §B.3) — a Postgres SEQUENCE
        would leak numbers on a rolled-back transaction, which GST's
        gap-free requirement does not tolerate. A deliberate bottleneck:
        invoice issuance is low-volume and correctness beats throughput here.

        An `pg_advisory_xact_lock` keyed on the FY comes FIRST because
        `SELECT ... FOR UPDATE` alone cannot lock a row that doesn't exist
        yet — the very first invoice of a new financial year has no
        `InvoiceSequence` row to lock, so two concurrent first-issuances
        would both try to INSERT it and one loses to a unique-constraint
        violation (caught by
        test_concurrent_invoice_issuance_produces_no_duplicate_sequence_numbers
        against real Postgres). The advisory lock closes that gap the same
        way `_lock` closes it for the free-review race.
        """
        if self.s.get_bind().dialect.name == "postgresql":
            key = (
                int.from_bytes(hashlib.sha256(f"invoice_seq:{fy}".encode()).digest()[:8], "big")
                & 0x7FFFFFFFFFFFFFFF
            )
            self.s.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})
        row = self.s.execute(
            select(InvoiceSequence).where(InvoiceSequence.fy == fy).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            row = InvoiceSequence(fy=fy, last_seq=0)
            self.s.add(row)
            self.s.flush()
        row.last_seq += 1
        return row.last_seq

    def _seller_settings(self):
        if self._settings is None:
            raise PaywallError("billing_settings_unavailable")
        return self._settings

    def issue_invoice(self, intent: PaymentIntent, event) -> Invoice:
        """Issue a GST invoice on payment success (R-007 §B.4). Tax is
        computed on `intent.amount_minor` — the amount actually charged,
        already GST-inclusive (R-005/R-007: catalog prices include tax, no
        "+ GST" surprise at checkout) — via the SAME
        `compute_invoice_from_inclusive_total` split that produced
        `intent.tax_minor` at checkout, so the invoice's tax lines and the
        charged amount can never diverge (R-007 §B.6's reconciliation check
        is true by construction rather than something to verify after the
        fact).
        """
        settings = self._seller_settings()
        workspace = self._workspaces().get(intent.workspace_id)
        now = datetime.now(UTC)
        fy = financial_year(now)
        seq = self._next_seq(fy)
        gst = compute_invoice_from_inclusive_total(
            number=invoice_number(seq, prefix=settings.invoice_series_prefix, fy=fy),
            total_minor=intent.amount_minor,
            buyer_gstin=workspace.gstin if workspace else None,
            seller_state_code=settings.seller_state_code,
        )
        lines = {line.name: line.amount_minor for line in gst.lines}
        inv = Invoice(
            workspace_id=intent.workspace_id,
            invoice_number=gst.number,
            fy=fy,
            seq=seq,
            base_minor=gst.base_minor,
            cgst_minor=lines.get("CGST", 0),
            sgst_minor=lines.get("SGST", 0),
            igst_minor=lines.get("IGST", 0),
            round_off_minor=gst.round_off_minor,
            total_minor=gst.total_minor,
            currency=intent.currency,
            sac_code=gst.sac,
            seller_gstin=settings.seller_gstin or None,
            buyer_gstin=workspace.gstin if workspace else None,
            buyer_legal_name=(workspace.legal_name or workspace.name) if workspace else None,
            place_of_supply=(
                workspace.place_of_supply or (workspace.gstin[:2] if workspace.gstin else None)
            )
            if workspace
            else None,
            payment_intent_id=intent.id,
            provider=event.provider,
            provider_invoice_id=event.event_id,
            status="paid",
            paid_at=now,
        )
        self.s.add(inv)
        self.s.flush()
        return inv

    def issue_credit_note(self, original: Invoice, *, refund_minor: int, event) -> Invoice:
        """A refund needs a credit note referencing the original invoice, in
        the SAME series (R-007 §B.7) — never a deletion or edit of the paid
        invoice, which is a statutory record. Tax is apportioned at the same
        rate the original invoice charged (a partial refund produces a
        partial credit note, not a full reversal)."""
        settings = self._seller_settings()
        now = datetime.now(UTC)
        fy = financial_year(now)
        seq = self._next_seq(fy)
        # Apportion every line at the original invoice's own rate — refund_minor
        # is itself GST-inclusive, exactly like the original charge.
        gst = compute_invoice_from_inclusive_total(
            number=invoice_number(seq, prefix=settings.invoice_series_prefix, fy=fy),
            total_minor=refund_minor,
            buyer_gstin=original.buyer_gstin,
            seller_state_code=settings.seller_state_code,
        )
        lines = {line.name: line.amount_minor for line in gst.lines}
        note = Invoice(
            workspace_id=original.workspace_id,
            invoice_number=gst.number,
            fy=fy,
            seq=seq,
            doc_type="credit_note",
            original_invoice_id=original.id,
            base_minor=gst.base_minor,
            cgst_minor=lines.get("CGST", 0),
            sgst_minor=lines.get("SGST", 0),
            igst_minor=lines.get("IGST", 0),
            round_off_minor=gst.round_off_minor,
            total_minor=gst.total_minor,
            currency=original.currency,
            sac_code=original.sac_code,
            seller_gstin=original.seller_gstin,
            buyer_gstin=original.buyer_gstin,
            buyer_legal_name=original.buyer_legal_name,
            place_of_supply=original.place_of_supply,
            payment_intent_id=original.payment_intent_id,
            provider=event.provider,
            provider_invoice_id=event.event_id,
            status="issued",
            paid_at=None,
        )
        self.s.add(note)
        self.s.flush()
        return note

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
        if intent.kind == "topup":
            # A top-up credits the CURRENT period's quota (R-009 §B.4) — it
            # never touches workspace.plan; unlike paygo/subscription, this
            # purchase doesn't elect the workspace into a different tier.
            self.record_usage(intent.workspace_id, "review_topup_granted", ref_id=intent.id)
        else:
            # Choosing "pay as you go" is itself a plan election (PLAN_LIMITS
            # models paygo as an ongoing tier, not a one-off top-up) — set
            # here for both kinds, since intent.plan is already "paygo" for a
            # paygo checkout and the chosen tier for a subscription checkout.
            # Without this, workspace.plan never transitions to "paygo" at
            # all, and authorize_review's per-opportunity payment check
            # (requires workspace.plan == "paygo") is unreachable (R-008/TS-091).
            self._workspaces().set_plan(intent.workspace_id, intent.plan)
            if intent.kind == "subscription":
                period_start, period_end = _subscription_period(event.raw)
                self._workspaces().set_plan_status(
                    intent.workspace_id,
                    "active",
                    grace_until=None,
                    period_start=period_start,
                    period_end=period_end,
                    provider_subscription_id=_subscription_id(event.raw),
                )
            else:
                self.record_usage(intent.workspace_id, "review_paid", ref_id=intent.opportunity_id)
        self.issue_invoice(intent, event)
        self._redeem_coupon_if_any(intent)
        self._consume_credit_if_any(intent)
        self._reward_referral_if_qualifying(intent)

    def _redeem_coupon_if_any(self, intent: PaymentIntent) -> None:
        """Written only on payment SUCCESS (R-006 §B.2/B.4). `payment_intent_id`
        is unique on `CouponRedemption`, so a duplicate webhook delivery for
        the same intent hits a unique-constraint violation here — caught, not
        re-raised, the same idempotency idiom as `WebhookEvent` (R-006 §A5).
        Redemption limits are re-checked at this point too (not just at
        quote time), closing the race a concurrent double-checkout could
        otherwise exploit against a `max_redemptions=1` coupon (R-006 §A6).
        """
        if not intent.coupon_code or intent.discount_minor <= 0:
            return
        coupon = self.s.scalar(select(Coupon).where(Coupon.code == intent.coupon_code))
        if coupon is None:
            return
        if coupon.max_redemptions is not None and coupon.redeemed_count >= coupon.max_redemptions:
            return  # exhausted between checkout and payment — charge stands, no redemption recorded
        try:
            self.s.add(
                CouponRedemption(
                    workspace_id=intent.workspace_id,
                    coupon_id=coupon.id,
                    payment_intent_id=intent.id,
                    discount_minor=intent.discount_minor,
                )
            )
            self.s.flush()
        except IntegrityError:
            self.s.rollback()
            return
        coupon.redeemed_count += 1

    def _consume_credit_if_any(self, intent: PaymentIntent) -> None:
        """The debit is written only on payment SUCCESS — an abandoned
        checkout must never burn a balance the customer never spent (R-006
        §B.2/B.3, mirroring the coupon idempotency posture: `ref_id` set to
        the intent id makes a re-run of this handler for the same intent
        detectable, though double-application would additionally require
        the outer webhook/event dedup to have failed first)."""
        if intent.credit_applied_minor <= 0:
            return
        already_consumed = self.s.scalar(
            select(Credit.id).where(
                Credit.workspace_id == intent.workspace_id,
                Credit.reason == "consumed",
                Credit.ref_id == intent.id,
            )
        )
        if already_consumed is not None:
            return
        self.s.add(
            Credit(
                workspace_id=intent.workspace_id,
                amount_minor=-intent.credit_applied_minor,
                currency=intent.currency,
                reason="consumed",
                ref_id=intent.id,
            )
        )

    def _reward_referral_if_qualifying(self, intent: PaymentIntent) -> None:
        """A referred workspace's FIRST paid purchase rewards both sides
        (R-006 §B.7). `status` only ever transitions signed_up -> rewarded
        once, so a second purchase (status already "rewarded") credits
        nobody — the status check IS the idempotency guard, no separate
        dedup key needed."""
        referral = self.s.scalar(
            select(Referral).where(
                Referral.referred_workspace_id == intent.workspace_id,
                Referral.status == "signed_up",
            )
        )
        if referral is None:
            return
        referral.status = "rewarded"
        referral.reward_minor = _REFERRAL_REWARD_MINOR
        # `credits` is WorkspaceScopedMixin/RLS-protected (WITH CHECK), and the
        # session is currently bound to the REFERRED workspace (process_webhook
        # bound it to intent.workspace_id). Writing the referred side's own
        # Credit is fine under that binding; writing the referrer's Credit is
        # a genuine cross-tenant write and needs its own binding, or WITH CHECK
        # rejects it (found via an e2e run against real Postgres with FORCE
        # RLS live — SQLite's RLS no-op let this pass silently in tests).
        self.s.add(
            Credit(
                workspace_id=referral.referred_workspace_id,
                amount_minor=_REFERRAL_REWARD_MINOR,
                currency="INR",
                reason="referral",
                # Referral.id is an int PK, Credit.ref_id is a UUID column
                # (matches PaymentIntent/Invoice's id type elsewhere) — no
                # type-compatible id to store here; reason="referral" +
                # workspace_id + created_at is enough to correlate the two
                # for the stats query in get_referral_stats.
                ref_id=None,
            )
        )
        self.s.flush()
        bind_workspace_context(self.s, referral.referrer_workspace_id)
        self.s.add(
            Credit(
                workspace_id=referral.referrer_workspace_id,
                amount_minor=_REFERRAL_REWARD_MINOR,
                currency="INR",
                reason="referral",
                ref_id=None,
            )
        )
        self.s.flush()
        bind_workspace_context(self.s, referral.referred_workspace_id)

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
        elif intent.kind == "topup":
            # Reverses the SAME period's grant only — `_topups_in_period`
            # nets granted-minus-refunded within the period bounds, so a
            # refund can never claw back a top-up that already expired with
            # a prior period.
            self.record_usage(intent.workspace_id, "review_topup_refunded", ref_id=intent.id)
        else:
            self.record_usage(intent.workspace_id, "review_refunded", ref_id=intent.opportunity_id)
        original = self.s.scalar(
            select(Invoice)
            .where(Invoice.payment_intent_id == intent.id, Invoice.doc_type == "invoice")
            .order_by(Invoice.id.desc())
        )
        if original is not None:
            refund_minor = (
                event.amount_minor if event.amount_minor is not None else intent.amount_minor
            )
            self.issue_credit_note(original, refund_minor=refund_minor, event=event)

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


def _subscription_period(raw_event: dict) -> tuple[datetime | None, datetime | None]:
    """The PROVIDER's period is authoritative, not our arithmetic (R-009
    §B.2) — Razorpay's subscription entity carries `current_start`/
    `current_end` as unix epoch seconds. Absent in a synthetic test payload
    with no `subscription` entity — the workspace then falls back to the
    calendar-month period (`BillingService._period`), same as free/paygo."""
    entity = raw_event.get("payload", {}).get("subscription", {}).get("entity", {})
    start = entity.get("current_start")
    end = entity.get("current_end")
    if start is None or end is None:
        return None, None
    return datetime.fromtimestamp(start, tz=UTC), datetime.fromtimestamp(end, tz=UTC)


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
            "credit_applied": intent.credit_applied_minor,
            "tax": intent.tax_minor,
            "total": intent.amount_minor,
        },
        "checkout": intent.checkout_payload,
    }
