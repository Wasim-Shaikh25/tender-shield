# TS-037 — Stripe (GCC/UK) provider + live Razorpay keys behind the billing interface

**Status:** todo (needs creds)
**Requirement:** Doc §7, §15.6
**Spec(s) updated:** `specs/modules/billing.md` (to be updated when built)
**Module(s):** `billing`
**Severity / Gate:** P2 · Phase 1 MVP

## What this builds

A second payment provider (Stripe, for GCC/UK customers) implementing the
same billing interface Razorpay (TS-022) already does, plus switching
Razorpay from test to live keys for production.

## Implementation (reference plan — not yet built; blocked on provider creds)

- `StripeProvider` implementing the same checkout-session-creation +
  webhook-verification shape as the existing Razorpay integration —
  webhook remains the only activator of a paid entitlement (CLAUDE.md §4),
  identically for Stripe.
- Provider selection by billing region/currency at checkout time.
- Live Razorpay keys behind environment config, not a code change.

## Files touched (planned)

- `backend/app/modules/billing/{webhook,service,router,module}.py`
- new `backend/app/modules/billing/stripe_provider.py`

## Tests (planned)

- Stripe webhook signature-verification unit tests with fixture payloads.

## Acceptance criteria

- [ ] A Stripe webhook event activates the paid entitlement the same way
      the Razorpay webhook does; the client redirect never does.
- [ ] Razorpay live keys are configured via environment, not hardcoded.

## Commit

Not yet implemented — blocked on provider credentials.
