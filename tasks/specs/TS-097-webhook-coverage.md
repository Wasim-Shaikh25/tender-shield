# TS-097 — Webhook coverage: refunds, failures, disputes, dunning/grace, dedupe

**Status:** done
**Requirement:** [R-005 §C](../../specs/requirements/R-005-payments-checkout.md)
**Spec(s) updated:** `specs/modules/billing.md`
**Module(s):** `billing`
**Severity / Gate:** P1 · Gate 1

## What this builds

Expands webhook handling from 4 event types to full coverage (payment
success/failure, subscription lifecycle, refunds, disputes), fixes an
idempotency hole where events with no provider-assigned id were reprocessed
on every retry, and adds dunning/grace so a failed payment doesn't
instantly downgrade a workspace mid-billing-cycle.

## Current (the defects)

```python
# backend/app/modules/billing/service.py:148 (before this task) — only 4 types handled
if typ == "order.paid" and workspace_id: ...
elif typ == "subscription.charged" and workspace_id: ...
# missing: payment.failed, refund.*, disputes, subscription.past_due, ...
```

```python
# service.py:177 — idempotency hole
if event_id:                                   # events without an id NEVER deduped
    self.s.add(WebhookEvent(..., provider_event_id=event_id))
```

## Implementation

```python
def _dedupe_key(self, event: ProviderEvent, raw_body: bytes) -> str:
    """Falling back to a body hash means a provider that omits an id cannot
    cause double-application."""
    return event.event_id or f"sha256:{hashlib.sha256(raw_body).hexdigest()}"

try:
    self.s.add(WebhookEvent(provider=event.provider, provider_event_id=key, ...))
    self.s.flush()
except IntegrityError:
    self.s.rollback()
    return {"ok": True, "duplicate": True}      # unique index does the dedup work
```

```python
HANDLERS = {
    "payment.succeeded": "_on_payment_succeeded", "payment.failed": "_on_payment_failed",
    "subscription.activated": "_on_subscription_activated", "subscription.past_due": "_on_subscription_past_due",
    "subscription.cancelled": "_on_subscription_cancelled", "refund.processed": "_on_refund",
    "dispute.created": "_on_dispute",
}

def _on_payment_succeeded(self, event) -> None:
    intent = self._intent_for(event)             # by reference_id → payment_intents (TS-089)
    if intent is None:
        self._log_orphan(event); return           # never guess; alert instead
    if intent.amount_minor != event.amount_minor:
        self._log(intent.workspace_id, event, status="amount_mismatch"); return
    intent.status = "paid"
    if intent.kind == "subscription":
        self._workspaces().set_plan(intent.workspace_id, intent.plan)   # from the INTENT
    self._issue_invoice(intent, event)            # R-007
    self._events.publish("billing.payment_applied", {...})
```

```python
GRACE_DAYS = 7

def _on_subscription_past_due(self, event) -> None:
    """Never delete data on non-payment. Downgrade deferred by GRACE_DAYS —
    contractors pay by NEFT on their own cycle; instant downgrade loses
    accounts that would have paid."""
    ws.plan_status = "past_due"
    ws.grace_until = datetime.now(UTC) + timedelta(days=GRACE_DAYS)
```

```python
def _on_refund(self, event) -> None:
    intent = self._intent_for(event)
    intent.status = "refunded"
    self._issue_credit_note(intent, event)        # GST credit note, R-007
    if intent.kind == "subscription":
        self._workspaces().set_plan(intent.workspace_id, "free")
```

Also populates `PaymentLog.amount_minor`/`.currency` (declared but never
populated) and gives billing its own unattributed-workspace sentinel
(`00000000-...-00ff`) instead of sharing `uuid.UUID(int=0)` with auth's
`_NO_WORKSPACE` (R-001 §B.6's collision).

## Files touched

- `backend/app/modules/billing/{service,models}.py`
- `backend/migrations/versions/` (workspace `plan_status`/`grace_until`/
  `current_period_start`/`current_period_end`/`provider_subscription_id`)

## Tests

- `backend/tests/modules/billing/test_webhook.py::test_dedupe_without_event_id`,
  `test_past_due_grace_period`, `test_refund_downgrades_and_credits`

## Acceptance criteria (R-005 §C, A5–A8, A10)

- [x] An event with no provider-assigned id is deduped by body-hash, not
      reprocessed on retry.
- [x] A `past_due` subscription keeps full access until `grace_until`
      passes, then downgrades.
- [x] A refund event issues a credit note and downgrades/records the refund.

## Commit

Predates commit-granular history (PR #10 bulk import).
