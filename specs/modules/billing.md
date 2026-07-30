# Billing & Metering — Spec

**Status:** implemented — free-tier metering + paywall (pure), Razorpay webhook (HMAC-verified, idempotent, payment_log ledger), plan activation via webhook only; checkout returns a handle (live keys wire in later); GST invoice computation (CGST/SGST vs IGST + sequential numbering) done; Stripe webhook verification and processing implemented (credential-gated); Razorpay/Stripe provider skeletons in place
**Requirement refs:** Doc §7, §15, §16.5
**Task refs:** TS-022, TS-037, TS-172

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
  - `GET /api/billing/settings` (admin)
  - `PUT /api/billing/settings` (admin)
  - `POST /api/billing/cancel` (admin — cancel subscription and downgrade to free)
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
- **B13 (seat limits):** the billing module publishes `billing.seat_limits` from the
  Doc §7 plan table so the auth module can enforce per-workspace seat caps during
  member addition and invitation creation/acceptance.
- **B14 (Stripe redirect URLs):** Stripe checkout uses `TS_APP_URL` for `success_url`
  and `cancel_url`, never hardcoded `example.com`.
- **B15 (Stripe verifier):** Stripe webhook signature verification only treats
  `SignatureVerificationError` and `ValueError` as a bad signature; all other SDK or
  runtime errors propagate so silent failures do not swallow billing outages.
- **B16 (Billing settings):** `GET/PUT /api/billing/settings` lets workspace admins
  store a billing profile (GSTIN, PAN, billing address, state, payment method
  identifier) on the workspace. GSTIN and PAN are validated for Indian workspaces
  (15 and 10 characters respectively); invalid values return `400`.
- **B17 (Subscription cancel):** `POST /api/billing/cancel` allows a workspace admin
  to cancel a paid subscription immediately. The workspace plan is set to `free`,
  `free_review_used` is reset to `false`, and a `billing.subscription_cancelled`
  event is recorded in `payment_log`.

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
- A7: Stripe checkout `success_url`/`cancel_url` are derived from `TS_APP_URL`.
- A8: a malformed Stripe payload or invalid signature returns a 400 without raising,
  but a Stripe SDK outage raises.
- A9: `PUT /api/billing/settings` validates GSTIN length 15 and PAN length 10 for
  Indian workspaces and persists the billing profile.
- A10: `POST /api/billing/cancel` downgrades the workspace to `free`, resets
  `free_review_used`, and writes a `subscription_cancelled` payment log row.

## Out of scope

Stripe live wiring (P2/GCC), admin refund console (Doc §16, P1-admin scope),
annual plans/proration polish.
