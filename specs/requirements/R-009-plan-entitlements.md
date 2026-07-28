# R-009 — Plan entitlements: seats, top-ups, billing periods

**Status:** implemented — one `Entitlements` object, billing-anniversary
periods (month-end-safe), seats actually enforced (`auth.seats_used` +
`billing.entitlements`, 402 not 403), top-ups sellable (`authorize()`'s real
signature), a downgrade-vs-seats guard on checkout, and a real
previously-shipped bug fixed in passing: `past_due` outside its grace
window kept full access forever until this task added the `grace_expired`
check. Deferred: true deferred-effect downgrades/cancellations that don't
immediately violate a limit (needs R-016/TS-105's job scheduler), and a
seat-check TOCTOU race (lower severity than the free-review race, not
locked). See `specs/modules/billing.md` B13-B18 and A20-A25, and
`specs/modules/auth.md` B16/A14 for the full account.
**Severity:** P1 — declared limits are unenforced; top-ups are unsellable
**Requirement refs:** Doc §7
**Task refs:** TS-098
**Gap refs:** `docs/GAP_ANALYSIS.md` §2.9
**Specs to update:** `specs/modules/billing.md`, `specs/modules/auth.md`

## Purpose

`PLAN_LIMITS` declares seats and quotas that nothing reads, `authorize()` takes a
`has_topups` parameter no caller ever passes, and monthly quota resets on the
calendar month rather than the billing anniversary. This document turns the
declared plan table into one enforced entitlement service.

## Current

```python
# backend/app/modules/billing/plans.py:9
PLAN_LIMITS: dict[str, dict] = {
    "free":  {"reviews_total": 1,  "seats": 2},
    "paygo": {"reviews_total": None, "seats": 3},
    "pro":   {"reviews_month": 10, "seats": 10},
    "scale": {"reviews_month": 40, "seats": 25},
}
```

```console
$ grep -rn "seats" backend/app
app/modules/billing/plans.py:10-13      # declared, never read
```

```python
# plans.py:41 — has_topups is a parameter with no caller
def authorize(*, plan, free_review_used, reviews_this_month, has_topups: bool = False) -> Grant:
    ...
    if reviews_this_month >= limits["reviews_month"] and not has_topups:
        raise PaywallError("quota_exhausted", {"topup_price_inr_paise": OVERAGE_PRICE_INR_PAISE.get(plan)})
```

The upsell quotes a top-up price for a product that cannot be bought.

```python
# service.py:29 — calendar month, not billing anniversary
start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
```

A customer subscribing on the 28th gets a near-empty first period, then a full
reset three days later.

## Target

### B.1 One entitlement object

Every consumer asks the same question of one place.

```python
# backend/app/modules/billing/entitlements.py

"""Resolved entitlements for a workspace. One object answers every "may they?"
question, so a limit cannot be enforced in one module and forgotten in another
(R-009 §B.1). Pure over inputs the caller supplies."""


@dataclass(frozen=True)
class Entitlements:
    plan: str
    plan_status: str                 # active | trialing | past_due | cancelled
    reviews_included: int | None     # None = not metered by count
    reviews_used: int
    reviews_topup: int
    seats_included: int
    seats_used: int
    storage_bytes: int
    watermark_exports: bool
    period_start: datetime
    period_end: datetime

    @property
    def reviews_remaining(self) -> int | None:
        if self.reviews_included is None:
            return None
        return max(self.reviews_included + self.reviews_topup - self.reviews_used, 0)

    @property
    def seats_remaining(self) -> int:
        return max(self.seats_included - self.seats_used, 0)

    @property
    def is_entitled(self) -> bool:
        """past_due within grace keeps full access — never delete or restrict on
        non-payment (specs/modules/billing.md B8)."""
        return self.plan_status in ("active", "trialing", "past_due")
```

Published as `billing.entitlements` so auth (seats), ingestion (storage) and
export (watermark) all consume the same source without importing billing.

### B.2 Billing periods

```python
# backend/app/modules/auth/models.py — Workspace
plan_status: Mapped[str] = mapped_column(String, nullable=False, default="active")
current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
provider_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)
```

```python
def _period(self, workspace) -> tuple[datetime, datetime]:
    """Quota resets on the billing anniversary, not the calendar month.

    Subscribing on the 28th must not hand the customer a 3-day first period
    (R-009 §B.2). Falls back to the calendar month only for workspaces with no
    subscription (free/paygo), where no anniversary exists.
    """
    if workspace.current_period_start and workspace.current_period_end:
        return workspace.current_period_start, workspace.current_period_end
    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, _add_month(start)
```

Periods are set from the provider's subscription payload on
`subscription.activated` / `subscription.renewed` (R-005 §C.3) — the provider's
period is authoritative, not our arithmetic. Guard month-end rollover
(31 Jan → 28/29 Feb) in `_add_month`.

### B.3 Seat enforcement

Seats are consumed by **accepted** members, not by pending invitations — but an
invitation that cannot be accepted is a bad experience, so check at both points
and count pending invitations toward the total.

```python
# backend/app/modules/auth/service.py

def _check_seat_available(self, workspace_id) -> None:
    ent = self._entitlements                       # registry capability, may be absent
    if ent is None:
        return                                     # billing disabled → no seat limit
    e = ent(self.s, workspace_id)
    if e.seats_remaining <= 0:
        raise AuthError("seat_limit_reached")      # → 402 with upsell, not 403


def seats_used(self, workspace_id) -> int:
    members = self.s.scalar(
        select(func.count()).select_from(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == uuid.UUID(str(workspace_id)))
    ) or 0
    pending = self.s.scalar(
        select(func.count()).select_from(Invitation).where(
            Invitation.workspace_id == uuid.UUID(str(workspace_id)),
            Invitation.used_at.is_(None),
            Invitation.expires_at > func.now(),
        )
    ) or 0
    return members + pending
```

Call `_check_seat_available` in `add_workspace_member`, `create_invitation` and
`accept_invitation`. `seat_limit_reached` returns **402**, not 403 — it is a
commercial limit with an upgrade path, and the frontend renders the same
`<Paywall />` (R-008 §2).

**Downgrade with too many members:** never auto-remove people. Block the
downgrade with a clear message naming how many seats must be freed first.

### B.4 Top-ups

```python
TOPUP_PRICES_MINOR = {"pro": 499_900, "scale": 349_900}   # per extra review
```

A top-up is a paygo-shaped purchase that credits reviews to the current period:

```python
def _topups_in_period(self, workspace_id, start, end) -> int:
    return self.s.scalar(
        select(func.coalesce(func.sum(UsageEvent.qty), 0)).where(
            UsageEvent.workspace_id == uuid.UUID(str(workspace_id)),
            UsageEvent.event == "review_topup_granted",
            UsageEvent.created_at >= start, UsageEvent.created_at < end,
        )
    ) or 0
```

`authorize()` gains the real signature:

```python
def authorize(*, plan, plan_status, free_review_used, reviews_used,
              reviews_included, reviews_topup) -> Grant:
    if plan_status == "cancelled":
        raise PaywallError("subscription_cancelled", {"plans": ["pro", "scale"]})
    if plan == "free":
        if free_review_used:
            raise PaywallError("free_exhausted", {...})
        return Grant(kind="free_first_review", watermark=True)
    if plan == "paygo":
        return Grant(kind="paygo", requires_payment=True)
    if reviews_included is None:
        raise PaywallError("unknown_plan")
    if reviews_used >= reviews_included + reviews_topup:
        raise PaywallError("quota_exhausted", {
            "topup_price_inr_paise": TOPUP_PRICES_MINOR.get(plan),
            "next_plan": {"pro": "scale"}.get(plan),
        })
    return Grant(kind="plan")
```

Unused top-ups expire with the period — state this in the purchase UI, or it
becomes a support burden.

### B.5 Plan changes

| Change | Effective | Proration |
|---|---|---|
| Upgrade (pro → scale) | immediately | credit unused portion of current period |
| Downgrade (scale → pro) | at `current_period_end` | none; keeps entitlements until then |
| Cancel | at `current_period_end` | none; `plan_status="cancelled"`, data retained |
| Free → paid | immediately | none |

Never delete data on downgrade or cancellation. Over-quota resources become
read-only, which for this product means: existing reviews stay readable and
exportable, new reviews are paywalled.

### B.6 The consumer table

| Entitlement | Enforced in | Route |
|---|---|---|
| reviews | `meter()` (R-004 §A.2) | `POST /risk/opportunities/{id}/run` |
| seats | `_check_seat_available` | member add, invitation create/accept |
| storage | `_check_quota` (R-003 §B.3) | `POST /ingestion/.../upload` |
| watermark | `export_entitlement` (R-004 §B.2) | `GET /export/opportunities/{id}` |

Each is a one-line call to `billing.entitlements`. That uniformity is the point —
the current bug class is "limit declared in one place, enforced in none".

## Behavior

- **B1** All limits resolve through one `Entitlements` object.
- **B2** Quota periods follow the billing anniversary when a subscription exists;
  calendar month otherwise.
- **B3** Seats count accepted members plus live pending invitations.
- **B4** Exceeding a commercial limit returns `402` with an upsell payload, never
  `403`.
- **B5** Top-ups credit the current period and expire with it.
- **B6** Upgrades take effect immediately; downgrades and cancellations at period
  end.
- **B7** Data is never deleted for downgrade, cancellation or non-payment.
- **B8** `past_due` within grace retains full entitlements.
- **B9** With billing disabled, all limits are absent and the app still boots.

## Acceptance criteria

- **A1** An 11th member on a `pro` workspace (10 seats) returns `402
  seat_limit_reached`; a pending invitation counts toward the 10.
- **A2** A workspace subscribing on the 28th has `reviews_used == 0` on the 1st
  and its quota resets on the 28th.
- **A3** A `pro` workspace at 10/10 with one top-up may run one more review.
- **A4** Unused top-ups do not carry into the next period.
- **A5** Downgrading `scale`→`pro` with 15 members is blocked with a message
  naming 5 seats to free; no member is removed.
- **A6** A cancelled workspace keeps read access to existing reviews and exports.
- **A7** A `past_due` workspace inside `grace_until` can still run reviews;
  outside it, it cannot.
- **A8** With `TS_ENABLED_MODULES` excluding `billing`, member add and upload
  succeed with no limit.
- **A9** Month-end rollover: a period starting 31 Jan ends 28 Feb (or 29 in a
  leap year), not 3 Mar.

## Out of scope

- Usage-based/metered pricing beyond review counts.
- Enterprise custom contracts (Phase 3).
- Per-seat pricing — seats are plan-bundled in v1.

## Assumptions

- `assumption:` Top-up prices reuse `OVERAGE_PRICE_INR_PAISE` from `plans.py:18`.
- `assumption:` Upgrade proration credits the unused portion. If Razorpay
  subscription proration differs, the provider's calculation wins and ours
  becomes display-only.
