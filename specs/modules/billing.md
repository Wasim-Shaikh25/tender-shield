# Billing & Metering — Spec

**Status:** implemented — free-tier metering + paywall (pure), Razorpay webhook (HMAC-verified, idempotent, payment_log ledger), plan activation via webhook only; checkout returns a handle (live keys wire in later); GST invoice computation (CGST/SGST vs IGST + sequential numbering) done; Stripe webhook verification and processing implemented (credential-gated); Razorpay/Stripe provider skeletons in place
**Requirement refs:** Doc §7, §15, §16.5
**Task refs:** TS-022, TS-037

## Purpose

Freemium metering (one free full review per org), race-safe plan enforcement,
Razorpay (India) behind a provider abstraction (Stripe joins for GCC/UK), GST
invoicing, and the append-only `payment_log`.

## Public interface

- **Capabilities published:**
  - `billing.service_factory` → `BillingService(session)` with `authorize_review`,
    `record_usage`, `list_invoices`, `create_invoice`, and `checkout`.
  - `billing.record_usage(session, org_id, event, ref_id=None)` — direct capability
    for modules that only need to log usage without pulling in the full service.
  - `billing.metering.authorize_review(org) -> Grant` (legacy alias via service).
  - `billing.provider_factory` → `BillingProvider` with `RazorpayProvider` and
    `StripeProvider` implementations; falls back to the deterministic dev notes
    when no live keys are configured.
- **Events emitted:** `billing.plan_activated`, `billing.payment_applied`,
  `billing.paywall_hit`.
- **API routes:**
  - `GET /api/billing/status` (viewer)
  - `POST /api/billing/checkout` (admin)
  - `POST /api/billing/authorize-review` (estimator)
  - `GET /api/billing/invoices` (viewer)
  - `POST /api/billing/webhooks/razorpay` (unauthenticated, HMAC-verified)
  - `POST /api/billing/webhooks/stripe` (unauthenticated, signature-verified)

## Data owned

`usage_events`, `payment_log` (append-only, from day one), `invoices`, payment
intents, webhook-dedup records, plan state on `orgs`.

## Behavior

- **B1 (metering point):** a review is metered at processing start, not export;
  addendum re-processing on a metered opportunity is free.
- **B2 (race-safe):** authorization under a per-org advisory lock; plan limits
  from Doc §7 table.
- **B3 (webhook = only truth):** client redirects/success handlers activate
  nothing; webhooks are HMAC-verified, idempotent by event id, logged to
  `payment_log` (`received` → `verified` → `applied|failed`) *before* acting.
- **B4 (money):** minor units only; never float.
- **B5 (GST):** Indian payments auto-issue GST invoice (SAC 998313, CGST/SGST vs
  IGST by buyer state, sequential gap-free numbering).
- **B6 (paywall as conversion surface):** `PaywallError` carries `code`
  (`free_exhausted|quota_exhausted|paygo_payment_required`) + upsell payload;
  dismissals logged.
- **B7 (abuse):** one free org per verified phone; disposable-email blocklist;
  free review complete but watermarked.
- **B8 (dunning):** past_due → banner + retries + grace; never delete data on
  non-payment.
- **B9 (provider checkout):** `POST /api/billing/checkout` calls the configured
  `BillingProvider` to create a real order/session when keys are present; in dev
  it returns the deterministic notes object used by manual activation.
- **B10 (no activation on redirect):** client-side success redirects or callbacks
  never change plan state; only verified webhooks do.
- **B11 (server-owned prices):** `POST /api/billing/checkout` ignores any client
  `amount_minor` and uses the server price table (`plans.py`). The webhook rejects
  payments whose amount does not match the expected price for the `kind`/`plan`/`currency`.
- **B12 (webhook atomicity):** the idempotency marker (`WebhookEvent`) is claimed,
  the payment effect is applied, and `payment_log` rows are committed in a single
  transaction. Duplicate events are rejected without side effects.

## Acceptance criteria

- A1: second free review raises `PaywallError(free_exhausted)`; concurrent
  requests can't double-spend the free review (lock test).
- A2: duplicate webhook event id is a no-op; tampered signature → 400 and a
  `webhook_verify_failed` payment_log row.
- A3: nothing activates on the redirect path in integration tests.
- A4: checkout with Razorpay/Stripe keys configured creates a real provider order/session.
- A5: client-provided `amount_minor` is rejected if it does not match the server
  price; webhook processing rejects mismatched amounts before plan activation.
- A6: webhook idempotency marker is claimed atomically within the same transaction
  as the billing effect.

## Out of scope

Stripe live wiring (P2/GCC), admin refund console (Doc §16, P1-admin scope),
annual plans/proration polish.
