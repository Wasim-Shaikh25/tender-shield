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


def authorize(
    *,
    plan: str,
    free_review_used: bool,
    reviews_this_month: int,
    has_topups: bool = False,
) -> Grant:
    """Decide whether a review may start (Doc §7). Pure: callers supply current
    usage; this raises PaywallError or returns a Grant. Metering happens at
    processing start, and re-processing addenda is free (caller's concern)."""
    if plan == "free":
        if free_review_used:
            raise PaywallError(
                "free_exhausted",
                {"paygo_price_inr_paise": PAYGO_PRICE_INR_PAISE, "plans": ["pro"]},
            )
        return Grant(kind="free_first_review", watermark=True)

    if plan == "paygo":
        # A paygo review must be paid before processing (checkout → webhook).
        return Grant(kind="paygo", requires_payment=True)

    limits = PLAN_LIMITS.get(plan)
    if not limits or "reviews_month" not in limits:
        raise PaywallError("unknown_plan")
    if reviews_this_month >= limits["reviews_month"] and not has_topups:
        raise PaywallError(
            "quota_exhausted",
            {"topup_price_inr_paise": OVERAGE_PRICE_INR_PAISE.get(plan)},
        )
    return Grant(kind="plan")
