# TS-098 — Entitlement service: seats, top-ups, billing-anniversary periods, plan changes

**Status:** done
**Requirement:** [R-009](../../specs/requirements/R-009-plan-entitlements.md)
**Spec(s) updated:** `specs/modules/billing.md`, `specs/modules/auth.md`
**Module(s):** `billing`, `auth`
**Severity / Gate:** P1 · Gate 1

## What this builds

One entitlement object every consumer asks the same question of, so a
limit isn't enforced in one module and forgotten in another: seat limits,
review quotas, storage, and watermark status all resolve from one place.

## Implementation

```python
# backend/app/modules/billing/entitlements.py
@dataclass(frozen=True)
class Entitlements:
    plan: str
    plan_status: str                 # active | trialing | past_due | cancelled
    reviews_included: int | None
    reviews_used: int
    reviews_topup: int
    seats_included: int
    seats_used: int
    storage_bytes: int
    watermark_exports: bool

    @property
    def reviews_remaining(self) -> int | None:
        if self.reviews_included is None: return None
        return max(self.reviews_included + self.reviews_topup - self.reviews_used, 0)

    @property
    def is_entitled(self) -> bool:
        """past_due within grace keeps full access — never delete/restrict
        on non-payment (billing.md B8)."""
        return self.plan_status in ("active", "trialing", "past_due")
```

Published as `billing.entitlements`, consumed by `auth` (seats),
`ingestion` (storage, TS-095), `export` (watermark, TS-088) — none import
`billing` (CLAUDE.md §2).

```python
def _period(self, workspace) -> tuple[datetime, datetime]:
    """Quota resets on the BILLING ANNIVERSARY, not the calendar month —
    subscribing on the 28th must not hand a 3-day first period. Falls back
    to calendar month only for workspaces with no subscription."""
    if workspace.current_period_start and workspace.current_period_end:
        return workspace.current_period_start, workspace.current_period_end
    ...
```

Periods are set from the provider's subscription payload on
`subscription.activated`/`renewed` (TS-097) — the provider's period is
authoritative, not local arithmetic.

```python
# backend/app/modules/auth/service.py — seat enforcement
def _check_seat_available(self, workspace_id) -> None:
    ent = self._entitlements    # registry capability, may be absent
    if ent is None: return      # billing disabled → no seat limit
    if ent(self.s, workspace_id).seats_remaining <= 0:
        raise AuthError("seat_limit_reached")      # → 402, not 403

def seats_used(self, workspace_id) -> int:
    """Counts accepted members AND pending (unexpired) invitations —
    a pending invitation that can't be accepted is a bad experience."""
```

```python
# backend/app/modules/billing/plans.py — top-ups + real authorize() signature
TOPUP_PRICES_MINOR = {"pro": 499_900, "scale": 349_900}   # per extra review

def authorize(*, plan, plan_status, free_review_used, reviews_used, reviews_included, reviews_topup) -> Grant:
    if plan_status == "cancelled":
        raise PaywallError("subscription_cancelled", {...})
    if plan == "free":
        if free_review_used: raise PaywallError("free_exhausted", {...})
        return Grant(kind="free_first_review", watermark=True)
    if reviews_used >= reviews_included + reviews_topup:
        raise PaywallError("quota_exhausted", {"topup_price_inr_paise": TOPUP_PRICES_MINOR.get(plan), ...})
    return Grant(kind="plan")
```

Plan changes: upgrade is immediate (credits unused portion); downgrade/
cancel take effect at `current_period_end` (no proration, entitlements kept
until then); never auto-remove members on downgrade — the downgrade is
blocked with a message naming how many seats must be freed first. Never
delete data on downgrade/cancellation — over-quota resources become
read-only (existing reviews stay readable/exportable, new reviews
paywalled).

## Files touched

- `backend/app/modules/billing/{entitlements,plans,module}.py`
- `backend/app/modules/auth/{service,models}.py` (`seats_used`,
  `_check_seat_available`)

## Tests

- `backend/tests/modules/billing/test_entitlements.py::test_billing_anniversary_period`,
  `test_downgrade_blocked_with_too_many_seats`
- `backend/tests/modules/auth/test_service.py::test_seat_limit_402`

## Acceptance criteria (billing.md A20–A25, auth.md A14)

- [x] Quota resets on the billing anniversary, not the 1st of the calendar
      month, for subscribed workspaces.
- [x] `seat_limit_reached` returns 402 (commercial limit), never 403.
- [x] A downgrade that would leave too few seats is blocked, not silently
      applied by removing members.

## Commit

Predates commit-granular history (PR #10 bulk import).
