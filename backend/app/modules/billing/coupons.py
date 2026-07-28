"""Coupon validation and discount arithmetic (Doc §7, R-006). Pure: no DB, no
I/O. Money is minor units and every division floors — a rounding drift here
is a reconciliation problem later."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class CouponError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CouponView:
    """Everything validate()/discount_for() need, lifted out of the ORM so
    this file stays pure and independently testable."""

    code: str
    kind: str  # percent | fixed | free_months | free_reviews
    value: int
    currency: str | None
    applies_to: dict
    max_redemptions: int | None
    max_per_workspace: int
    redeemed_count: int
    valid_from: datetime | None
    valid_until: datetime | None
    active: bool


def validate(
    coupon: CouponView,
    *,
    plan: str,
    kind: str,
    currency: str,
    now: datetime,
    workspace_redemptions: int,
    is_first_purchase: bool,
) -> None:
    if not coupon.active:
        raise CouponError("coupon_inactive")
    if coupon.valid_from and now < coupon.valid_from:
        raise CouponError("coupon_not_started")
    if coupon.valid_until and now > coupon.valid_until:
        raise CouponError("coupon_expired")
    if coupon.max_redemptions is not None and coupon.redeemed_count >= coupon.max_redemptions:
        raise CouponError("coupon_exhausted")
    if workspace_redemptions >= coupon.max_per_workspace:
        raise CouponError("coupon_already_used")

    rules = coupon.applies_to or {}
    if (plans := rules.get("plans")) and plan not in plans:
        raise CouponError("coupon_not_applicable")
    if (kinds := rules.get("kinds")) and kind not in kinds:
        raise CouponError("coupon_not_applicable")
    if rules.get("first_purchase_only") and not is_first_purchase:
        raise CouponError("coupon_first_purchase_only")
    if coupon.kind == "fixed" and coupon.currency != currency:
        raise CouponError("coupon_currency_mismatch")
    if coupon.kind not in ("percent", "fixed", "free_months", "free_reviews"):
        raise CouponError("coupon_kind_unknown")


def discount_for(coupon: CouponView, list_amount_minor: int) -> int:
    """Discount in minor units, never exceeding the list price.

    Percent uses floor division so the customer is never charged a fraction
    of a paisa and the discount never rounds up past the price. `free_months`/
    `free_reviews` grant entitlements rather than reduce price (R-006 §B.5) —
    the amount charged and the amount invoiced must stay identical for GST,
    so they contribute zero discount here; the grant itself is applied at
    redemption time by the caller.
    """
    if coupon.kind == "percent":
        return min(list_amount_minor * coupon.value // 100, list_amount_minor)
    if coupon.kind == "fixed":
        return min(coupon.value, list_amount_minor)
    if coupon.kind in ("free_months", "free_reviews"):
        return 0
    raise CouponError("coupon_kind_unknown")
