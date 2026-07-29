# TS-090 — Coupons, discounts, credits, referrals, trials, pilot comps

**Status:** done
**Requirement:** [R-006](../../specs/requirements/R-006-coupons-discounts.md)
**Spec(s) updated:** `specs/modules/billing.md`
**Module(s):** `billing`, `auth`
**Severity / Gate:** P1 · Gate 1

## What this builds

There was no way to give anyone a discount, run a promotion, credit a
referral, or comp a pilot account — a real gap given the Phase-1 exit gate
requires 3 paid conversions (design-partner pilots at a discount are the
normal route there) and the GTM is referral-led (contractor WhatsApp
groups).

## Data model — shipped differs from the R-doc's original draft

The R-doc's original sketch used `Coupon`/`CouponRedemption`/`Credit`/
`Referral` with a `Referral.status` of 4 states
(`pending|signed_up|qualified|rewarded`). Two real bugs were found by
testing against real Postgres with FORCE RLS (not SQLite, where RLS is a
no-op):

1. **Referral-code resolution needed a third table,
   `ReferralCode(code, workspace_id, owner_email_domain)`, deliberately
   NOT RLS-protected** — a signing-up referred user isn't a member of any
   workspace yet, so the RLS-protected `workspaces` table's compound
   predicate hid the referrer's row from a plain lookup. An earlier version
   silently created zero `Referral` rows and granted zero credits for
   *every* cross-tenant signup.
2. `Referral.status` ships as 2 states (`signed_up | rewarded`), not 4 —
   "qualifying purchase" and "rewarded" collapse into one transition in the
   shipped implementation.

```python
# backend/app/modules/billing/models.py
class Coupon(Base): ...              # NOT workspace-scoped — global, many workspaces redeem
class CouponRedemption(Base, WorkspaceScopedMixin):
    """Append-only. Written only when a payment SUCCEEDS, never at quote
    time, so an abandoned checkout doesn't burn a redemption."""
class Credit(Base, WorkspaceScopedMixin):
    """Prepaid balance ledger. Minor units, never float."""
class Referral(Base): ...
class ReferralCode(Base): ...        # not RLS-protected — see above
```

```python
def credit_balance(self, workspace_id, currency="INR") -> int:
    """Balance is the SUM of the ledger, never a mutable column — same
    discipline as payment_log."""
    return self.s.scalar(select(func.coalesce(func.sum(Credit.amount_minor), 0))
        .where(Credit.workspace_id == ..., or_(Credit.expires_at.is_(None), Credit.expires_at > func.now()))) or 0
```

## Implementation — discount computation (pure, integer-only)

```python
# backend/app/modules/billing/coupons.py
def validate(coupon: CouponView, *, plan, kind, currency, now,
             workspace_redemptions, is_first_purchase) -> None:
    if not coupon.active: raise CouponError("coupon_inactive")
    if coupon.max_redemptions is not None and coupon.redeemed_count >= coupon.max_redemptions:
        raise CouponError("coupon_exhausted")
    if workspace_redemptions >= coupon.max_per_workspace:
        raise CouponError("coupon_already_used")
    ...

def discount_for(coupon: CouponView, list_amount_minor: int) -> int:
    """Floor division — never charges a fraction of a paisa, never rounds
    the discount up past the price."""
    if coupon.kind == "percent":
        return min(list_amount_minor * coupon.value // 100, list_amount_minor)
    if coupon.kind == "fixed":
        return min(coupon.value, list_amount_minor)
    if coupon.kind in ("free_months", "free_reviews"):
        return 0        # entitlement grants, not price reductions
```

Order of operations: `list → discount → credits → tax` — GST is computed
on the *discounted* amount (legally correct: tax follows consideration).
Redemption limits enforced under the same advisory lock TS-087's metering
uses, so concurrent double-redemption is impossible. Self-referral is
blocked by comparing owner email domain (auth owns this comparison; billing
only resolves the code and records the relationship — CLAUDE.md §2).

## Files touched

- `backend/app/modules/billing/{models,coupons,service,router}.py`
- `backend/app/modules/auth/service.py` (self-referral email-domain check,
  `signup`'s referral flow)
- `backend/migrations/versions/21095f7b4b70_coupons_discounts_credits_referrals.py`

## Tests

- `backend/tests/modules/billing/test_coupons.py`,
  `test_service.py::test_referral_credit_real_postgres` (Postgres-only,
  proves the `ReferralCode` fix)

## Acceptance criteria (billing.md A26–A33, auth.md A15–A16)

- [x] A referral signup across two different workspaces correctly creates a
      `Referral` row and grants credit to both sides under real Postgres
      RLS (not just SQLite).
- [x] `discount_for` never produces a discount exceeding the list price or
      a fractional-paisa rounding error.
- [x] Self-referral (same email domain) is rejected.

## Commit

Predates commit-granular history (PR #10 bulk import).
