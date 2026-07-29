# R-005 — Payments: real orders, server-side price binding, full webhook coverage

**Status:** draft
**Severity:** P0 — no payment path exists; the webhook trusts client-supplied plan data
**Requirement refs:** Doc §7, §15, §16.5
**Task refs:** TS-089 (orders + binding), TS-097 (webhook coverage)
**Task files:** code-level detail (current-vs-target snippets, file:line, files touched, tests) now lives per-task, split out by TS-126's restructure: [TS-089](../../tasks/specs/TS-089-payment-intents-server-binding.md), [TS-097](../../tasks/specs/TS-097-webhook-coverage.md). This document stays the business/behavior-level record (purpose, target behavior, acceptance criteria).

**Gap refs:** `docs/GAP_ANALYSIS.md` §2.3, §2.4, §2.7, §2.8
**Specs to update:** `specs/modules/billing.md`

## Purpose

`POST /billing/checkout` returns a `notes` dict and no order, so nothing can be
paid. When a real integration is added, the webhook as written would grant plans
based on unvalidated client input. This document specifies order creation, the
server-side price/plan binding that must accompany it, and the webhook event
coverage a production billing system needs.

---

## Part A — Provider abstraction

`specs/000-product-overview.md` promises "Razorpay (IN) + Stripe (GCC/UK) behind
one interface". There is no interface — `BillingService` is Razorpay-specific
end to end, and `stripe` appears once, in a column comment. Define the seam now,
even while only Razorpay is implemented, or the Stripe work becomes a rewrite.

```python
# backend/app/modules/billing/providers/base.py

from typing import Protocol


@dataclass(frozen=True)
class OrderRequest:
    workspace_id: str
    amount_minor: int          # after discount (R-006); minor units always
    currency: str              # INR | AED | GBP
    kind: str                  # paygo | subscription
    plan: str | None
    opportunity_id: str | None
    idempotency_key: str


@dataclass(frozen=True)
class OrderHandle:
    provider: str
    order_id: str              # provider's id — what the client SDK opens
    amount_minor: int
    currency: str
    checkout_payload: dict     # provider-specific fields the SDK needs


class PaymentProvider(Protocol):
    name: str

    def create_order(self, req: OrderRequest) -> OrderHandle: ...
    def create_subscription(self, req: OrderRequest) -> OrderHandle: ...
    def verify_webhook(self, raw_body: bytes, headers: dict) -> bool: ...
    def parse_event(self, raw_body: bytes) -> "ProviderEvent": ...
    def refund(self, payment_id: str, amount_minor: int) -> dict: ...
```

`ProviderEvent` is the normalised shape every provider maps onto, so
`BillingService` never sees a Razorpay payload again:

```python
@dataclass(frozen=True)
class ProviderEvent:
    provider: str
    event_id: str
    type: str                  # normalised: payment.succeeded | subscription.renewed | ...
    amount_minor: int | None
    currency: str | None
    reference_id: str | None   # our payment_intents.id, round-tripped
    raw: dict
```

Selection by workspace country (`Workspace.country`, `auth/models.py:61`):
`IN → razorpay`, everything else → `stripe` when implemented.

---

## Part B — The price/plan binding defect (P0)

### B.1 Current

```python
# backend/app/modules/billing/router.py:34
@router.post("/checkout")
def checkout(body: CheckoutBody, ..., principal = Depends(require("admin"))):
    notes = {"workspace_id": str(principal.workspace_id), "kind": body.kind}
    if body.opportunity_id:
        notes["opportunity_id"] = body.opportunity_id
    if body.plan:
        notes["plan"] = body.plan          # ← unvalidated, client-chosen
    return {"provider": "razorpay", "kind": body.kind, "notes": notes, ...}
```

```python
# backend/app/modules/billing/service.py:161
elif typ == "subscription.charged" and workspace_id:
    self._workspaces().set_plan(workspace_id, notes.get("plan", "pro"))   # ← trusts notes
```

Two failures:

1. **`body.plan` is never validated** against `PLAN_LIMITS`. `plan="scale"` (or
   `plan="enterprise_free"`) passes straight through.
2. **Amount is never bound to plan.** Nothing checks that the money received
   matches the plan granted. A customer who can influence the notes on their own
   order pays for Pro and receives Scale.

`workspace_id` has the same problem: a signed event carrying another workspace's
id would be applied to that workspace.

### B.2 Target — a server-side payment intent

The server records what was ordered, at what price, for whom. The provider
round-trips only an opaque reference. Nothing about the grant is ever read from
client-controlled fields.

```python
# backend/app/modules/billing/models.py

class PaymentIntent(Base, WorkspaceScopedMixin):
    """Server-side record of what was ordered, at what price, for whom.

    The webhook resolves the grant from THIS row, never from provider `notes`
    (R-005 §B.1). Client-supplied fields influence nothing after creation.
    """
    _tablename_ = "payment_intents"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String, nullable=False)            # paygo | subscription
    plan: Mapped[str | None] = mapped_column(String, nullable=True)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    list_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)  # what we charge
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    coupon_code: Mapped[str | None] = mapped_column(String, nullable=True)  # R-006
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="created")
    # created | pending | paid | failed | expired | refunded
    idempotency_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

Price comes from one server-side table and nowhere else:

```python
# backend/app/modules/billing/plans.py

PRICES_MINOR: dict[tuple[str, str], int] = {
    ("paygo", "INR"): 750_000,        # ₹7,500 per tender
    ("pro", "INR"): 2_499_900,        # ₹24,999 / month
    ("scale", "INR"): 7_499_900,      # ₹74,999 / month
}

BILLABLE_PLANS = {"paygo", "pro", "scale"}


def price_for(plan: str, currency: str = "INR") -> int:
    try:
        return PRICES_MINOR[(plan, currency)]
    except KeyError:
        raise PaywallError("unknown_plan") from None
```

Checkout becomes:

```python
@router.post("/checkout")
def checkout(body: CheckoutBody, request: Request, session=Depends(get_session),
             principal=Depends(require("admin"))):
    if body.kind not in ("paygo", "subscription"):
        raise HTTPException(400, "bad_kind")
    plan = "paygo" if body.kind == "paygo" else (body.plan or "")
    if plan not in BILLABLE_PLANS:
        raise HTTPException(400, "unknown_plan")     # ← the validation that is missing today
    return _service(request, session).create_checkout(
        principal.workspace_id,
        kind=body.kind,
        plan=plan,
        opportunity_id=body.opportunity_id,
        coupon_code=body.coupon_code,
    )
```

```python
def create_checkout(self, workspace_id, *, kind, plan, opportunity_id=None, coupon_code=None):
    workspace = self._workspaces().get(workspace_id)
    currency = CURRENCY_BY_COUNTRY.get(workspace.country, "INR")
    list_amount = price_for(plan, currency)
    discount = self._coupons().quote(workspace_id, coupon_code, plan, list_amount) if coupon_code else 0
    net = max(list_amount - discount, 0)
    tax = compute_tax(net, workspace)                      # R-007

    intent = PaymentIntent(
        workspace_id=uuid.UUID(str(workspace_id)),
        kind=kind, plan=plan,
        opportunity_id=uuid.UUID(opportunity_id) if opportunity_id else None,
        list_amount_minor=list_amount, discount_minor=discount,
        tax_minor=tax, amount_minor=net + tax, currency=currency,
        coupon_code=coupon_code, provider=self._provider.name,
        idempotency_key=uuid.uuid4().hex,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    self.s.add(intent)
    self.s.flush()

    handle = self._provider.create_order(OrderRequest(
        workspace_id=str(workspace_id), amount_minor=intent.amount_minor,
        currency=currency, kind=kind, plan=plan,
        opportunity_id=opportunity_id, idempotency_key=intent.idempotency_key,
    ))
    intent.provider_order_id = handle.order_id
    intent.status = "pending"
    self.s.commit()
    return {
        "intent_id": str(intent.id),
        "provider": handle.provider,
        "order_id": handle.order_id,
        "amount_minor": intent.amount_minor,
        "currency": currency,
        "breakdown": {
            "list": list_amount, "discount": discount,
            "tax": tax, "total": intent.amount_minor,
        },
        "checkout": handle.checkout_payload,
    }
```

The provider still receives `notes` — but only as a **reference**, and the
webhook uses it only to *find* the intent, never to decide the grant:

```python
notes = {"intent_id": str(intent.id)}
```

---

## Part C — Webhook coverage

### C.1 Current

```python
# backend/app/modules/billing/service.py:148
typ = evt.get("event")
if typ == "order.paid" and workspace_id: ...
elif typ == "subscription.charged" and workspace_id: ...
elif typ == "subscription.activated" and workspace_id: ...
elif typ in ("subscription.halted", "subscription.cancelled") and workspace_id: ...
```

Four types. Missing: `payment.failed`, `payment.captured`,
`refund.created|processed`, `subscription.pending`, `subscription.completed`,
`subscription.updated`, disputes/chargebacks.

Consequences: no dunning, no grace period (a halted subscription drops straight
to `free` mid-month), no proration, and a refund silently leaves the customer on
a paid plan.

### C.2 Idempotency hole

```python
# service.py:177
if event_id:                                   # ← events without an id are NEVER deduped
    self.s.add(WebhookEvent(..., provider_event_id=event_id))
```

Providers retry. An event with a missing/empty id is reprocessed on every
delivery, producing duplicate invoices and duplicate credits.

```python
def _dedupe_key(self, event: ProviderEvent, raw_body: bytes) -> str:
    """Every event gets a key. Falling back to a body hash means a provider that
    omits an id cannot cause double-application (R-005 §C.2)."""
    return event.event_id or f"sha256:{hashlib.sha256(raw_body).hexdigest()}"
```

Make the ledger insert the concurrency guard rather than a check-then-act:

```python
try:
    self.s.add(WebhookEvent(provider=event.provider, provider_event_id=key, ...))
    self.s.flush()
except IntegrityError:
    self.s.rollback()
    return {"ok": True, "duplicate": True}      # unique index did the work
```

### C.3 Target — normalised handlers

```python
HANDLERS = {
    "payment.succeeded":     "_on_payment_succeeded",
    "payment.failed":        "_on_payment_failed",
    "subscription.activated":"_on_subscription_activated",
    "subscription.renewed":  "_on_subscription_renewed",
    "subscription.past_due": "_on_subscription_past_due",
    "subscription.cancelled":"_on_subscription_cancelled",
    "refund.processed":      "_on_refund",
    "dispute.created":       "_on_dispute",
}


def _on_payment_succeeded(self, event: ProviderEvent) -> None:
    intent = self._intent_for(event)                    # by reference_id → payment_intents
    if intent is None:
        self._log_orphan(event)                          # never guess; alert instead
        return
    if intent.amount_minor != event.amount_minor:
        # Underpayment/overpayment: log, do not grant. This is the check whose
        # absence lets a customer pay for Pro and receive Scale (R-005 §B.1).
        self._log(intent.workspace_id, event, status="amount_mismatch")
        return
    intent.status = "paid"
    if intent.kind == "subscription":
        self._workspaces().set_plan(intent.workspace_id, intent.plan)   # ← from the INTENT
    else:
        self.record_usage(intent.workspace_id, "review_paid", ref_id=intent.opportunity_id)
    self._issue_invoice(intent, event)                   # R-007
    self._redeem_coupon(intent)                          # R-006
    self._events.publish("billing.payment_applied", {...})
```

### C.4 Dunning and grace

```python
GRACE_DAYS = 7


def _on_subscription_past_due(self, event: ProviderEvent) -> None:
    """Never delete data on non-payment (specs/modules/billing.md B8).

    Downgrade is deferred by GRACE_DAYS; during grace the workspace keeps full
    access and the UI shows a banner. Contractors pay by NEFT on their own
    cycle — an instant downgrade loses accounts that would have paid.
    """
    ws = self._workspaces().get(event_workspace)
    ws.plan_status = "past_due"
    ws.grace_until = datetime.now(UTC) + timedelta(days=GRACE_DAYS)
    self._notify_admins(ws, "payment_failed")
```

New columns on `workspaces`: `plan_status` (`active|past_due|cancelled`),
`grace_until`, `current_period_start`, `current_period_end`,
`provider_subscription_id`.

A scheduled job downgrades workspaces whose `grace_until` has passed; entitlement
checks (R-009) treat `past_due` within grace as fully entitled.

### C.5 Refunds

```python
def _on_refund(self, event: ProviderEvent) -> None:
    intent = self._intent_for(event)
    intent.status = "refunded"
    self._issue_credit_note(intent, event)          # GST credit note, R-007
    if intent.kind == "subscription":
        self._workspaces().set_plan(intent.workspace_id, "free")
    else:
        self.record_usage(intent.workspace_id, "review_refunded", ref_id=intent.opportunity_id)
```

An admin refund console is Doc §16 scope; the webhook path must handle
provider-initiated refunds regardless.

### C.6 `payment_log` completeness

`PaymentLog.amount_minor` and `.currency` (`models.py:35`) are declared and never
populated — the "append-only financial ledger" has no amounts in it. Populate
both on every log write, and give billing its own sentinel instead of sharing
`uuid.UUID(int=0)` with auth's `_NO_WORKSPACE`:

```python
UNATTRIBUTED_WORKSPACE = uuid.UUID("00000000-0000-0000-0000-0000000000ff")
```

---

## Behavior

- **B1** Plan and price are resolved server-side from `PRICES_MINOR`; client
  input selects *which* plan, never *what it costs*.
- **B2** Every checkout creates a `payment_intents` row before contacting the
  provider; the provider carries only `intent_id`.
- **B3** The webhook resolves the grant from the intent, never from provider
  `notes`.
- **B4** A payment whose amount ≠ the intent's amount grants nothing and is
  logged `amount_mismatch`.
- **B5** Every webhook event is deduped, including events with no provider id.
- **B6** Signature verification precedes parsing; the raw body is logged before
  any action (Doc §16.5).
- **B7** Past-due subscriptions keep full access for `GRACE_DAYS`; data is never
  deleted for non-payment.
- **B8** Refunds reverse the entitlement and issue a credit note.
- **B9** An intent unpaid at `expires_at` moves to `expired` and grants nothing.
- **B10** Client redirects activate nothing — only the verified webhook does.

## Acceptance criteria

- **A1** `POST /billing/checkout` with `plan="enterprise"` returns
  `400 unknown_plan`.
- **A2** A successful checkout creates one `payment_intents` row with
  `amount_minor == price_for(plan)` and a provider order id.
- **A3** A signed webhook whose amount is less than the intent's leaves the plan
  unchanged and writes a `payment_log` row with `status="amount_mismatch"`.
- **A4** A webhook whose `notes.plan` says `scale` while the intent says `pro`
  grants **pro**.
- **A5** Replaying an identical webhook body with no event id is a no-op the
  second time.
- **A6** A tampered signature returns `400` and writes a `payment_log` row with
  `status="failed"` before rejecting.
- **A7** `subscription.past_due` sets `grace_until` and leaves entitlements
  intact; after grace expires, the workspace is `free`.
- **A8** `refund.processed` sets the intent `refunded`, downgrades the plan and
  creates a credit note.
- **A9** Calling `/billing/checkout` twice with the same idempotency key returns
  the same order id.
- **A10** Every `payment_log` row has non-null `amount_minor` and `currency` when
  the event carried them.

## Out of scope

- Stripe implementation — TS-037, needs credentials. The interface here must
  make it a new file, not a rewrite.
- Admin refund console — Doc §16.
- Annual plans and proration — R-009.

## Assumptions

- `assumption:` Razorpay is the only live provider for v1. `CURRENCY_BY_COUNTRY`
  maps `IN → INR`; GCC/UK rows stay unpriced until Stripe lands.
- `assumption:` A 30-minute intent expiry matches Razorpay's default order
  lifetime.
