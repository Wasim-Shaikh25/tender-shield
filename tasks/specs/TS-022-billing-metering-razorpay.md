# TS-022 — `billing` module: free-tier metering, paywall, Razorpay + webhooks

**Status:** done
**Requirement:** Doc §7, §15, §16.5
**Spec(s) updated:** `specs/modules/billing.md`
**Module(s):** `billing`
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

Race-safe free-tier usage metering, the paywall error a request hits once
the free quota is spent, and Razorpay checkout + webhook handling — with
the webhook as the only billing truth, never the client redirect
(CLAUDE.md §4).

## Implementation

```python
# backend/app/modules/billing/plans.py
def price_for(plan: str, currency: str = "INR") -> int: ...   # minor units (paise)

class PaywallError(Exception): ...

@dataclass
class Grant: ...

def authorize(...) -> Grant:
    """Race-safe: usage increment + entitlement check happen inside one
    DB transaction so concurrent requests can't both slip through the
    free-tier quota."""
```

```python
# backend/app/modules/billing/models.py
class UsageEvent(Base, WorkspaceScopedMixin): ...
class PaymentLog(Base, WorkspaceScopedMixin): ...
class WebhookEvent(Base, WorkspaceScopedMixin): ...
class PaymentIntent(Base): ...
```

Webhook handler (`webhook.py`) is the sole activator of a paid entitlement —
the Razorpay checkout redirect only tells the client "payment submitted,"
never flips `Entitlements` itself (Doc §15).

## Files touched

- `backend/app/modules/billing/{plans,models,webhook,service,router,module}.py`

## Tests

- `backend/tests/modules/billing/test_plans.py`, `test_webhook.py`

## Acceptance criteria

- [x] All money values are stored/computed in minor units (paise), never
      float.
- [x] Free-tier quota enforcement is race-safe under concurrent requests.
- [x] Only the Razorpay webhook activates a paid entitlement; the client
      redirect never does.

## Commit

Predates commit-granular history (PR #10 bulk import).
