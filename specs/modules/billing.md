# Billing & Metering — Spec

**Status:** implemented — free-tier metering + paywall (pure), Razorpay webhook (HMAC-verified, idempotent, payment_log ledger), plan activation via webhook only; checkout returns a handle (live keys wire in later); Stripe + GST invoice are follow-ups
**Requirement refs:** Doc §7, §15, §16.5
**Task refs:** TS-022

## Purpose

Freemium metering (one free full review per org), race-safe plan enforcement,
Razorpay (India) behind a provider abstraction (Stripe joins for GCC/UK), GST
invoicing, and the append-only `payment_log`.

## Public interface

- **Capabilities published:** `billing.metering.authorize_review(org) -> Grant`
  (raises `PaywallError` with upsell payload), `billing.record_usage(...)`.
- **Events emitted:** `billing.plan_activated`, `billing.payment_applied`,
  `billing.paywall_hit`.
- **API routes:** `/api/billing/checkout`, `/api/billing/status`,
  `/api/billing/webhooks/razorpay` (+ `/stripe` later), invoice list.

## Data owned

`usage_events`, `payment_log` (append-only, from day one), payment intents,
webhook-dedup records, plan state on `orgs`.

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

## Acceptance criteria

- A1: second free review raises `PaywallError(free_exhausted)`; concurrent
  requests can't double-spend the free review (lock test).
- A2: duplicate webhook event id is a no-op; tampered signature → 400 and a
  `webhook_verify_failed` payment_log row.
- A3: nothing activates on the redirect path in integration tests.

## Out of scope

Stripe live wiring (P2/GCC), admin refund console (Doc §16, P1-admin scope),
annual plans/proration polish.
