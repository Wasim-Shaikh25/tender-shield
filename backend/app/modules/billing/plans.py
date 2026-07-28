"""Plan limits + pure paywall logic (Doc §7). No DB, no I/O — testable in
isolation. Money is always in minor units (paise); never float."""

from __future__ import annotations

from dataclasses import dataclass, field

# Doc §7 PLAN_LIMITS. reviews_total = lifetime cap; reviews_month = monthly cap.
PLAN_LIMITS: dict[str, dict] = {
    "free": {"reviews_total": 1, "seats": 2},
    "paygo": {"reviews_total": None, "seats": 3},
    "pro": {"reviews_month": 10, "seats": 10},
    "scale": {"reviews_month": 40, "seats": 25},
}

# Prices in paise (Doc §0.4). Kept here so the paywall can quote an upsell.
PAYGO_PRICE_INR_PAISE = 750_000  # ₹7,500
OVERAGE_PRICE_INR_PAISE = {"pro": 499_900, "scale": 349_900}

# Server-side price table (R-005 §B.2) — the ONLY source of what a plan costs.
# Checkout resolves plan+price from here; client input selects WHICH plan,
# never what it costs. A signed webhook's amount is checked against
# payment_intents.amount_minor (itself derived from this table), never
# trusted from provider `notes`.
PRICES_MINOR: dict[tuple[str, str], int] = {
    ("paygo", "INR"): PAYGO_PRICE_INR_PAISE,
    ("pro", "INR"): 2_499_900,  # ₹24,999 / month
    ("scale", "INR"): 7_499_900,  # ₹74,999 / month
}

BILLABLE_PLANS = frozenset({"paygo", "pro", "scale"})

# assumption: IN -> INR only until Stripe (GCC/UK) lands, TS-037/R-005 out of scope.
CURRENCY_BY_COUNTRY: dict[str, str] = {"IN": "INR"}


def price_for(plan: str, currency: str = "INR") -> int:
    try:
        return PRICES_MINOR[(plan, currency)]
    except KeyError:
        raise PaywallError("unknown_plan") from None


class PaywallError(Exception):
    def __init__(self, code: str, upsell: dict | None = None):
        super().__init__(code)
        self.code = code
        self.upsell = upsell or {}


@dataclass
class Grant:
    kind: str
    watermark: bool = False
    requires_payment: bool = False
    meta: dict = field(default_factory=dict)


_NEXT_PLAN = {"pro": "scale"}


def authorize(
    *,
    plan: str,
    plan_status: str = "active",
    grace_expired: bool = False,
    free_review_used: bool,
    reviews_used: int = 0,
    reviews_topup: int = 0,
    opportunity_id=None,
) -> Grant:
    """Decide whether a review may start (Doc §7, R-009 §B.4). Pure: callers
    supply current usage; this raises PaywallError or returns a Grant.
    Metering happens at processing start, and re-processing addenda is free
    (caller's concern).

    `reviews_used`/`reviews_topup` are counted over the workspace's current
    BILLING PERIOD (the anniversary when a subscription exists, calendar
    month otherwise — resolved by the caller, `BillingService._period`),
    not a hardcoded calendar month. `reviews_included` is looked up from
    `PLAN_LIMITS` here rather than passed in, so there is one place that maps
    a plan name to its quota.

    `opportunity_id` is carried into the free_exhausted upsell (when given)
    purely so the client can check out a paygo payment for THIS opportunity
    directly from the paywall, without a second round trip (R-008/TS-091);
    it plays no role in the authorization decision itself.
    """
    if plan_status == "cancelled":
        # Defensive: `_on_subscription_cancelled` already resets plan to
        # "free" in the same webhook, so this should be unreachable in
        # practice — kept as a belt-and-braces check against any state where
        # plan_status lags plan (R-009 §B.5).
        raise PaywallError("subscription_cancelled", {"plans": ["pro", "scale"]})

    if plan_status == "past_due" and grace_expired:
        # Inside grace, past_due keeps full access (never delete/restrict on
        # non-payment, specs/modules/billing.md B8) — `grace_expired` is only
        # true once the caller's clock has actually passed
        # `workspace.grace_until` (R-009 §A7). Until this check existed, a
        # past_due workspace ran reviews forever regardless of how long ago
        # its grace window closed.
        raise PaywallError("payment_overdue", {"plans": ["pro", "scale"]})

    if plan == "free":
        if free_review_used:
            raise PaywallError(
                "free_exhausted",
                {
                    "paygo_price_inr_paise": PAYGO_PRICE_INR_PAISE,
                    "plans": ["pro"],
                    "opportunity_id": str(opportunity_id) if opportunity_id else None,
                },
            )
        return Grant(kind="free_first_review", watermark=True)

    if plan == "paygo":
        # A paygo review must be paid before processing (checkout → webhook).
        return Grant(kind="paygo", requires_payment=True)

    limits = PLAN_LIMITS.get(plan)
    if not limits or "reviews_month" not in limits:
        raise PaywallError("unknown_plan")
    included = limits["reviews_month"]
    if reviews_used >= included + reviews_topup:
        raise PaywallError(
            "quota_exhausted",
            {
                "topup_price_inr_paise": OVERAGE_PRICE_INR_PAISE.get(plan),
                "next_plan": _NEXT_PLAN.get(plan),
            },
        )
    return Grant(kind="plan")
