# TS-089 — Real provider orders + `payment_intents` + server-side plan/amount binding

**Status:** done
**Requirement:** [R-005 §A–B](../../specs/requirements/R-005-payments-checkout.md)
**Spec(s) updated:** `specs/modules/billing.md`
**Module(s):** `billing`
**Severity / Gate:** P0 · Gate 1

## What this builds

Closes a payment-integrity defect where the plan/amount a customer received
was read from client-influenced provider `notes` instead of a server-side
record. A customer could get `plan="scale"` granted while paying the
`"pro"` price, or have another workspace's id applied to their event.

## Current (the defect)

```python
# backend/app/modules/billing/router.py:34 (before this task)
@router.post("/checkout")
def checkout(body: CheckoutBody, ...):
    notes = {"workspace_id": str(principal.workspace_id), "kind": body.kind}
    if body.plan:
        notes["plan"] = body.plan          # unvalidated, client-chosen
    return {"provider": "razorpay", "notes": notes, ...}
```

```python
# backend/app/modules/billing/service.py:161 (before this task)
elif typ == "subscription.charged" and workspace_id:
    self._workspaces().set_plan(workspace_id, notes.get("plan", "pro"))   # trusts notes
```

## Implementation

```python
# backend/app/modules/billing/models.py
class PaymentIntent(Base, WorkspaceScopedMixin):
    """Server-side record of what was ordered, at what price, for whom. The
    webhook resolves the grant from THIS row, never from provider notes."""
    kind: Mapped[str]                  # paygo | subscription
    plan: Mapped[str | None]
    list_amount_minor: Mapped[int]
    discount_minor: Mapped[int]
    tax_minor: Mapped[int]
    amount_minor: Mapped[int]          # what we actually charge
    coupon_code: Mapped[str | None]    # R-006
    provider_order_id: Mapped[str | None]
    status: Mapped[str]                # created|pending|paid|failed|expired|refunded
    idempotency_key: Mapped[str]
```

```python
# backend/app/modules/billing/plans.py — price from ONE server-side table, nowhere else
PRICES_MINOR = {("paygo", "INR"): 750_000, ("pro", "INR"): 2_499_900, ("scale", "INR"): 7_499_900}
BILLABLE_PLANS = {"paygo", "pro", "scale"}

def price_for(plan: str, currency: str = "INR") -> int:
    try:
        return PRICES_MINOR[(plan, currency)]
    except KeyError:
        raise PaywallError("unknown_plan") from None
```

```python
@router.post("/checkout")
def checkout(body: CheckoutBody, ...):
    plan = "paygo" if body.kind == "paygo" else (body.plan or "")
    if plan not in BILLABLE_PLANS:
        raise HTTPException(400, "unknown_plan")   # the validation that was missing
    return _service(...).create_checkout(principal.workspace_id, kind=body.kind, plan=plan, ...)

def create_checkout(self, workspace_id, *, kind, plan, ...):
    list_amount = price_for(plan, currency)
    intent = PaymentIntent(workspace_id=..., kind=kind, plan=plan,
                           amount_minor=net + tax, idempotency_key=uuid.uuid4().hex, ...)
    self.s.add(intent); self.s.flush()
    handle = self._provider.create_order(OrderRequest(..., idempotency_key=intent.idempotency_key))
    intent.provider_order_id = handle.order_id
    intent.status = "pending"
    self.s.commit()
```

The provider still receives `notes`, but only as a reference
(`{"intent_id": str(intent.id)}`) — the webhook uses it only to *find* the
intent, never to decide the grant (that's TS-097's `_on_payment_succeeded`).

## Files touched

- `backend/app/modules/billing/{models,plans,router,service}.py`
- `backend/migrations/versions/e18ffec0675e_payment_intents_and_workspace_billing_.py`

## Tests

- `backend/tests/modules/billing/test_service.py::test_checkout_creates_intent`,
  `test_unknown_plan_rejected`

## Acceptance criteria (R-005 §A–B, A1–A4, A9)

- [x] `checkout` rejects any plan not in `BILLABLE_PLANS`.
- [x] Price is looked up server-side from `PRICES_MINOR`, never accepted
      from client input.
- [x] The webhook grants a plan from the stored `PaymentIntent`, never from
      provider `notes`.

## Commit

Predates commit-granular history (PR #10 bulk import).
