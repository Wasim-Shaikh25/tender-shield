# Billing & Metering — Spec

**Status:** implemented — free-tier metering + paywall enforced in the review
path itself (not just billing's own status endpoint), race-safe under real
concurrency (Postgres advisory lock, TS-087), free-tier export watermark
applied (TS-088); real Razorpay orders behind a `PaymentProvider` abstraction
with server-side price/plan binding (R-005 §B, TS-089); webhook resolves the
grant from a `payment_intents` row it looks up by opaque id, never from
provider `notes` (R-005 §B.3); full webhook coverage — payment success
(paygo/subscription-activation/renewal, one amount-checked handler for all
three), failure, past-due/grace (dunning), cancellation, refund — and
event-id-or-body-hash idempotency (R-005 §C, TS-097). Billing UI shipped as a
thin, complete paid path (R-008, TS-091), which also fixed two real backend
bugs (paygo enforcement was computed but never checked; `workspace.plan`
never actually became "paygo"). GST invoicing wired end to end (R-007,
TS-096): tax-correct invoices issued on payment success with gap-free per-FY
numbering, credit notes on refund, GSTIN capture + validation, and an
on-demand PDF route. Stripe (GCC/UK) is a second file behind
`select_provider`, not yet written; coupons/discounts (R-006/TS-090) and
seat/top-up entitlements (R-009/TS-098) remain open.
**Requirement refs:** Doc §7, §15, §15.8, §16.5; R-004, R-005, R-007, R-008
**Task refs:** TS-022, TS-087, TS-088, TS-089, TS-097, TS-091, TS-096

## Purpose

Freemium metering (one free full review per org), race-safe plan enforcement,
real payment orders + webhook-only activation via a provider abstraction
(Razorpay live for India; Stripe joins for GCC/UK by adding a file, not
rewriting `service.py`), GST invoicing, and the append-only `payment_log`.

## Public interface

- **Capabilities published:**
  - `billing.service_factory` → `BillingService(session, workspace_factory,
    provider_factory, settings)` with `authorize_review`, `record_usage`,
    `create_checkout`, `get_intent_status`, `process_webhook`,
    `list_invoices`, `issue_invoice`, `issue_credit_note`, `get_invoice_pdf`,
    `set_billing_details`, `status`, and `export_entitlement`. `settings` is
    new (R-007, TS-096) — GST issuance needs the seller's own GSTIN/state/
    invoice-series config, so the factory now threads `ctx.settings` through
    (only billing's own router does this; `deps.py`'s `meter()` and other
    registry-resolved factories don't touch invoicing and pass no settings).
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
- **Provider abstraction (R-005 §A, TS-089):** `app/modules/billing/providers/`
  — `base.py` defines the `PaymentProvider` Protocol (`create_order`,
  `verify_webhook`, `parse_event`) plus `OrderRequest`/`OrderHandle`/
  `ProviderEvent` dataclasses; `razorpay.py` implements it against the real
  Razorpay Orders API; `select.py`'s `select_provider(settings, country)`
  returns a `RazorpayProvider` for `country == "IN"` when keys are configured,
  else `None` (checkout then returns 503 `payment_provider_unavailable`
  instead of silently issuing a fake order).
- **Events emitted:** `billing.paywall_hit` (published from `meter()` on every
  402, TS-087). `billing.plan_activated`/`billing.payment_applied` as events
  are still not emitted — the webhook handlers apply the grant directly via
  `WorkspaceAdmin`; nothing else currently needs to react to them.
- **API routes:**
  - `GET /api/billing/status` (viewer)
  - `POST /api/billing/checkout` (admin) — body `{kind: paygo|subscription,
    plan?, opportunity_id?}`; price/plan resolved server-side, returns an
    intent id + provider order handle, never activates anything.
  - `GET /api/billing/intents/{intent_id}` (viewer) — polled by the client
    after opening the provider checkout; ownership-checked in application
    code since `PaymentIntent` carries no RLS.
  - `POST /api/billing/authorize-review` (estimator)
  - `GET /api/billing/invoices` (viewer)
  - `GET /api/billing/invoices/{id}/pdf` (viewer) — rendered on demand from
    the `Invoice` row's own snapshotted fields; workspace-scoped, never a
    public URL (R-007 §B.8).
  - `PUT /api/billing/details` (admin) — sets buyer GST identity
    (`legal_name`, `gstin`, `billing_address`, `place_of_supply`); GSTIN
    format/checksum is validated before it's persisted (R-007 §B.1, §A10).
  - `POST /api/billing/webhooks/razorpay` (unauthenticated, HMAC-verified)

## Data owned

`usage_events`, `payment_log` (append-only, from day one), `invoices`
(now GST tax-correct — see B5), `invoice_sequences` (one row per FY, gap-free
numbering), `payment_intents` (checkout orders — see below), `webhook_events`
(dedup records), plan + billing-lifecycle state on `workspaces`
(`plan`, `plan_status`, `grace_until`, `current_period_start`,
`current_period_end`, `provider_subscription_id`), and buyer GST identity on
`workspaces` (`legal_name`, `gstin`, `billing_address`, `place_of_supply`).

`PaymentIntent` is deliberately **not** `WorkspaceScopedMixin`/RLS-protected —
same precedent as `RefreshToken`/`PasswordReset`. The webhook must look the
row up by the opaque `intent_id` in provider `notes` *before* it knows which
workspace it belongs to; RLS would block that exact lookup. Authenticated
routes that read a `PaymentIntent` (`get_intent_status`) do the ownership
check themselves in application code.

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
- **B3 (webhook = only truth, R-005 §B/§C):** client redirects/success
  handlers activate nothing; `create_checkout` creates a `PaymentIntent` row
  and a real provider order but changes no entitlement. `process_webhook`
  verifies the signature, logs to `payment_log` *before* trusting anything
  (`_log` commits internally, binding RLS context to the intent's own
  workspace, or a fixed `UNATTRIBUTED_WORKSPACE` sentinel when the intent
  can't be resolved — an unauthenticated route has no `app.workspace_id`
  bound yet). Idempotency is a unique-constraint insert on
  `event_id or sha256(raw_body)` caught via `IntegrityError`, not
  check-then-act, so a replayed event with no id can't loop forever either.
  The grant is always resolved by looking up the `PaymentIntent` referenced
  by the event, never by trusting amount/plan/workspace fields carried in
  provider `notes` directly — `notes` carries only the opaque `intent_id`
  (R-005 §B.3, the core fix: a client could previously edit `notes.plan`
  client-side before the provider redirect and receive whatever plan they
  asked for). `_on_payment_succeeded` is the single handler for a paygo
  payment, a subscription's first activation, and a renewal charge — all
  three carry an amount to verify against `intent.amount_minor`; a mismatch
  logs `amount_mismatch` and grants nothing (`test_webhook_amount_mismatch_
  grants_nothing`, which caught a real bug where `subscription.activated`
  was a separate handler that skipped this check).
- **B4 (money):** minor units only; never float.
- **B5 (GST, R-007, TS-096):** every successful payment issues a real GST
  invoice via `issue_invoice` — SAC 998313, CGST/SGST (buyer state == seller
  state) vs IGST, gap-free per-FY numbering (`TS/2026-27/000001`, ...), buyer/
  seller identity snapshotted onto the invoice at issuance (never joined from
  `Workspace` at render time, so a later profile change never rewrites an
  issued statutory record). `PRICES_MINOR` is treated as GST-**inclusive**
  (an explicit deviation from the R-007 draft, which assumed tax added on top
  of an exclusive price) — `gst.py`'s `compute_invoice_from_inclusive_total`
  backs the taxable base and tax lines out of the amount actually charged,
  with any ±1 paise rounding residue landing in an explicit `round_off_minor`
  so `base + taxes + round_off == total` always holds exactly. The SAME split
  is computed once at checkout (`create_checkout`'s `tax_minor`, informational
  only — it does not change what's charged) and again at invoice issuance
  against that exact `intent.amount_minor`, so the two can never diverge —
  R-007's own "reconciliation check" is true by construction rather than
  something to verify after the fact. A refund issues a credit note in the
  same series referencing the original invoice, apportioned at the same rate
  (`issue_credit_note`). GSTIN format + checksum is validated before it's
  persisted (`gst.validate_gstin`) — an invalid GSTIN is rejected at save
  time, never discovered wrong at invoice issuance; **the checksum algorithm's
  exact form is unverified against a real GSTN reference vector** (documented
  in `gst.py`'s own docstring — this sandbox has no way to confirm it against
  an authoritative source), so it is self-consistent (catches a
  typo'd/transposed GSTIN reliably) rather than proven correct against real
  registrations — confirm before this gates a live paid checkout. Invoice
  PDFs are rendered **on demand** from the `Invoice` row's own fields, not
  pre-rendered and stored — a deliberate deviation from the R-007 draft's
  `pdf_key`/`Storage` reference, since `billing` may not import
  `ingestion.storage` (CLAUDE.md §2) and there is no cross-module storage
  capability published yet; rendering fresh each request needs nothing new
  and can never drift from the statutory record. Gap-free numbering under
  concurrency needed a `pg_advisory_xact_lock` keyed on the FY *in addition
  to* `SELECT ... FOR UPDATE` — a lock can't protect a row that doesn't exist
  yet, so the very first invoice of a new FY raced two concurrent issuers
  into the same INSERT (caught by
  `test_concurrent_invoice_issuance_produces_no_duplicate_sequence_numbers`
  against real Postgres, sanity-checked both ways: fails reliably without the
  lock, passes reliably with it).
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
- **B8 (dunning, R-005 §C.4, TS-097):** `subscription.halted` → `plan_status =
  "past_due"` + `grace_until = now + 7 days`; plan itself is untouched during
  grace, so the workspace keeps full paid access — contractors often pay by
  NEFT on their own cycle, and an instant downgrade would lose accounts that
  would have paid a few days late. `subscription.cancelled` → plan reset to
  `free`, `plan_status = "cancelled"`. Never delete data on non-payment.
- **B9 (checkout idempotency, R-005 §A.9):** `create_checkout` computes a
  deterministic idempotency key (`workspace:kind:plan:opportunity:30-min-
  bucket`); a retry within the same 30-minute window reopens the existing
  `PaymentIntent`/provider order instead of creating a duplicate charge
  attempt, while a genuinely later purchase gets a fresh key and a fresh
  order.
- **B10 (refunds, R-005 §C.3):** `refund.processed` marks the intent
  `refunded`; a subscription refund downgrades to free/cancelled, a paygo
  refund records a `review_refunded` usage event. GST credit-note issuance on
  refund is not wired yet (follows R-007/TS-096).
- **B11 (paygo enforcement, R-008/TS-091 bugfix):** `authorize_review`
  actually enforces `Grant(requires_payment=True)` now. Until this fix,
  `plans.authorize()`'s paygo branch computed that flag but nothing ever
  read it — found while wiring the checkout UI, a paygo-plan workspace ran
  unlimited unpaid reviews (`test_paygo_workspace_blocked_until_its_own_
  opportunity_is_paid`, `backend/tests/test_paywall_enforcement.py`). The fix
  reuses the existing `review_paid` usage event the webhook already writes
  on payment success (keyed by `ref_id=opportunity_id`) — no new table:
  `BillingService._has_paid_review(workspace_id, opportunity_id)` checks for
  one before granting, and `POST /checkout` now requires `opportunity_id`
  for `kind="paygo"` (400 `opportunity_id_required` otherwise) since payment
  is scoped to the one opportunity it unlocks and can't be spent on another.
- **B12 (paygo is a plan election, R-008/TS-091 bugfix):** nothing ever set
  `workspace.plan = "paygo"`, which made B11's enforcement branch
  unreachable in practice — `_on_payment_succeeded` only called `set_plan`
  for `kind == "subscription"`. Fixed by calling `set_plan(intent.plan)` for
  every successful payment, not only subscriptions (`intent.plan` is already
  `"paygo"` for a paygo checkout, so this is a one-line unification, not a
  new branch). The free_exhausted upsell now also carries the blocked
  opportunity's id (`plans.authorize()`'s new `opportunity_id` param) so the
  paywall can check out that exact opportunity's paygo payment directly —
  paying elects the workspace into the paygo plan AND unlocks the paid-for
  opportunity in one webhook
  (`test_free_exhausted_workspace_can_pay_per_tender_from_the_paywall`).

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
- A7 (R-005): `POST /checkout` never accepts a client-supplied price — price is
  always looked up server-side from `PRICES_MINOR` by `(plan, currency)`; an
  unknown plan raises `PaywallError("unknown_plan")` (400), a workspace with
  no configured provider for its country raises
  `PaywallError("payment_provider_unavailable")` (503).
- A8 (R-005): a webhook event whose amount doesn't match its intent's
  `amount_minor` grants nothing and marks the intent `amount_mismatch`, for
  every payment-success event type (`order.paid`, `subscription.charged`,
  `subscription.activated`) — not just the ones an earlier draft happened to
  check.
- A9 (R-005): a duplicate webhook (same `event_id`, or same raw body when no
  `event_id` is present) is a no-op the second time, verified against real,
  non-superuser PostgreSQL with FORCE RLS live (webhook RLS binding via
  `bind_workspace_context` before any query, since this is an unauthenticated
  route that never calls `authenticate()`).
- A10 (R-005): a checkout retry within the 30-minute idempotency window
  returns the same `PaymentIntent`/order, not a new one.
- A11 (R-005): `GET /intents/{id}` returns `{"status": "not_found"}` for an
  intent belonging to a different workspace, even though `PaymentIntent` has
  no RLS to enforce that automatically.
- A12 (R-008/TS-091 bugfix): a paygo-plan workspace is blocked with
  `paygo_payment_required` on an unpaid opportunity's review-run, and paying
  for one opportunity does not unlock a different one.
- A13 (R-008/TS-091 bugfix): a free-plan workspace that hits `free_exhausted`
  can pay per-tender for the exact blocked opportunity from the paywall in
  one checkout, which also elects the workspace into the paygo plan.
- A14 (R-007): buyer GSTIN state `29`, seller state `27` -> IGST only,
  CGST/SGST zero; matching state on both sides -> CGST+SGST split evenly,
  IGST zero.
- A15 (R-007): `base_minor + cgst_minor + sgst_minor + igst_minor +
  round_off_minor == total_minor` for 1,000 randomly generated inclusive
  totals across both intra- and inter-state buyers (property test,
  `test_inclusive_split_reconstructs_exactly_property`).
- A16 (R-007): invoice numbers within one financial year are consecutive
  with no gaps, including under real concurrent issuance (Postgres,
  two threads).
- A17 (R-007): a refund issues a credit note whose `original_invoice_id`
  points at the paid invoice and whose `total_minor` equals the refunded
  amount.
- A18 (R-007): `GET /invoices/{id}/pdf` for another workspace's invoice
  returns 404; for the owning workspace it returns a `%PDF`-prefixed body.
- A19 (R-007): `PUT /billing/details` with a GSTIN whose checksum doesn't
  self-validate returns 400 `invalid_gstin` and persists nothing.

## Out of scope

Stripe live wiring (P2/GCC), admin refund console (Doc §16, P1-admin scope),
annual plans/proration polish, coupons/discounts/credits/referrals
(R-006/TS-090, next), seat/top-up entitlements (R-009/TS-098, next),
GSTR-1 filing exports, e-invoicing/IRN registration, TDS/TCS handling
(R-007 explicitly defers these), and requiring a GSTIN-or-explicit-
unregistered declaration before checkout (R-007 §B.9) — a B2C invoice with no
GSTIN is already valid per the edge-case table, so this gate is a UX nicety
deferred rather than a correctness gap.
