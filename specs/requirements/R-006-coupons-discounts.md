# R-006 — Coupons, discounts, referral credits and trials

**Status:** draft
**Severity:** P1 — no discounting mechanism exists; blocks pilot conversions
**Requirement refs:** Doc §0.4, §7, §12.6, §706 (GTM)
**Task refs:** TS-090
**Gap refs:** `docs/GAP_ANALYSIS.md` §2.5
**Specs to update:** `specs/modules/billing.md`

## Purpose

`grep -rni "coupon|discount|promo|referral|trial"` across the repository returns
**zero product hits**. There is no way to give anyone a discount, run a promotion,
credit a referral, or comp a pilot account.

This is not a nice-to-have for this product specifically. Two facts from the
requirement docs make it load-bearing:

- **The Phase-1 exit gate requires 3 paid conversions**
  (`specs/000-product-overview.md` §Phase gates). Design-partner pilots at a
  discount are the normal route to those first three.
- **The GTM is referral-led** — Doc §706 describes contractor WhatsApp groups as
  the distribution channel. A referral motion with no referral credit is a
  referral motion with no incentive.

## Data owned

```python
# backend/app/modules/billing/models.py

class Coupon(Base):
    """Discount definitions. NOT workspace-scoped — a coupon is a global object
    that many workspaces may redeem (restrictions live in the columns below)."""

    __tablename__ = "coupons"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    # Stored uppercase; lookups uppercase the input so codes are case-insensitive.

    kind: Mapped[str] = mapped_column(String, nullable=False)
    # percent | fixed | free_months | free_reviews

    value: Mapped[int] = mapped_column(Integer, nullable=False)
    # percent: 1..100 · fixed: minor units · free_months/free_reviews: a count

    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    # required for kind="fixed"; a fixed ₹ discount cannot apply to a GBP order

    applies_to: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # {"plans": ["pro","scale"], "kinds": ["subscription"], "first_purchase_only": true}

    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_per_workspace: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    redeemed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    campaign: Mapped[str | None] = mapped_column(String, nullable=True)  # attribution
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CouponRedemption(Base, WorkspaceScopedMixin):
    """Append-only redemption ledger — one row per successful application.

    Written only when a payment SUCCEEDS, never at quote time, so an abandoned
    checkout does not burn a redemption (R-006 §B.4).
    """

    _tablename_ = "coupon_redemptions"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    coupon_id: Mapped[int] = mapped_column(_BigId, nullable=False, index=True)
    payment_intent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, unique=True)
    discount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Credit(Base, WorkspaceScopedMixin):
    """Prepaid balance: referral rewards, goodwill, refund-to-credit.

    Consumed before charging a card. Minor units, never float.
    """

    _tablename_ = "credits"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)   # +granted / −consumed
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    reason: Mapped[str] = mapped_column(String, nullable=False)
    # referral | goodwill | refund | promo | pilot
    ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Referral(Base):
    __tablename__ = "referrals"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    referrer_workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    referred_workspace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, unique=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    # pending | signed_up | qualified | rewarded
    reward_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Balance is the sum of the ledger, never a mutable column — same discipline as
`payment_log`:

```python
def credit_balance(self, workspace_id, currency="INR") -> int:
    return self.s.scalar(
        select(func.coalesce(func.sum(Credit.amount_minor), 0)).where(
            Credit.workspace_id == uuid.UUID(str(workspace_id)),
            Credit.currency == currency,
            or_(Credit.expires_at.is_(None), Credit.expires_at > func.now()),
        )
    ) or 0
```

## Discount computation — pure, testable, integer-only

```python
# backend/app/modules/billing/coupons.py

"""Coupon validation and discount arithmetic (Doc §7). Pure: no DB, no I/O.
Money is minor units and every division floors — a rounding drift here is a
reconciliation problem later."""


class CouponError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CouponView:
    """Everything validate() needs, lifted out of the ORM so this stays pure."""
    code: str
    kind: str
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
    coupon: CouponView, *, plan: str, kind: str, currency: str,
    now: datetime, workspace_redemptions: int, is_first_purchase: bool,
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


def discount_for(coupon: CouponView, list_amount_minor: int) -> int:
    """Discount in minor units, never exceeding the list price.

    Percent uses floor division so the customer is never charged a fraction of
    a paisa and the discount never rounds up past the price.
    """
    if coupon.kind == "percent":
        return min(list_amount_minor * coupon.value // 100, list_amount_minor)
    if coupon.kind == "fixed":
        return min(coupon.value, list_amount_minor)
    if coupon.kind in ("free_months", "free_reviews"):
        return 0        # entitlement grants, not price reductions — see §B.5
    raise CouponError("coupon_kind_unknown")
```

## Behavior

- **B1 (server-side only).** Discounts are computed on the server and written to
  `payment_intents.discount_minor` before the provider order is created
  (R-005 §B.2). The client never sends an amount.
- **B2 (quote ≠ redeem).** `POST /billing/coupons/validate` returns a quote and
  writes nothing. Redemption happens in the webhook, on payment success only.
- **B3 (order of operations).** `list → discount → credits → tax`.
  Discount applies to the base; **GST is computed on the discounted amount**
  (R-007), which is the legally correct order — tax follows consideration.
  Credits are applied after discount and before tax, as a payment method.
- **B4 (redemption limits).** `max_redemptions` globally and
  `max_per_workspace` per workspace, both enforced at redemption time under the
  same advisory lock metering uses (R-004 §A.4), so a concurrent double-redeem
  is impossible.
- **B5 (grant coupons).** `free_months` and `free_reviews` do not reduce a price;
  they write entitlement rows (`Credit` for months, `UsageEvent` credits for
  reviews) at redemption. This keeps the amount charged and the amount invoiced
  identical, which matters for GST.
- **B6 (stacking).** One coupon per payment. Credits stack with a coupon.
  Stacking two coupons is out of scope and must be rejected explicitly rather
  than silently ignored.
- **B7 (referrals).** Each workspace gets a referral code. When a referred
  workspace makes its **first paid** purchase, both sides receive credit
  (referrer ₹2,500, referred ₹2,500 — `assumption:`, needs a pricing decision).
  Self-referral is blocked by comparing owner email domain and signup IP.
- **B8 (trials).** A `trial` plan state grants Pro entitlements until
  `trial_ends_at`, with no card required. Expiry downgrades to `free`; it never
  auto-charges. A workspace may hold one trial, ever.
- **B9 (pilot comps).** A superadmin can set a workspace to a paid plan with
  `billing_provider="comp"` and an expiry. Comped workspaces are excluded from
  revenue metrics but counted in usage metrics — otherwise pilots corrupt the
  Phase-1 conversion numbers.
- **B10 (audit).** Every coupon creation, edit, deactivation and redemption is
  written to the audit log with the acting user.

## API

```
POST   /api/billing/coupons/validate      {code, plan, kind} → quote (viewer)
GET    /api/billing/credits                → {balance_minor, currency, entries[]} (viewer)
GET    /api/billing/referral               → {code, url, stats} (admin)

POST   /api/billing/admin/coupons          create (superadmin)
GET    /api/billing/admin/coupons          list + redemption stats (superadmin)
PATCH  /api/billing/admin/coupons/{code}   deactivate / adjust limits (superadmin)
POST   /api/billing/admin/credits          grant goodwill credit (superadmin)
POST   /api/billing/admin/comp             comp a workspace (superadmin)
```

Quote response — the frontend renders this directly (R-008):

```json
{
  "valid": true,
  "code": "PILOT25",
  "kind": "percent",
  "value": 25,
  "list_amount_minor": 2499900,
  "discount_minor": 624975,
  "credit_applied_minor": 0,
  "tax_minor": 337487,
  "total_minor": 2212412,
  "currency": "INR",
  "description": "25% off your first Pro subscription"
}
```

Invalid codes return `200` with `{"valid": false, "code_reason": "coupon_expired"}`
rather than `4xx` — a validation endpoint that 400s on the expected path makes
the UI awkward and turns the endpoint into an enumeration oracle by status code.

Rate-limit `coupons/validate` (10/min per workspace) so codes cannot be guessed
in bulk.

## Acceptance criteria

- **A1** `discount_for(percent 25, 2_499_900) == 624_975`; no float appears in
  the computation.
- **A2** A `fixed` INR coupon against a GBP order raises
  `coupon_currency_mismatch`.
- **A3** A coupon at `max_redemptions` raises `coupon_exhausted`; a workspace at
  `max_per_workspace` raises `coupon_already_used`.
- **A4** `POST /billing/coupons/validate` writes no `coupon_redemptions` row.
- **A5** A completed payment with a coupon writes exactly one redemption row and
  increments `redeemed_count` once, even if the webhook is delivered twice.
- **A6** Two concurrent payments using a coupon with `max_redemptions=1` produce
  exactly one redemption; the other is charged full price or fails cleanly.
- **A7** GST is computed on the **discounted** amount: list 2_499_900, 25% off,
  18% GST → tax 337_487, total 2_212_412.
- **A8** A referred workspace's first paid purchase credits both workspaces once;
  a second purchase credits nobody.
- **A9** Self-referral (same owner email domain) is rejected.
- **A10** A trial workspace has Pro entitlements; after `trial_ends_at` it has
  free entitlements and was never charged.
- **A11** A comped workspace appears in usage metrics and not in revenue metrics.
- **A12** Coupon codes are case-insensitive: `pilot25` resolves `PILOT25`.

## Out of scope

- Automatic promotional campaigns / scheduled price experiments (Phase 3).
- Multi-currency coupon values beyond INR until Stripe lands (R-005).
- Affiliate/partner commission tracking — referrals here are customer-to-customer.

## Assumptions

- `assumption:` Referral reward of ₹2,500 each side is a placeholder pending a
  pricing decision. The mechanism is specified; the number is not.
- `assumption:` One coupon per payment. If stacking is wanted later, the
  redemption ledger already supports it; the validation does not.
