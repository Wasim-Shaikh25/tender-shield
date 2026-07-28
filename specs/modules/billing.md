# Billing & Metering — Spec

**Status:** implemented — free-tier metering + paywall now enforced in the
review path itself (not just billing's own status endpoint), race-safe under
real concurrency (Postgres advisory lock, TS-087), free-tier export watermark
applied (TS-088); Razorpay webhook (HMAC-verified, idempotent, payment_log
ledger), plan activation via webhook only; checkout returns a handle (live
keys wire in later); GST invoice computation (CGST/SGST vs IGST + sequential
numbering) computed but not yet wired into real invoices (R-007/TS-096);
Stripe + on-payment invoice issuance are follow-ups
**Requirement refs:** Doc §7, §15, §16.5
**Task refs:** TS-022, TS-087, TS-088

## Purpose

Freemium metering (one free full review per org), race-safe plan enforcement,
Razorpay (India) behind a provider abstraction (Stripe joins for GCC/UK), GST
invoicing, and the append-only `payment_log`.

## Public interface

- **Capabilities published:**
  - `billing.service_factory` → `BillingService(session)` with `authorize_review`,
    `record_usage`, `list_invoices`, `create_invoice`, and `export_entitlement`.
  - `billing.record_usage(session, workspace_id, event, ref_id=None)` — direct
    capability for modules that only need to log usage without pulling in the
    full service.
  - `billing.export_entitlement(session, workspace_id) -> {"watermark": bool}`
    — consumed by `export` (TS-088) to decide the free-tier watermark
    server-side; export never imports billing.
  - `app.core.deps.meter(event)` (not published by billing — lives in
    `app.core.deps` so any module can gate a billable action without importing
    billing) resolves `billing.service_factory` by name and is the actual
    enforcement point: `risk`'s `POST /opportunities/{id}/run` consumes it
    (TS-087). Before TS-087, `authorize_review`'s only caller was billing's own
    `/authorize-review` endpoint — nothing forced a client to call it.
- **Events emitted:** `billing.paywall_hit` (published from `meter()` on every
  402, TS-087). `billing.plan_activated`, `billing.payment_applied` are
  specified but not yet emitted — R-005/TS-089.
- **API routes:**
  - `GET /api/billing/status` (viewer)
  - `POST /api/billing/checkout` (admin)
  - `POST /api/billing/authorize-review` (estimator)
  - `GET /api/billing/invoices` (viewer)
  - `POST /api/billing/webhooks/razorpay` (unauthenticated, HMAC-verified)

## Data owned

`usage_events`, `payment_log` (append-only, from day one), `invoices`, payment
intents, webhook-dedup records, plan state on `orgs`.

## Behavior

- **B1 (metering point, TS-087):** a review is metered at processing start —
  `risk`'s run route, via `meter()` — not export, and not only billing's own
  status endpoint. `authorize_review(workspace_id, opportunity_id=None)`:
  re-processing an already-metered opportunity (`_already_metered`, keyed on a
  `review_started` usage event carrying that `ref_id`) is free, permanently,
  regardless of calendar month — an addendum must never cost a second review.
- **B2 (race-safe, TS-087):** the free-review read-check-write and the lock
  acquisition (`pg_advisory_xact_lock`, no-op on SQLite) happen in ONE
  transaction with a single commit — `WorkspaceAdmin.mark_free_review_used`/
  `set_plan` no longer commit internally, because doing so would release the
  lock before the write it protects. Verified against real, non-superuser
  PostgreSQL with two genuinely concurrent threads
  (`tests/test_billing_race_postgres.py`) — confirmed to actually catch the
  race (fails reliably with the lock removed, passes reliably with it).
- **B3 (webhook = only truth):** client redirects/success handlers activate
  nothing; webhooks are HMAC-verified, idempotent by event id, logged to
  `payment_log` (`received` → `verified` → `applied|failed`) *before* acting.
- **B4 (money):** minor units only; never float.
- **B5 (GST):** Indian payments auto-issue GST invoice (SAC 998313, CGST/SGST vs
  IGST by buyer state, sequential gap-free numbering).
- **B6 (paywall as conversion surface):** `PaywallError` carries `code`
  (`free_exhausted|quota_exhausted|paygo_payment_required`) + upsell payload;
  dismissals logged.
- **B7 (abuse, watermark shipped TS-088):** the free review is complete but
  watermarked — `export_entitlement` decides server-side from
  `Workspace.plan == "free"`, never from client input, and marks the
  *document* only (XLSX header/footer + tinted title cell, DOCX page header,
  PDF diagonal page stamp) — findings, quotes and citations are byte-identical
  between a free and a paid export of the same opportunity (`render.py`'s
  `stamp_line`/`WATERMARK_TEXT`). One free workspace per verified phone;
  disposable-email blocklist are still todo (R-015/TS-099).
- **B8 (dunning):** past_due → banner + retries + grace; never delete data on
  non-payment.

## Acceptance criteria

- A1: second free review (on a NEW opportunity) raises
  `PaywallError(free_exhausted)` from `POST /risk/opportunities/{id}/run`, not
  just from the billing endpoint; no findings are written for the blocked
  opportunity. Concurrent requests can't double-spend the free review
  (`test_billing_race_postgres.py`, real Postgres, two threads).
- A2: duplicate webhook event id is a no-op; tampered signature → 400 and a
  `webhook_verify_failed` payment_log row.
- A3: nothing activates on the redirect path in integration tests.
- A4: re-running risk on an already-metered opportunity succeeds and writes no
  second `review_started` usage event.
- A5: a free-plan export contains the watermark in all rendered locations
  (XLSX header/footer, DOCX page header, PDF page stamp); a paid-plan export
  of the same opportunity does not, and its findings are identical.
- A6: `billing.paywall_hit` fires exactly once per `402`.

## Out of scope

Stripe live wiring (P2/GCC), admin refund console (Doc §16, P1-admin scope),
annual plans/proration polish.
