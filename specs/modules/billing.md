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
on-demand PDF route. Entitlements wired end to end (R-009, TS-098): one
`Entitlements` object resolves reviews/seats/plan-status for every consumer;
seats are actually enforced (previously declared in `PLAN_LIMITS` and never
read); billing-anniversary quota periods (month-end-safe) replace the
hardcoded calendar month; top-ups are sellable (`authorize()`'s `has_topups`
parameter had no caller before this); a `past_due` workspace outside its
grace window is now actually blocked (previously kept full access
indefinitely — found while testing this task). Coupons, discounts, a
prepaid credit ledger, referrals, trials, and superadmin pilot comps are
wired end to end (R-006, TS-090) — this found and fixed a genuine
cross-tenant RLS violation in the referral flow (see B21) and a second,
unrelated `Decimal`-vs-`int` type bug in `credit_balance` that only
manifested under real Postgres (see B20). Stripe (GCC/UK) is a second
file behind `select_provider`, not yet written.
**Requirement refs:** Doc §7, §15, §15.8, §16.5; R-004, R-005, R-006, R-007,
R-008, R-009
**Task refs:** TS-022, TS-087, TS-088, TS-089, TS-097, TS-091, TS-096, TS-098, TS-090

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
  - `billing.entitlements(session, workspace_id, seats_used=0) ->
    Entitlements` (R-009, TS-098) — the one object every consumer asks. Reviews/
    plan/period are billing's own data; `seats_used` is supplied by the
    CALLER (`auth`) because billing may not query auth's own
    `workspace_members`/`invitations` tables (CLAUDE.md §2). Consumed by
    `AuthService._check_seat_available` for seat enforcement.
  - `app.core.deps.meter(event)` (not published by billing — lives in
    `app.core.deps` so any module can gate a billable action without importing
    billing) resolves `billing.service_factory` by name and is the actual
    enforcement point: `risk`'s `POST /opportunities/{id}/run` consumes it
    (TS-087). Before TS-087, `authorize_review`'s only caller was billing's own
    `/authorize-review` endpoint — nothing forced a client to call it.
  - `billing.record_referral_signup(session, referrer_workspace_id,
    referred_workspace_id, code)` (R-006, TS-090) — consumed by
    `AuthService.signup`. Auth does the self-referral domain check itself
    (it owns `User`/`Workspace`) and calls this only to record the
    relationship; billing owns `Referral`/`Credit`.
  - `billing.resolve_referral_code(session, code) -> {"workspace_id",
    "owner_email_domain"} | None` (R-006, TS-090) — consumed by
    `AuthService._apply_referral` to resolve a referral code at signup.
    Resolves through billing's own non-RLS `referral_codes` pointer table,
    **never** a `Workspace.referral_code` query — see B21 for why that
    distinction is load-bearing, not stylistic.
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
  - `GET /api/billing/status` (viewer) — resolves `auth.seats_used` (if auth
    is enabled) and includes it in the response alongside
    `reviews_included`/`reviews_topup`/`seats_included`/`period_end`
    (R-009, TS-098) so the frontend stops duplicating `PLAN_LIMITS`.
  - `POST /api/billing/checkout` (admin) — body `{kind: paygo|subscription|
    topup, plan?, opportunity_id?}`; price/plan resolved server-side, returns
    an intent id + provider order handle, never activates anything. `topup`
    resolves its own price from the workspace's CURRENT plan
    (`OVERAGE_PRICE_INR_PAISE`) — the client cannot name a plan for a
    top-up. A `subscription` checkout that would leave the workspace over
    the new plan's seat limit is rejected with `400 seats_exceed_new_plan`
    (`{"seats_over", "current_seats"}`) — resolved via `auth.seats_used`,
    never auto-removing members (R-009 §B.5/A5).
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
  - `POST /api/billing/coupons/validate` (admin) — body `{code, plan, kind,
    opportunity_id?}`; returns the discount a coupon would apply without
    redeeming it (R-006 §B.2/A6).
  - `GET /api/billing/credits` (viewer) — `{balance_minor, currency, entries}`
    (R-006).
  - `GET /api/billing/referral` (viewer) — `{code, stats: {signed_up,
    rewarded}}`; generates the workspace's code lazily on first call
    (R-006 §B.7).
  - `POST /api/billing/trial/start` (admin) — starts a time-boxed trial;
    `assumption:` this self-serve route isn't named in R-006's own API list,
    added because a trial with no start endpoint is unreachable.
  - `POST /api/billing/admin/coupons`, `GET /api/billing/admin/coupons`,
    `PATCH /api/billing/admin/coupons/{code}` (superadmin) — coupon CRUD.
  - `POST /api/billing/admin/credits` (superadmin) — goodwill/promo credit
    grant.
  - `POST /api/billing/admin/comp` (superadmin) — pilot/goodwill plan comp,
    optionally time-boxed.

## Data owned

`usage_events`, `payment_log` (append-only, from day one), `invoices`
(now GST tax-correct — see B5), `invoice_sequences` (one row per FY, gap-free
numbering), `payment_intents` (checkout orders — see below), `webhook_events`
(dedup records), plan + billing-lifecycle state on `workspaces`
(`plan`, `plan_status`, `grace_until`, `current_period_start`,
`current_period_end`, `provider_subscription_id`), and buyer GST identity on
`workspaces` (`legal_name`, `gstin`, `billing_address`, `place_of_supply`).
`coupons` (global, not workspace-scoped), `coupon_redemptions` (append-only,
`WorkspaceScopedMixin`/RLS), `credits` (append-only ledger,
`WorkspaceScopedMixin`/RLS), `referrals` (one row per referrer→referred
relationship, spans two workspaces — see below), `referral_codes` (see
below), and trial/comp state on `workspaces` (`referral_code`,
`trial_ends_at`, `had_trial`, `comp_expires_at`) (R-006, TS-090).

`PaymentIntent` is deliberately **not** `WorkspaceScopedMixin`/RLS-protected —
same precedent as `RefreshToken`/`PasswordReset`. The webhook must look the
row up by the opaque `intent_id` in provider `notes` *before* it knows which
workspace it belongs to; RLS would block that exact lookup. Authenticated
routes that read a `PaymentIntent` (`get_intent_status`) do the ownership
check themselves in application code.

`Referral` is deliberately **not** `WorkspaceScopedMixin`: a single row is
jointly relevant to TWO workspaces (referrer and referred), so no single
`workspace_id` could be the RLS-scoping key without arbitrarily picking a
side. Both `GET /billing/referral` and the reward-crediting in
`_on_payment_succeeded` query it directly by workspace id in application
code instead.

`ReferralCode` (`code` PK, `workspace_id` unique, `owner_email_domain`) is
deliberately **not** `WorkspaceScopedMixin`/RLS-protected — same precedent as
`PaymentIntent`. A person signing up is not yet a member of ANY workspace, so
they must be able to resolve someone else's referral code; RLS's compound
predicate on `workspaces` would hide the referrer's row from that exact
lookup (see B21). `Workspace.referral_code` (RLS-protected, same value)
remains the referrer's own same-tenant read path for `GET /billing/referral`
— `ReferralCode` exists purely so a stranger can resolve the code
cross-tenant, which `Workspace.referral_code` structurally cannot serve.

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
- **B13 (one entitlement object, R-009 §B.1, TS-098):** `Entitlements`
  (`billing/entitlements.py`, pure) answers every "may they?" question —
  `reviews_remaining`, `seats_remaining`, `is_entitled` — so a limit can't be
  enforced in one module and forgotten in another, which is exactly what had
  happened: `PLAN_LIMITS` declared `seats` for every plan and nothing ever
  read it.
- **B14 (billing-anniversary periods, R-009 §B.2):** `BillingService._period`
  uses `workspace.current_period_start/end` (set from the Razorpay
  subscription entity's `current_start`/`current_end` on
  `subscription.activated`/renewal — the provider's period is authoritative,
  never our arithmetic) when a subscription exists; calendar month is only a
  fallback for free/paygo, where no anniversary exists. `entitlements.
  add_month` is month-end-safe (31 Jan → 28/29 Feb, never 3 Mar).
- **B15 (seats enforced, R-009 §B.3):** `auth.seats_used` (accepted members +
  live pending invitations) feeds `billing.entitlements`; `AuthService.
  _check_seat_available` blocks `add_workspace_member`/`create_invitation`/
  `accept_invitation` at capacity with `402 seat_limit_reached`, never `403`
  — a commercial limit with an upgrade path, not an authorization failure.
- **B16 (top-ups, R-009 §B.4):** `POST /checkout {"kind": "topup"}` resolves
  its price from the workspace's own current plan
  (`OVERAGE_PRICE_INR_PAISE`), never a client-named plan. The webhook credits
  a `review_topup_granted` usage event (never touching `workspace.plan` — a
  top-up is not a plan election, unlike paygo/subscription); a refund credits
  `review_topup_refunded`. `authorize()`'s real signature
  (`reviews_used`/`reviews_topup`, replacing the old `reviews_this_month`/
  `has_topups` — the latter had no caller before this) checks
  `reviews_used >= reviews_included + reviews_topup`.
  `BillingService._topups_in_period` nets granted-minus-refunded **within the
  current period's bounds only** — a top-up bought in an earlier period is
  never visible in a later one, so unused top-ups expire with the period
  they were bought in.
- **B17 (past_due outside grace is blocked, R-009 §B.8/A7, bugfix):**
  `authorize()` gained a `grace_expired` param — before this, a `past_due`
  workspace kept full access indefinitely regardless of how long ago its
  `grace_until` had passed, because nothing ever compared "now" against it.
  `BillingService.authorize_review` computes `grace_expired` and raises
  `payment_overdue` when true. Caught a second, unrelated bug while adding
  this: SQLite returns naive datetimes even for `DateTime(timezone=True)`
  columns (Postgres preserves tzinfo), which crashed the very first
  aware-vs-naive comparison (`entitlements.as_aware_utc` fixes this, and also
  fixes `status()`'s `grace_until`/`period_end` ISO serialization, which had
  the same latent bug since TS-097 shipped it — untested because no prior
  test compared the exact serialized string).
- **B18 (downgrade guard, R-009 §B.5/A5):** a `subscription` checkout to a
  plan with fewer seats than the workspace currently uses is rejected
  (`400 seats_exceed_new_plan`) rather than silently over-committing seats or
  auto-removing members. True deferred effects for downgrades/cancellations
  (R-009 §B.5's "takes effect at period end" for plans that DON'T immediately
  violate a limit) are explicitly deferred — there is no scheduled-job system
  yet (that's R-016/TS-105) to apply a delayed change, and building an inert
  "pending plan change" field with nothing to ever act on it isn't worth
  shipping.
- **B19 (coupons/discounts, R-006 §B.1-B.6, TS-090):** `coupons.py` (pure) is
  the discount math — `validate()` raises `CouponError` for currency
  mismatch, exhaustion (`max_redemptions`), per-workspace reuse
  (`max_per_workspace`), wrong plan/kind (`applies_to`), and expiry;
  `discount_for()` computes percent/fixed/free_months/free_reviews discounts,
  never exceeding the list price. `CouponRedemption` is written only on
  payment SUCCESS (`_redeem_coupon_if_any`), never at quote time — an
  abandoned checkout must never burn a redemption — and its
  `payment_intent_id` uniqueness (idempotent-insert idiom, `IntegrityError`
  caught not re-raised) closes the double-redeem race a duplicate webhook
  delivery could otherwise exploit against a `max_redemptions=1` coupon.
  Redemption limits are re-checked again at this point, not just at quote
  time, for the same reason.
- **B20 (credit ledger, R-006 §B.3/B.4, TS-090 bugfix):** `Credit` is an
  append-only ledger (`credit_balance()` sums it, never a mutable balance
  column — same discipline as `payment_log`/`usage_events`). Credit is
  reserved at checkout time (`credit_applied_minor` on the `PaymentIntent`)
  but only actually consumed — a negative `Credit` row written — on payment
  SUCCESS (`_consume_credit_if_any`), so an abandoned checkout never spends a
  balance the customer never paid with. **Bugfix found via this task's own
  Postgres validation:** `credit_balance()` returned
  `select(func.coalesce(func.sum(Credit.amount_minor), 0))` unconverted —
  Postgres's `SUM()` over a `BigInteger` (`bigint`) column returns `NUMERIC`,
  which psycopg maps to Python `Decimal`, while SQLite's `SUM()` returns a
  plain `int`. Every test passed on SQLite; under real Postgres, the first
  checkout for a workspace with a nonzero credit balance poisoned
  `credit_applied_minor`/`amount_minor` with a `Decimal`, which
  `json.dumps` (the provider order's `checkout_payload`) can't serialize,
  crashing checkout entirely. Fixed with an explicit `int(...)` cast.
- **B21 (referrals — cross-tenant RLS, R-006 §B.7, TS-090 major bugfix):**
  a referred workspace's signup transaction is bound to **its own** new
  workspace's RLS context, never the referrer's — there is no point in the
  flow where the caller is authenticated as, or a member of, the referrer's
  workspace. An initial version of this feature resolved a referral code via
  a plain `Workspace.referral_code` query
  (`WorkspaceAdmin.find_by_referral_code`): under real Postgres with FORCE
  RLS live, `workspaces`' compound predicate (visible only if it's the bound
  workspace OR the caller's own membership) made the referrer's row
  invisible, so the lookup silently returned `None` and no `Referral` row
  was ever created — confirmed via `select count(*) from referrals` = 0 and
  both workspaces showing a 0 credit balance after a real paid purchase.
  **SQLite's tests passed the whole time**, because `bind_workspace_context`
  is a documented no-op there — the third time in this codebase's history
  that "SQLite green, Postgres red" caught a real cross-tenant bug (see
  R-001's migration-ordering bug and the free-review race for the other
  two). Fixed by resolving through a new, deliberately non-RLS
  `ReferralCode` pointer table (`billing.resolve_referral_code`) instead —
  same precedent as `PaymentIntent`. A second, related violation:
  `_reward_referral_if_qualifying` wrote a `Credit` row for the referrer's
  workspace while RLS was still bound to the referred workspace's context
  (the only binding `process_webhook` ever sets) — a genuine cross-tenant
  write that `credits`' `WITH CHECK` correctly rejects. Fixed by explicitly
  calling `bind_workspace_context(self.s, referral.referrer_workspace_id)`
  before that specific insert, then rebinding back afterward — mirroring how
  `process_webhook` already binds to `log_workspace` for its own purposes.
  Both bugs are covered by `tests/test_referrals_postgres.py` (real
  Postgres, FORCE RLS live, full app + `TestClient`), sanity-checked by
  temporarily reverting each fix in turn and confirming the test fails the
  way the bug actually failed (bug #1: silent 0-row/0-balance; bug #2: a
  `ProgrammingError` from Postgres's RLS engine itself).
- **B22 (referral reward, R-006 §B.7):** a referred workspace's FIRST paid
  purchase rewards both sides (₹2,500/side —
  `assumption:` a pricing placeholder, not specified in R-006). `Referral.
  status` transitions `signed_up -> rewarded` exactly once; the status check
  IS the idempotency guard for a second purchase, no separate dedup key
  needed. Self-referral (same owner email domain on both sides, since the
  same person can sign up with a different address at the same employer) is
  blocked silently at signup — no `Referral` row is ever created — rather
  than erroring, so an invalid/unknown code never blocks signup and a
  self-referral attempt is never tipped off that it was detected.
- **B23 (trials, R-006 §B.8):** a workspace may hold one trial, ever —
  `Workspace.had_trial` is set the moment a trial STARTS, not when it ends,
  so it can never be restarted via a later downgrade back to free.
- **B24 (pilot comps, R-006 §B.9):** superadmin-only `set_comp` grants a paid
  plan with no real payment behind it (`billing_provider="comp"`, so a future
  revenue-metrics system — none exists yet — can exclude it), auto-reverting
  once `comp_expires_at` passes. Computed lazily on every read
  (`_effective_plan_and_status`), the same no-scheduled-job pattern as
  `past_due` grace expiry (B17) — the workspace's real stored `plan` is never
  mutated by expiry, only the computed "effective" view.

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
- A20 (R-009): an 11th... well, a 3rd member on a free workspace (2 seats)
  returns `402 seat_limit_reached`; a live pending invitation counts toward
  the total; billing disabled means no limit at all.
- A21 (R-009): a `pro` workspace at 10/10 reviews is blocked
  (`quota_exhausted`); buying a top-up (`kind: "topup"`) allows exactly one
  more review in the SAME period, without changing `workspace.plan`.
- A22 (R-009): a top-up granted in an earlier period does not count toward
  the current period's `reviews_topup` (verified directly against
  `UsageEvent.created_at` outside the period bounds).
- A23 (R-009): a `subscription` checkout to a plan whose seat limit is below
  the workspace's current member count returns `400 seats_exceed_new_plan`
  naming how many seats are over; no member is removed.
- A24 (R-009): a `past_due` workspace inside `grace_until` runs reviews
  normally; the same workspace past `grace_until` gets `402
  payment_overdue`.
- A25 (R-009): a subscription's period bounds come from the provider's own
  `current_start`/`current_end` when present (verified via a synthetic
  payload with a 28 Jan → 28 Feb period), not a hardcoded calendar month.
- A26 (R-006): a coupon at `max_redemptions` or a workspace's own
  `max_per_workspace` limit is rejected (`coupon_exhausted` /
  `coupon_already_used`); a currency-mismatched fixed coupon is rejected
  (`coupon_currency_mismatch`); an abandoned checkout (never paid) burns no
  redemption.
- A27 (R-006): two different webhook deliveries for the same
  `PaymentIntent` (distinct `event_id`s, so the outer `WebhookEvent` dedup
  doesn't shortcut the test) redeem a coupon at most once, proven by
  temporarily removing `CouponRedemption.payment_intent_id`'s unique
  constraint and confirming the test then fails.
- A28 (R-006): `credit_balance` reflects the ledger sum exactly and returns a
  plain Python `int` under real Postgres, not `Decimal` (regression test for
  B20 — a checkout with a nonzero credit balance must not crash on
  `json.dumps`).
- A29 (R-006): a referred workspace's signup — under real Postgres with
  FORCE RLS live, not SQLite — creates exactly one `Referral` row and
  registers a `referral_codes` pointer row; a referral code re-fetched via
  `GET /billing/referral` is stable (same code both times).
- A30 (R-006): the referred workspace's first paid purchase credits BOTH
  workspaces ₹2,500 each — verified against real Postgres with FORCE RLS
  live (`tests/test_referrals_postgres.py`), which fails with the exact
  RLS-rejection or silent-zero-row symptom described in B21 when either fix
  is reverted. A second purchase does not reward again.
- A31 (R-006): self-referral (same owner email domain, e.g. a referred
  signup using a work email at the same company as the referrer) creates no
  `Referral` row and signup still succeeds.
- A32 (R-006): a workspace can start exactly one trial, ever;
  `start_trial` on a workspace with `had_trial=true` (even after the trial
  itself has since expired) raises `trial_already_used`.
- A33 (R-006): a superadmin-only comp grant is rejected for a non-superadmin
  caller (`403`); a comp's `expires_at` passing reverts the workspace's
  *effective* plan/status on the next read without ever mutating the stored
  `workspace.plan` column.

## Out of scope

Stripe live wiring (P2/GCC), admin refund console (Doc §16, P1-admin scope),
annual plans/proration polish, GSTR-1 filing exports, e-invoicing/IRN
registration, TDS/TCS handling (R-007 explicitly defers these), requiring a
GSTIN-or-explicit-unregistered declaration before checkout (R-007 §B.9) — a
B2C invoice with no GSTIN is already valid per the edge-case table, so this
gate is a UX nicety deferred rather than a correctness gap — and true
deferred-effect downgrades/cancellations that don't immediately violate a
limit (R-009 §B.5; needs R-016/TS-105's job scheduler to have anything to
act on the deferral). A theoretical TOCTOU race on seat checks (two
concurrent `add_workspace_member` calls both passing the check) is not
locked the way the free-review race is — lower severity than a double-spent
free review or a broken invoice sequence, and not fixed in this pass.
Affiliate/partner commission tracking (R-006 explicitly scopes referrals to
customer-to-customer only), fraud/velocity limits on referral signups beyond
the same-employer-domain check, and coupon-usage analytics/reporting are all
deferred past this pass (R-006, TS-090).
