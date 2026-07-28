# Changelog

All notable changes to TenderShield. Updated **every session** with what was
done and what comes next (see `CLAUDE.md` §1.5). Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); task IDs reference `tasks/backlog.md`.

## [Unreleased]

### Done — 2026-07-28 (Product-discovery audit — capabilities never built: TS-126)

`docs/GAP_ANALYSIS.md` (TS-083) audited what exists and found it defective, and
Gates 1–4 fixed it. This audit asks the opposite question — **what was never
built at all**: requirements never written, roles with no reachable workflow,
journeys that dead-end, capabilities the domain expects that appear nowhere.

- **The finding that reframes the previous four gates: a user cannot upload
  their own tender.** `POST /ingestion/opportunities/{id}/upload` is fully
  implemented and was hardened in TS-095 (streaming, size cap, magic-byte
  validation) — and has **no user interface**. There is no `<input type="file">`,
  no `FormData`, and no caller anywhere in `frontend/`. The only path a document
  takes into the system is the "Upload sample tender" button, which posts a
  hardcoded 12-line demo string. Everything downstream — risk review, BOQ checks,
  deadline extraction, artifacts, export, and the paywall charging ₹7,500 per
  review — currently operates exclusively on that fixture. Gates 1–4 made a
  workspace billable, isolated and switchable; it is not yet usable.
- **Other release-blocking discoveries.** `Opportunity.status` is a dead column
  never written by any code path, so the product that produces "bid-decision
  artifacts" has nowhere to record the decision (and its own Phase-1/kill-gate
  metrics are unmeasurable). The app has **two DELETE routes in total**, both on
  `standards` — nothing can be archived or deleted. `notifications/digest.py`
  implements the deadline-alert thresholds exactly as specified and has **zero
  callers**, so the product's primary promise is unrealised. A departed employee
  **cannot be removed** from a workspace — there is no member-removal route.
- **Seven implemented, tested, routable backend modules have no UI at all**:
  timeline (including a finished `.ics` calendar feed), review queue, qualification,
  comparison, crossref, rulepacks, plus the ops console. The `reviewer` role gates
  only the review-queue endpoints, so it currently has no reachable workflow.
- **Cross-cutting:** roles are enforced server-side but unmanageable and invisible
  in the UI; `projects`/`project_members` is a fully-built sub-tenant layer with
  zero product references; `audit_log` is written in exactly one place (review
  decisions) so no auth, billing, membership or export action is auditable.
- **New:** `docs/PRODUCT_DISCOVERY_GAPS.md` (16 gaps, each with the full
  capability / roles / evidence / classification / consequences / proposed
  behavior / changes / acceptance / priority / release-blocking / questions
  treatment), requirement docs **R-017…R-023**, tracker **Gates 5–7**, and
  backlog rows **TS-110…TS-126**. Findings are classified Confirmed Missing /
  Strongly Implied / Domain-Expected / Clarification Required — nothing inferred
  is recorded as confirmed.
- **10 product decisions are still required** and are listed in both the audit
  and the tracker. The most consequential: does DPDP apply at launch (decides
  whether TS-115 blocks release), is this a design-partner cohort or GA, and who
  receives deadline alerts by default — "the assignee" would require building
  assignment, which does not exist.
- No product-context brief was supplied, so the product context used for the
  audit is inferred from the repository and labelled as assumptions throughout.

### Done — 2026-07-28 (Workspace switching: TS-100)

Before this, a user who belonged to several workspaces landed in an
arbitrary one at login (an unordered `WorkspaceMember` query — the same
user's next login could land somewhere different for no reason a customer
could explain) and had no way to reach any workspace but the one baked into
their current token. Persona P3 (a QS consultancy working across client
workspaces) couldn't use the product as designed.

- **Deterministic login workspace (real bug found and fixed).**
  `login`/`refresh`/`apple_callback` now resolve via new
  `AuthService._resolve_login_workspace`: explicit default → last used →
  oldest membership (`Workspace.created_at ASC` tiebreak), via two new
  `User` columns (`default_workspace_id`, `last_workspace_id`). `login`/
  `apple_callback` update `last_workspace_id` on every sign-in;
  `switch_workspace` (below) also updates it, so a later plain login lands
  back in whichever workspace was last switched to — `refresh` deliberately
  does NOT update it, since a refresh is a transparent continuation, not a
  fresh workspace choice. Regression-proven: a test logs in again after
  switching to a workspace that is NOT the oldest membership and confirms
  it lands there — sanity-checked by temporarily reverting to the old naive
  query and confirming the test then fails.
- **New `POST /auth/workspaces/{id}/switch`.** Verifies membership
  server-side (non-members get `404`, not `403` — matching
  `require_workspace_member`'s existing reasoning: a 403 would itself
  confirm the workspace exists) and re-issues tokens carrying the target
  workspace's role — a client cannot switch by editing its own token, since
  the workspace claim is what RLS binds to. Retires the PREVIOUS
  refresh-token family (`assumption:` one active session per user at a
  time — concurrent families per workspace would interact badly with the
  reuse-detection model and R-010's single-flight refresh).
- **`no_workspace` dead end closed.** A user with zero memberships (e.g.
  their last membership was removed) now gets a workspace-less token
  instead of `AuthError("no_workspace")` locking them out entirely.
- **`GET /auth/workspaces`** now returns `plan`/`is_current` per row, enough
  for the frontend switcher to render without a second call.
- **Frontend: header `WorkspaceSwitcher`** (hidden entirely for a
  single-workspace user — a switcher with one option is noise), built on
  the R-010/TS-092 session plumbing: switching calls the SAME `signIn()`
  login already uses, so it persists the rotated refresh token and swaps in
  a new `session` object — every protected page's data-fetching effect
  already depends on `session`, so switching naturally triggers a refetch
  under the new workspace with no dedicated cache-clear step needed (this
  codebase has no shared query cache). New `/workspaces/new` page: a
  workspace-less session is now redirected here by `RequireAuth` instead of
  onto a protected page that would just show empty results under RLS.
- Validated live with a real browser: switcher absent with one workspace,
  appears once a second is created, switching updates the header and lands
  back on `/opportunities`. New `tests/test_workspace_switching.py` (7
  tests). Updated `specs/modules/auth.md` (B18-B19, A17-A23),
  `specs/frontend.md` (B13, A16-A17), `specs/requirements/
  R-011-workspace-switching.md` (status: implemented). 247 SQLite tests
  pass (1 skipped) + 13 Postgres tests; `ruff check .`, `next build`,
  `tsc --noEmit` all clean.

### Done — 2026-07-28 (Frontend session: refresh tokens, 401 recovery, route guards: TS-092)

Before this, the frontend discarded the refresh token it was handed at
login — the access token (15-minute TTL) was the ONLY credential kept, so
every session died 15 minutes after sign-in with no recovery path, and there
was no 401 interceptor to even detect it. This is Gate 3's first task (make
it usable); Gate 2 closed with the previous entry.

- **Token custody rewritten (Phase 1 of R-010 — Phase 2 moves the refresh
  token to an httpOnly cookie, tracked under R-016).** Access token is now
  memory-only React state, never persisted; the refresh token is persisted
  and rotated on every use. New `lib/auth-client.ts` is framework-free (no
  React import) so both `components/session.tsx` (the React state owner)
  and `lib/api.ts` (a plain function, no hooks) can share one refresh
  implementation without a dependency cycle between them.
- **Single-flight refresh.** The backend revokes the WHOLE refresh-token
  family when a refresh token is replayed (`auth/refresh.py`'s reuse
  detection) — two concurrent refreshes against the same stored token would
  look exactly like a replay and log the user out for being fast. A
  module-level `inflight` promise collapses concurrent callers into one
  request, including across browser tabs (they share the same
  localStorage-held token).
- **Proactive + reactive refresh.** `components/session.tsx` schedules a
  refresh 60 seconds before the access token's own `exp` claim (decoded
  client-side — display/scheduling only, never a trust boundary).
  `lib/api.ts`'s `req()` additionally retries exactly once on a 401 with a
  freshly refreshed token; every OTHER call site's `api.xxx(token, ...)`
  signature is unchanged, so this didn't require touching every page that
  calls the API.
- **Typed errors.** New `lib/errors.ts`: `ApiError`/`SessionExpired`/
  `PaywallError`, replacing `throw new Error(body.detail)` — the reason a
  402's object payload used to render as the literal string
  `"[object Object]"` in the UI. `PaywallError.upsell` is now always a real
  object.
- **Route protection.** New `components/require-auth.tsx`: gates on a real
  three-state `status` (`loading | authenticated | unauthenticated`), not
  `session` (which is legitimately `null` in both the loading and the
  truly-signed-out case — the exact reason a signed-in user's reload used to
  flash "signed out" for a frame). An unauthenticated visit to a protected
  route now redirects to `/login?next=<path>` and returns there after
  sign-in, instead of rendering whatever the page's own `if (!session)`
  branch happened to show. Wraps `/opportunities`, `/opportunities/[id]`,
  `/billing`, `/standards`.
- **Multi-tab coordination.** A `BroadcastChannel`-based channel propagates
  a refresh or sign-out from one tab to every other open tab.
- **New test infrastructure.** Vitest + Testing Library (this project's
  FIRST frontend test framework — R-010's own spec calls for this as "a
  natural first consumer," ahead of R-014/TS-104's broader test-stack task).
  `lib/auth-client.test.ts` (7 tests) and `lib/api.test.ts` (2 tests),
  including a test proving single-flight collapses 3 concurrent refresh
  calls into exactly 1 network request — sanity-checked by temporarily
  removing the `if (inflight) return inflight;` guard and confirming both
  tests then fail (3 calls observed, not 1) before restoring it.
- **Validated live**, not just via `next build`: signed up + logged in
  against a real running backend with a real Chromium browser
  (Playwright, used ad hoc for this validation only — not added as a
  project dependency). Confirmed: unauthenticated `/opportunities` and
  `/billing` redirect to `/login?next=...`; sign-in returns to that exact
  path; `localStorage` after login contains only `ts_refresh`/`ts_hint`, no
  access token; a full reload while signed in never flashes signed-out;
  revoking the refresh token server-side (simulating expiry or a
  sign-out-elsewhere) and reloading redirects to `/login` exactly once, with
  no loop, and clears `ts_refresh`.
- Updated `specs/frontend.md` (B12, A7-A15), `specs/requirements/
  R-010-frontend-session.md` (status: implemented), `tasks/
  gap_remediation_tracker.md` (TS-092 done, Gate 3 now 1/7), `tasks/
  backlog.md`. `next build`/`tsc --noEmit`/`npm test` (9 tests) all clean.

### Done — 2026-07-28 (Coupons, discounts, credits, referrals, trials, pilot comps: TS-090)

Before this, `grep -rni "coupon|discount|promo|referral|trial"` across the
product returned zero hits — there was no way to give anyone a discount, run
a promotion, credit a referral, or comp a pilot account. This is Gate 2's
last task; **Gate 2 (make it possible to get paid) is now fully closed.**

- **Coupons/discounts.** New `coupons.py` (pure): percent/fixed/free_months/
  free_reviews discounts, validated against currency, exhaustion
  (`max_redemptions`), per-workspace reuse (`max_per_workspace`), applicable
  plan/kind, and expiry. `POST /billing/coupons/validate` previews a
  discount without redeeming it. Redemption (`CouponRedemption`, append-only,
  workspace-scoped) is written only on payment SUCCESS, never at quote time,
  via the same idempotent-insert idiom as `WebhookEvent`
  (`payment_intent_id` unique, `IntegrityError` caught not re-raised) — a
  duplicate webhook can't double-redeem a `max_redemptions=1` coupon.
- **Prepaid credit ledger.** New `Credit` (append-only, workspace-scoped);
  `credit_balance()` sums it. Reserved at checkout (`credit_applied_minor`
  on the intent), consumed only on payment success — an abandoned checkout
  never spends a balance never paid with.
- **Referrals.** Each workspace gets a lazily-generated referral code
  (`GET /billing/referral`). A referred workspace's first paid purchase
  rewards both sides (₹2,500 each — `assumption:` a pricing placeholder, not
  specified in R-006). Self-referral (same owner email domain on both
  sides) is blocked silently at signup.
- **Trials & pilot comps.** One trial per workspace, ever
  (`POST /billing/trial/start`); superadmin-only pilot comps
  (`POST /billing/admin/comp`) grant a paid plan with no real payment
  behind it, auto-reverting on `comp_expires_at` (computed lazily on every
  read, same no-scheduled-job pattern as `past_due` grace expiry).
- **Two real bugs found and fixed while validating this against real
  Postgres with FORCE RLS live** (both passed vacuously on SQLite, where RLS
  is a documented no-op):
  1. **Cross-tenant RLS violation in the referral flow (major).** A referred
     workspace's signup transaction is bound to *its own* new workspace,
     never the referrer's — resolving the referral code via a plain
     `Workspace.referral_code` query silently found nothing (RLS's compound
     predicate hid the referrer's row), so zero `Referral` rows were ever
     created and zero credits ever granted. A second, related violation:
     crediting the referrer's workspace from inside the referred
     workspace's webhook-processing RLS binding is a genuine cross-tenant
     write that `credits`' `WITH CHECK` correctly rejected. Fixed with a
     new, deliberately non-RLS `referral_codes` pointer table (same
     precedent as `payment_intents`/`refresh_tokens`/`password_resets`,
     consumed via new `billing.resolve_referral_code`/
     `billing.record_referral_signup` capabilities) and by explicitly
     rebinding RLS context (`bind_workspace_context`) around the
     referrer-side credit insert. Both fixes sanity-checked by temporarily
     reverting each and confirming the new
     `tests/test_referrals_postgres.py` fails the way the bug actually
     failed (silent 0-row/0-balance for the read side; a Postgres
     `ProgrammingError` from the RLS engine itself for the write side).
  2. **`credit_balance()` returned a `Decimal` under real Postgres, an
     `int` under SQLite.** `SUM()` over a `BigInteger` column returns
     `NUMERIC` in Postgres (psycopg maps that to `Decimal`); SQLite's
     `SUM()` returns a plain int. Every test passed on SQLite; under
     Postgres, the first checkout for a workspace with a nonzero credit
     balance poisoned `credit_applied_minor`/`amount_minor` with a
     `Decimal`, crashing `json.dumps` on the order's `checkout_payload`.
     Fixed with an explicit `int(...)` cast.
- **Migration bugfix (found in passing).** Two historical migrations
  (`ae76edba3a7a`, `e26e85245237`) crash on a from-scratch Postgres build:
  `WORKSPACE_SCOPED_TABLES` is a live, process-wide set populated at
  model-import time, not a per-migration snapshot, so they tried to enable
  RLS on `coupon_redemptions`/`credits` before this task's own migration had
  created those tables. Fixed with an existence guard
  (`sa.inspect(...).get_table_names()`); verified with a full `alembic
  upgrade head` → `downgrade base` → `upgrade head` cycle on a fresh
  database, and `pg_class.relrowsecurity`/`relforcerowsecurity` confirms
  `coupon_redemptions`/`credits` carry RLS while `referral_codes` (like
  `payment_intents`/`coupons`/`referrals`) correctly does not.
- New `tests/test_coupons_referrals.py` (22 tests) and
  `tests/test_referrals_postgres.py` (2 tests, real Postgres/FORCE RLS).
  Updated `specs/modules/billing.md` (B19-B24, A26-A33),
  `specs/modules/auth.md` (B17, A15-A16), and
  `specs/requirements/R-006-coupons-discounts.md` (status: implemented).
  240 SQLite tests pass (1 skipped) + 13 Postgres tests; `ruff check .`
  clean.

### Next

- **Re-prioritise: Gate 5 (TS-110 upload) now outranks the rest of Gate 3.**
  The discovery audit found that no customer can upload their own tender, which
  makes most of Gates 3–4 unreachable with real data. Recommended order:
  **TS-110 (upload) → TS-119 (review queue) → TS-111 (lifecycle) → TS-112
  (archive) → TS-116 (member removal)**, then resume Gate 3.
- Gate 3 remains 2/7 (TS-092, TS-100 done): TS-099 (email verification),
  TS-101 (MFA enforcement), TS-102 (dashboard), TS-103 (account UI), TS-104
  (design system + remaining test stack).
- **Blocked on product decisions** (see `docs/PRODUCT_DISCOVERY_GAPS.md`
  §Product Decisions Required): TS-115 needs the DPDP answer; TS-113's default
  alert recipient needs the assignment decision; TS-110's scope needs the
  max-pack-size / resumable / ZIP answers.

### Done — 2026-07-28 (Plan entitlements — seats, top-ups, billing periods: TS-098)

`PLAN_LIMITS` declared `seats` per plan and nothing ever read it — a
workspace on any plan could add unlimited members. `authorize()`'s
`has_topups` parameter had no caller, so top-ups were unsellable. Quota reset
on a hardcoded calendar month regardless of when a subscription started.
This is Gate 2's last P1 task: one `Entitlements` object, seats actually
enforced, top-ups sellable, and billing-anniversary periods.

- **One `Entitlements` object** (new `billing/entitlements.py`, pure) —
  `reviews_remaining`, `seats_remaining`, `is_entitled` — so a limit can't be
  enforced in one module and forgotten in another.
- **Seats enforced.** New `auth.seats_used` capability (billing can't query
  auth's own `workspace_members`/`invitations` tables) feeds a new
  `billing.entitlements` capability; `AuthService._check_seat_available`
  blocks `add_workspace_member`/`create_invitation`/`accept_invitation` at
  capacity with `402 seat_limit_reached` — a commercial limit, not an authz
  failure, so it's 402 not 403 and carries the same `{code, upsell}` shape
  the frontend's `<Paywall/>` already renders for billing's own errors.
  Pending invitations count toward the limit; `accept_invitation` excludes
  the invitation being accepted from its own count (it already reserved that
  seat when created).
- **Top-ups sellable.** `POST /billing/checkout {"kind": "topup"}` resolves
  price from the workspace's own current plan (never client-named); the
  webhook credits `review_topup_granted` (never touching `workspace.plan` —
  unlike paygo/subscription, a top-up isn't a plan election).
  `authorize()`'s real signature (`reviews_used`/`reviews_topup`) replaces
  `reviews_this_month`/`has_topups`. Unused top-ups expire with the period
  they were bought in — `_topups_in_period` nets granted-minus-refunded
  scoped to the current period's bounds only.
- **Billing-anniversary periods.** `BillingService._period` uses the
  Razorpay subscription entity's own `current_start`/`current_end` when
  present (extracted by new `_subscription_period`), falling back to
  calendar month only for free/paygo. New `add_month` is month-end-safe
  (31 Jan → 28/29 Feb, never 3 Mar).
- **Downgrade guard.** A `subscription` checkout to a plan with fewer seats
  than the workspace currently uses returns `400 seats_exceed_new_plan`
  naming how many seats are over — never auto-removing members.
- **Two real bugs found and fixed while building this.** (1) A `past_due`
  workspace kept full access **indefinitely** — `authorize()` never actually
  compared the current time against `grace_until`, so the "grace window"
  was cosmetic. Fixed with a `grace_expired` param, computed in
  `authorize_review` and checked before granting. (2) Testing that fix
  immediately hit a second, unrelated bug: SQLite returns **naive**
  datetimes even for `DateTime(timezone=True)` columns (Postgres preserves
  timezone), which crashed the very first aware-vs-naive comparison.
  New `entitlements.as_aware_utc` fixes it — and also corrects `GET
  /billing/status`'s `grace_until`/`period_end` ISO serialization, which had
  carried the exact same latent bug since the TS-097 work shipped it (no
  prior test compared the serialized string closely enough to notice).
- **Frontend**: `/billing`'s usage meters now read `reviews_included`/
  `reviews_topup`/`seats_included`/`seats_used` from the real
  `GET /billing/status` response instead of a client-side `PLAN_LIMITS`
  duplicate (a gap flagged in the TS-091 changelog entry). `<Paywall/>`
  gained a `payment_overdue` code and a "Buy a top-up" button for
  `quota_exhausted`.
- New `tests/test_entitlements.py` (14 tests: month-end rollover, seat
  enforcement including the pending-invitation and billing-disabled cases,
  top-up purchase + period-expiry, the downgrade guard, past_due
  inside/outside grace, provider-sourced billing periods). Updated
  `specs/modules/billing.md` (B13-B18, A20-A25) and `specs/modules/auth.md`
  (B16, A14).
- No schema migration needed — `kind`/`event` are already free-form string
  columns, so `"topup"`/`review_topup_granted`/`review_topup_refunded` are
  new values, not new columns.
- Validated against real Postgres with FORCE RLS live: a dedicated e2e
  script drove signup → status (exercising the `auth.seats_used` →
  `billing.entitlements` cross-module registry call chain) → add-member →
  add-member-again → `402 seat_limit_reached`, all correct under FORCE RLS.
  218 SQLite tests pass (1 skipped) + 11 Postgres tests; `ruff check`,
  `next build`, and `tsc --noEmit` all clean.

### Done — 2026-07-28 (GST invoicing wired end to end: TS-096)

`gst.py`'s tax-correct computation existed but was completely dead code —
real invoices went through `create_invoice`, an untaxed placeholder
(`INV-000042`, no tax columns at all). This wires it in.

- **Tax-correct invoices.** `Invoice` gains `base_minor`/`cgst_minor`/
  `sgst_minor`/`igst_minor`/`round_off_minor`/`total_minor` (replacing the
  untaxed `amount_minor`), plus `fy`/`seq`/`doc_type`/`original_invoice_id`
  and snapshotted buyer/seller GST identity. New `issue_invoice(intent,
  event)` replaces `create_invoice`, called from `_on_payment_succeeded` on
  every successful payment.
- **Deliberate deviation from the draft spec:** catalog prices are treated as
  GST-**inclusive** rather than tax-added-on-top, so nothing about what a
  customer is charged changes — `gst.py`'s new
  `compute_invoice_from_inclusive_total` backs the taxable base and tax
  lines out of the amount actually charged, with any ±1 paise rounding
  residue landing in an explicit `round_off_minor` so
  `base + taxes + round_off == total` always holds exactly (verified with a
  1,000-iteration property test). The same split runs once at checkout
  (informational `tax_minor`) and again at issuance against the identical
  `intent.amount_minor`, so the two can never diverge — the draft's
  "reconciliation check" is true by construction instead of something to
  verify after the fact.
- **Gap-free per-FY numbering** (`TS/2026-27/000001`, ...) via a new
  `invoice_sequences` table and `SELECT ... FOR UPDATE`. Proving this against
  real, non-superuser PostgreSQL with two genuine threads caught a real bug:
  `FOR UPDATE` can't lock a row that doesn't exist yet, so the very first
  invoice of a new financial year let two concurrent issuers both try to
  INSERT the sequence row, and one lost to a unique-constraint violation.
  Fixed with a `pg_advisory_xact_lock` keyed on the FY (mirroring the
  existing free-review lock pattern) — sanity-checked both directions:
  fails reliably without the lock, passes reliably with it.
- **Credit notes on refund** (`issue_credit_note`) — same series as the
  original invoice, referencing it by id, apportioned at the same tax rate;
  a partial refund produces a partial credit note.
- **GSTIN capture and validation.** New `PUT /billing/details` (admin) sets
  buyer `legal_name`/`gstin`/`billing_address`/`place_of_supply`; format +
  checksum are validated before persisting (`gst.validate_gstin`) — invalid
  GSTINs are rejected at save time, not discovered wrong at invoice
  issuance. **Honesty note:** the checksum algorithm is self-consistent
  (built and tested against its own check-digit function, catches a
  typo'd/transposed GSTIN reliably) but has not been verified against a real
  GSTN reference vector — this sandbox has no way to confirm the exact
  published algorithm against an authoritative source. Flagged explicitly in
  `gst.py`'s docstring and the spec for confirmation before this gates a
  live paid checkout, the same posture already used for the SAC-rate
  assumption.
- **PDFs render on demand** (`GET /invoices/{id}/pdf`, workspace-scoped, via
  `reportlab`) rather than being pre-rendered and stored through the
  `Storage` protocol the draft suggested — `billing` cannot import
  `ingestion.storage` (CLAUDE.md §2) and no cross-module storage capability
  exists yet, and re-rendering from the invoice's own already-durable fields
  can never drift from the statutory record.
- **Real pre-existing CI gap found and fixed in passing:**
  `test_billing_race_postgres.py` (written during the earlier TS-087 work)
  was never actually wired into the `backend-postgres` CI job — it only ran
  `test_rls_postgres.py`. The job now runs the full `-m postgres` suite
  (verified locally against a fresh, isolated database matching CI's exact
  setup).
- New migration adds `invoice_sequences`, rewrites `invoices`' tax columns,
  and adds GST buyer-identity columns to `workspaces`
  (`legal_name`/`gstin`/`billing_address`/`place_of_supply`); backfills
  existing rows so the new NOT NULL columns don't break on upgrade.
- New `tests/test_gst_invoicing.py` (13 tests: inclusive-split correctness
  both directions, the 1,000-iteration rounding property test, GSTIN
  checksum self-consistency, checkout→webhook→invoice→PDF integration,
  cross-workspace PDF isolation) and `tests/test_gst_invoicing_postgres.py`
  (the gap-free-numbering concurrency test). Updated
  `specs/modules/billing.md` (B5, A14-A19) and
  `specs/requirements/R-007-gst-invoicing.md`.
- Validated against real, non-superuser PostgreSQL with FORCE RLS live:
  migration up/down clean on a fresh database, a dedicated e2e script walked
  checkout(with GSTIN)→webhook→invoice→PDF end to end, and the full
  `-m postgres` suite (11 tests: RLS isolation, free-review race-safety,
  gap-free GST sequencing) passes together. 202 SQLite tests pass (1
  skipped); `ruff check` clean.

### Done — 2026-07-28 (Billing UI — the first paid path end to end: TS-091)

Before this, `frontend/lib/api.ts` had no billing calls at all — the complete
monetization journey was "paywall blocks a review → 402 → nothing." This ships
a thin but complete paid path: `/pricing` (public), `<Paywall/>`,
`<CheckoutDialog/>`, and `/billing` (account home).

- **`/pricing`** — four plan cards (free/paygo/pro/scale) with prices that
  match `PRICES_MINOR` server-side exactly; signed-out users get "Sign up",
  signed-in users get a real checkout button per paid plan.
- **`<Paywall/>`** (`components/paywall.tsx`) — renders the 402 payload from
  any billable action, driven entirely by `detail.code`. Covers the three
  codes the backend can raise today: `free_exhausted`, `paygo_payment_
  required` (both payable per-tender directly from the paywall), and
  `quota_exhausted`. Wired into the opportunity page's "Run risk review"
  action via a new `ApiError` class in `lib/api.ts` that carries the
  structured `detail` payload instead of only a stringified message.
- **`<CheckoutDialog/>`** — opens Razorpay's hosted checkout for a real
  server-created order (`billing.checkout`), then polls
  `GET /billing/intents/{id}` for confirmation. The `handler` callback runs
  entirely on the client and never marks anything paid — only the webhook
  does (Doc §15.1). If the payment provider's script fails to load (offline,
  blocked network — this is exactly what happened testing in this sandbox,
  which has no route to `checkout.razorpay.com`), it now shows a retryable
  error instead of hanging forever on "Preparing checkout…".
- **`/billing`** — current plan + status + grace banner, a usage meter for
  quota'd plans, and — admin/owner only — the invoice table; viewer/estimator
  see a read-only summary with no checkout entry point.
- **Two real backend bugs found and fixed while wiring this UI** (the kind of
  thing that only surfaces when you actually build the client that has to
  call these endpoints):
  1. **A paygo-plan workspace could run unlimited unpaid reviews.**
     `plans.authorize()`'s paygo branch computed `Grant(requires_payment=True)`
     but nothing ever checked it — `meter()`/`authorize_review` just returned
     the grant and let the review through. Fixed by checking for an
     unconsumed `review_paid` usage event (already written by the webhook,
     no new table) before granting; `POST /checkout` now requires
     `opportunity_id` for `kind="paygo"` since payment is scoped to the one
     opportunity it unlocks.
  2. **`workspace.plan` never actually became `"paygo"`,** which made bug
     (1)'s fix unreachable in practice — `_on_payment_succeeded` only called
     `set_plan` for subscription payments. Fixed by calling it for every
     successful payment kind. The `free_exhausted` upsell now also carries
     the blocked opportunity's id so the paywall can pay for that exact
     tender directly, which elects the workspace into the paygo plan and
     unlocks the paid-for opportunity in one webhook.
  Both covered by new regression tests in `test_paywall_enforcement.py`
  (`test_paygo_workspace_blocked_until_its_own_opportunity_is_paid`,
  `test_free_exhausted_workspace_can_pay_per_tender_from_the_paywall`).
- Updated `specs/frontend.md` (B11, A3-A6), `specs/requirements/R-008-billing-ui.md`,
  and `specs/modules/billing.md` (B11, B12, A12, A13) to match.
- Validated against a **live backend** (not just a build check): ran
  `next build`/`tsc --noEmit` clean, then started the real FastAPI backend
  and Next.js dev server together and drove signup → free review → second-
  opportunity paywall → checkout dialog with Playwright, screenshotting each
  step. 189 SQLite tests pass (1 skipped) + 10 Postgres tests (RLS +
  race-safety) after the backend fixes; `ruff check` clean.

### Done — 2026-07-28 (Real payments + full webhook coverage: TS-089, TS-097)

`/billing/checkout` previously returned a handle with no real order behind
it, and the webhook trusted `notes.workspace_id`/`notes.plan` sent back by
the provider redirect — a client could edit those before the redirect and
receive whatever plan it asked for regardless of what it paid. Both are
fixed.

- **TS-089** — New `PaymentProvider` Protocol
  (`app/modules/billing/providers/base.py`: `create_order`, `verify_webhook`,
  `parse_event`) with a real `RazorpayProvider` implementation against the
  Razorpay Orders API, and `select_provider(settings, country)` choosing it
  for `country == "IN"` when keys are configured (adding Stripe for GCC/UK
  later is a new file, not a rewrite). `create_checkout` now creates a
  `PaymentIntent` row *before* contacting the provider, resolves price
  server-side from a new `PRICES_MINOR` table by `(plan, currency)` — the
  client selects which plan, never what it costs — and round-trips only an
  opaque `intent_id` in the order's `notes`. A workspace with no configured
  provider gets `503 payment_provider_unavailable` instead of a fake order;
  an unknown plan gets `400 unknown_plan`. Checkout retries within a 30-minute
  window reopen the same intent/order instead of creating a duplicate. New
  `GET /billing/intents/{id}` lets the client poll confirmation; ownership is
  checked in application code because `PaymentIntent` is deliberately **not**
  RLS-protected (same reasoning as `RefreshToken`/`PasswordReset`: the webhook
  must look the row up by opaque id before it knows the workspace, and RLS
  would block that exact lookup).
- **TS-097** — The webhook now resolves every grant by looking up the
  `PaymentIntent` the event references — never from `notes` fields directly.
  One amount-checked handler (`_on_payment_succeeded`) covers a paygo
  payment, a subscription's first activation, and a renewal charge alike;
  a mismatch between the event's amount and the intent's amount grants
  nothing and logs `amount_mismatch`. This caught a real bug during
  development: an earlier draft treated `subscription.activated` as a
  separate handler that skipped the amount check entirely, so an underpaid
  subscription activation still granted the plan — caught by the new test
  `test_webhook_amount_mismatch_grants_nothing`, fixed by routing
  `subscription.activated` through the same checked handler. Added coverage
  for refunds (`refund.processed` — downgrades a subscription or records
  `review_refunded` for paygo), failures (`payment.failed`), dunning
  (`subscription.halted` → `plan_status=past_due` + 7-day grace, plan itself
  untouched so paid access continues during grace — contractors often pay by
  NEFT off-cycle), and cancellation (`subscription.cancelled` → downgrade to
  free). Idempotency is now a unique-constraint insert on `event_id` (or a
  `sha256(raw_body)` fallback when the provider sends no event id), caught
  via `IntegrityError` — not check-then-act.
- **Real bug found and fixed in passing:** the webhook route is
  unauthenticated (no caller to run `authenticate()`), so it had never bound
  `app.workspace_id` for RLS — silently broken since the TS-086 RLS
  hardening shipped, since nothing had exercised the webhook against FORCE
  RLS until this task's Postgres validation. Fixed by binding
  `bind_workspace_context` explicitly in `process_webhook`, using a fixed
  `UNATTRIBUTED_WORKSPACE` sentinel for events that don't resolve to a known
  intent (e.g. a bad signature).
- New migration `e18ffec0675e`: `payment_intents` table; `workspaces` gains
  `plan_status`, `grace_until`, `current_period_start`,
  `current_period_end`, `provider_subscription_id`.
- Updated `specs/modules/billing.md` — provider abstraction, `PaymentIntent`
  data model and its deliberate RLS exclusion, webhook behavior (B3, B8-B10),
  and new acceptance criteria A7-A11 documented to match what's now actually
  implemented.
- Rewrote `tests/test_billing.py` (21 tests) and updated
  `tests/test_paywall_enforcement.py`'s webhook helper to go through a real
  checkout → webhook round trip instead of hand-crafting `notes` (the old
  shape is the exact vulnerability this task closes, so the old tests
  couldn't be kept as-is).
- Validated against real, non-superuser PostgreSQL with FORCE RLS live:
  migration up/down clean on a fresh database, the existing RLS (10 tests)
  and race-safety Postgres suites still pass with no regression, and a
  dedicated ad-hoc script walked the full
  checkout → webhook → status → invoice → replay-dedup → intent-status flow
  end to end. 187 SQLite tests pass (1 skipped, 10 postgres-marked
  deselected); `ruff check` clean; SQLite and Postgres migrations clean both
  directions.

### Done — 2026-07-28 (Gate 2 started — paywall enforced, watermark applied: TS-087, TS-088)

The two highest-leverage tasks in the whole backlog: before this, the paywall
was unenforced (any client could run unlimited reviews without ever calling
the billing endpoint) and the free tier produced clean, paid-grade exports.

- **TS-087** — Metering moved into the review path itself. New
  `app.core.deps.meter(event)` FastAPI dependency resolves
  `billing.service_factory` by name (risk never imports billing) and gates
  `POST /risk/opportunities/{id}/run`; a blocked workspace gets `402` with the
  upsell payload before any pattern runs, and `billing.paywall_hit` fires on
  the event bus. Degrades gracefully — proceeds unmetered in dev when billing
  is disabled, refuses with `503` in production.
  - `authorize_review(workspace_id, opportunity_id=None)`: re-processing an
    already-metered opportunity (e.g. after an addendum) is now free,
    permanently — tracked via a `review_started` usage event carrying the
    opportunity's id as `ref_id`.
  - **Race-safety, actually verified:** `WorkspaceAdmin.mark_free_review_used`/
    `set_plan` no longer commit internally (that was silently breaking the
    lock — a `pg_advisory_xact_lock` released by an early commit protects
    nothing). The lock, the free-review write, and the usage-event write now
    share one transaction. Proven with real concurrency: new
    `tests/test_billing_race_postgres.py` runs two genuine threads against a
    real, non-superuser PostgreSQL server racing for the same workspace's free
    review — confirmed to actually catch the bug by sanity-checking both
    directions (fails 5/5 with the lock removed, passes 5/5 with it restored).
- **TS-088** — Free-tier watermark applied in all three export formats,
  decided server-side by a new `billing.export_entitlement` capability from
  `Workspace.plan`, never from client input. XLSX gets a tinted title cell
  plus the mark repeated in the printed header/footer (survives a
  copy-paste into a new sheet); DOCX gets it in the page header (every page);
  PDF gets a diagonal grey page stamp via a reportlab page callback (every
  page). Marks the *document* only — a test
  (`test_free_and_paid_exports_have_identical_findings`) confirms free and
  paid exports of the same opportunity carry byte-for-byte identical findings.
- Updated `specs/modules/billing.md`, `risk.md`, `export.md` to match — several
  claims in those specs (race-safety, the watermark, `paywall_hit`) were
  previously aspirational/not-yet-implemented and are now actually true.
- 175 SQLite tests + 10 Postgres tests pass (19 new tests total, including the
  concurrency test); `ruff check` clean; `alembic upgrade head`/`downgrade
  base` clean on both dialects (no schema change this task).

### Done — 2026-07-28 (Gate 1 complete: TS-084, TS-085, TS-086, TS-093, TS-094, TS-095)

Implementation of five of Gate 1's six tasks from `tasks/gap_remediation_tracker.md`,
validated against **real PostgreSQL** (not just SQLite) — a local Postgres 16
server was provisioned specifically to exercise the RLS isolation guarantee,
which had never been tested against a real database before this session.

- **TS-084** — Membership authorization on every workspace/project path-scoped
  route. New `require_workspace_member(min_role)` / `require_project_member(min_role)`
  guards in `auth/deps.py` verify the caller's real membership of the workspace
  named in the URL (not the token's active workspace) before
  `GET/POST /workspaces/{id}/members`, `POST/GET /workspaces/{id}/projects`,
  and `GET/POST /projects/{id}/members` do anything; non-members get `404`
  (not `403`, so existence isn't disclosed). Also closes a real privilege
  escalation: an admin of workspace A could previously add themselves as
  `owner` of workspace B by posting to `/workspaces/{B}/members`. Added a
  last-owner guard (`add_workspace_member` now refuses to demote the sole
  remaining owner, `400 last_owner`) and fixed `list_project_members` to
  filter by workspace defensively.
- **TS-085** — `forgot_password`/`create_invitation` no longer echo raw tokens
  by default. New `TS_DEV_ECHO_TOKENS` setting (default `false`); app startup
  raises if it's `true` while `TS_ENV=production`. Both flows now also deliver
  via the `notifications.sender` capability (resolved by name — auth never
  imports notifications) when one is configured. `forgot_password` additionally
  invalidates any prior outstanding reset token for the user.
- **TS-093** — `reset_password` now revokes every refresh-token family for the
  user in the same transaction as the password change, so a session held
  before the reset (attacker's or the user's own other device) doesn't survive
  it. Session-list/logout-all endpoints deferred to TS-103 (need a UI to be
  worth shipping).
- **TS-086** — RLS actually isolates now. `FORCE ROW LEVEL SECURITY` (without
  it, PostgreSQL exempts the table *owner* from RLS, and the app connects as
  the owner in every deployment — the original policy was inert) and
  `WITH CHECK` (the original policy only filtered reads; a write could still
  place a row in another workspace) on every workspace-scoped table, plus
  `workspaces`/`workspace_members`/`project_members`, which were silently
  absent from RLS entirely (`WorkspaceScopedMixin` never covered them). New
  migration `ae76edba3a7a`.
  - **Four real bugs found by testing against real Postgres**, not by reading
    the code (documented as an erratum at the top of
    `specs/requirements/R-001-tenant-isolation.md`, since the original draft
    got all four wrong): (1) `SET LOCAL app.workspace_id = :param` is a
    PostgreSQL syntax error — `SET` only accepts a literal; fixed with
    `set_config(...)`. (2) SQLAlchemy's `after_commit` event cannot emit SQL
    (the session has no active transaction when it fires) — the rebinding
    listener that survives mid-request commits now uses `after_begin`
    instead. (3) A plain single-workspace RLS predicate on
    `workspaces`/`workspace_members` breaks `list_workspaces`, which must
    show a user every workspace they belong to — fixed with a compound
    predicate (bound workspace OR the caller's own row), backed by a new
    session-scoped GUC `app.user_id`. (4) That in turn broke `login`,
    `refresh`, and Apple sign-in's existing-user branch, which are
    unauthenticated entry points where `authenticate()` never runs — each now
    binds `app.user_id` explicitly before its first `WorkspaceMember` query.
    Workspace **creation** (`signup`, `create_workspace`, Apple sign-in) was
    unified behind one helper, `AuthService._create_workspace_and_owner`,
    which binds to the new workspace's own pre-generated id before inserting
    it (there's no workspace to bind to until that insert creates one).
  - Also found and fixed only by testing against a **non-superuser** Postgres
    role: a superuser bypasses RLS regardless of `FORCE`, which would have
    made the whole isolation test suite pass vacuously.
  - New `tests/test_rls_postgres.py` (9 tests, `@pytest.mark.postgres`) is the
    only place in the repo this guarantee is exercised — `bind_workspace_context`
    is a documented no-op on SQLite, so it was never tested before. Wired into
    CI as a new `backend-postgres` job (`.github/workflows/ci.yml`) with its
    own Postgres 16 service container and two databases (one for the
    migration up/down check, one dedicated to the RLS test's own minimal
    schema — sharing one database broke the test's `drop_all` against tables
    the test file doesn't import models for).
- Updated `specs/modules/auth.md` (B5, new B12–B15) and `specs/data-model.md`
  (B1, foundation section, acceptance criteria) to match.
- **TS-094** — Rate limiting + per-account lockout. New `app/core/ratelimit.py`
  (`InMemoryLimiter`, `rate_limit(bucket, limit)` FastAPI dependency; correct
  for a single-process deployment, best-effort — its absence never blocks a
  request). Applied to `/signup` (20/hour), `/login` (20/5min),
  `/forgot-password` (3/hour), `/reset-password` (10/hour), `/mfa/verify`
  (5/5min); exceeding a limit returns `429 rate_limited` with `Retry-After`.
  Independently, `login` now applies a capped, exponential-backoff per-account
  lockout: 10 failed attempts locks the account (`423 account_locked`) for up
  to 60 minutes — never permanent, which would hand the attacker a free
  denial-of-service. New `failed_logins`/`locked_until` columns on `users`
  (migration `2cf9d68a748b`). Shipped the IP limit looser than the R-002 §C
  draft (20/5min, not 10/5min) — the draft's number collides with the
  lockout threshold within one test client, so the two defenses could never
  be independently observed in the same test run; the lockout is the precise
  defense against a single-account attack, the IP limit blunts a spray
  attack across many accounts and 20/5min still does that.
- 156 SQLite tests + 9 Postgres tests pass; `ruff check` clean; `alembic
  upgrade head`/`downgrade base` clean on both SQLite and Postgres.
- **TS-095** — Upload safety, closing Gate 1. New shared `app/core/uploads.py`
  (`spool_upload`) — streams a multipart body to a size-capped temp file with
  the cap enforced mid-transfer, never after buffering the whole thing, then
  validates extension against an allowlist and magic bytes against the
  declared extension (rejects e.g. an executable renamed to `.pdf`) before
  anything is persisted or extracted. Applied to **both** file-upload
  endpoints: `ingestion`'s (previously buffered up to 2 GB in memory before
  checking) and `boq`'s (previously had **no size limit at all** — a gap the
  original R-003 draft, scoped only to `ingestion`, didn't call out). Core
  infrastructure rather than living in either module, so `boq` doesn't have to
  import `ingestion` to reuse it (`CLAUDE.md` §2). New
  `Document.size_bytes`/`content_type` columns (migration `c9ed90a8524f`).
  Deliberately **not** shipped in this task, and why: per-workspace storage
  quota (needs `billing.entitlements`, which doesn't exist until R-009/TS-098),
  ZIP-bomb/path-traversal guards (no ZIP upload path exists anywhere in the
  codebase to harden — R-003 §B.4 is forward guidance for when one is built,
  not a gap in something shipped), and malware scanning (interface-only,
  nothing to plug in yet). 10 new tests (`tests/test_upload_safety.py`),
  including a regression test for the boq gap specifically.
- **Gate 1 is now complete** (6/6). 166 SQLite tests + 9 Postgres tests pass;
  `ruff check` clean; `alembic upgrade head`/`downgrade base` clean on SQLite
  and Postgres.

### Next

- **Gate 2, starting with TS-087/TS-088** — enforce metering in the review
  path and apply the free-tier watermark; nothing else in billing has value
  until those two ship. Then TS-089 (real Razorpay orders) and TS-091 (billing
  UI) for a thin but complete paid path.

### Done — 2026-07-28 (whole-project gap analysis: TS-083)

- **TS-083** — Read-only audit of the entire project (business model, monetization,
  auth/registration, security & multi-tenancy, architecture, frontend/UI) against the
  code rather than the specs. Written up in `docs/GAP_ANALYSIS.md` with file:line
  references, severity ratings and a four-gate remediation order.
- Headline findings (no code changed in this session):
  - **P0 cross-tenant leaks** — `GET /auth/workspaces/{id}/members`,
    `GET /auth/projects/{id}/members` and `POST /auth/workspaces/{id}/members` trust the
    path workspace/project id with no membership check. `WorkspaceMember` and
    `ProjectMember` are not `WorkspaceScopedMixin` subclasses, so no RLS policy covers
    them either.
  - **P0 RLS is inert as configured** — no `FORCE ROW LEVEL SECURITY` (owner bypass),
    no `WITH CHECK`, key tables outside `WORKSPACE_SCOPED_TABLES`, and CI runs on SQLite
    only, so isolation is never exercised.
  - **P0 account takeover** — `forgot_password` returns the raw reset token in the HTTP
    response to an unauthenticated caller.
  - **P0 paywall is unenforced** — `authorize_review` is called only by its own endpoint;
    the risk/BOQ/export paths never meter, and the frontend never calls billing at all.
  - **P0 free-tier watermark is never applied** — `Grant.watermark` has no consumer in
    the export renderer, so free reviews produce clean paid-grade output.
  - **P0 no payment path** — `/billing/checkout` creates no provider order, and there is
    no billing UI anywhere in the frontend.
  - **Coupons/discounts/referral credits/trials do not exist** anywhere in the repo.
  - **GST invoicing is dead code** — `billing/gst.py` is imported only by tests; invoices
    carry no tax breakdown and use a non-statutory number series.
  - **Frontend drops the refresh token**, so every session dies 15 minutes after login —
    shorter than the product's own 25-minute p95 processing target.
- Filed **TS-084..TS-109** in `tasks/backlog.md` covering the remediation, ordered as
  four gates: stop the leaks → make it possible to get paid → make it usable → scale
  and prove.

### Done — 2026-07-28 (requirement suite for the gap remediation: TS-083 cont.)

- Second pass over the repo to ground every gap in the actual code, then wrote
  **`specs/requirements/R-001…R-016`** — implementation-ready requirement documents,
  one per change, each with: the current code quoted at `file:line`, a reference
  implementation, the data-model delta, the API contract, numbered behaviours (B1…)
  and acceptance criteria (A1…) written to become tests.
  - **Gate 1** R-001 tenant isolation · R-002 auth hardening · R-003 upload safety
  - **Gate 2** R-004 paywall + watermark · R-005 payments/checkout · R-006 coupons ·
    R-007 GST invoicing · R-008 billing UI · R-009 plan entitlements
  - **Gate 3** R-010 frontend session · R-011 workspace switching · R-012 dashboard ·
    R-013 account UI · R-014 design system · R-015 email verification
  - **Gate 4** R-016 async pipeline, S3 storage, observability, product metrics
- Added **`tasks/gap_remediation_tracker.md`** — the four-gate sprint plan for
  TS-084…TS-109 with per-task acceptance gates, suggested ordering, cross-cutting
  rules (module boundaries, minor units, fail-closed) and a definition of done.
- Cross-linked `tasks/backlog.md` (new Requirement column) and `specs/README.md`.
- Additional findings from the second pass, folded into the requirement docs:
  - `WorkspaceMember` and `ProjectMember` are plain `Base` subclasses, so they are
    absent from `WORKSPACE_SCOPED_TABLES` and **no RLS policy is generated for them
    at all** — the member-list leak has no database backstop (R-001 §B.3).
  - `SET LOCAL` dies with its transaction and services commit mid-request, so a
    single bind at `authenticate()` does not survive the request (R-001 §B.5).
  - `billing/module.py` already publishes `billing.service_factory` with the comment
    "consumed by risk/ingestion before starting a review" — the intended wiring was
    designed and never connected (R-004 §A.1).
  - `authorize_review(workspace_id)` has no opportunity id, so it cannot implement
    the doc's own "addendum re-processing is free" rule (R-004 §A.3).
  - `specs/modules/billing.md` declares three events (`plan_activated`,
    `payment_applied`, `paywall_hit`) and a per-org advisory lock that do not exist
    in the code (R-004 §A.4–A.5).
  - `User.phone` and `User.google_sub` columns already exist and are unused —
    the anti-abuse work in R-015 §C.2 needs no migration for them.
  - `session.tsx` has no three-state loading status, so a signed-in user renders as
    signed-out on every reload (R-010 §B.7).

### Next

- **Gate 1 — TS-084, TS-085, TS-086, TS-093, TS-094, TS-095.** Close the three
  cross-tenant leaks, remove the reset-token echo, harden RLS (FORCE + WITH CHECK +
  missing tables + post-commit rebinding) behind a new Postgres CI job, revoke
  sessions on password reset, rate-limit auth, stream uploads.
  Exit: a cross-tenant read attempt is covered by an automated test.
- **Gate 2 — TS-087, TS-088 first.** Nothing else in billing has value until the
  paywall is enforced in the review path and the free tier stops emitting clean
  paid-grade exports. Then TS-089/TS-091 for a thin but complete paid path.
- **Consider pulling forward:** the acceptance-rate half of TS-108 (the Phase-1 kill
  gate is unmeasurable today despite the data already being recorded), and the
  frontend test stack from TS-104 (TS-092 is the task most in need of tests and
  there is currently no way to write one).

### Done — 2026-07-26 (real web validation + invitation fix: TS-080..TS-081)

- **TS-080** — Ran end-to-end browser validation against the local frontend + backend:
  - UI signup (`http://localhost:3000/login`) created a user, default workspace, and
    navigated to `/opportunities`.
  - Real `fetch` calls from the browser verified workspace CRUD, project CRUD,
    project-member listing, and super-admin 403 rejection.
- **TS-081** — Fixed `POST /api/auth/invitations/{token}/accept` raising
  `TypeError: can't compare offset-naive and offset-aware datetimes` on SQLite.
  `accept_invitation` now normalizes a naive `expires_at` to UTC before comparing.
  Added `test_invitation_flow` to `tests/test_auth_module.py`.

### Done — 2026-07-26 (password reset: TS-082)

- **TS-082** — Added forgot-password and reset-password flow:
  - New `password_resets` table with 15-minute single-use tokens stored as SHA-256 hashes.
  - `POST /api/auth/forgot-password` returns `ok` even for unknown emails to prevent
    enumeration; returns the raw token in dev/test until real email delivery is wired.
  - `POST /api/auth/reset-password` validates the token, enforces an 8-character minimum,
    hashes the new password with argon2id, and marks the token used.
  - Frontend: `/forgot-password` and `/reset-password?token=...` pages, plus a link
    from `/login`.
  - Added regression tests for reset, reuse, and expired-token rejection.

### Done — 2026-07-26 (workspace/project tenant refactor + super admin: TS-074..TS-078)

- **TS-074** — Spec for the workspace/project tenant refactor + super admin:
  `specs/workspace-and-admin-refactor.md`.
- **TS-075** — New auth data model: removed `org`/`org_members`, added `User`,
  `Workspace`/`WorkspaceMember`, `Project`/`ProjectMember`, `Invitation`, global
  `is_superadmin` flag, and `mfa_method`/`mfa_phone` on `User`.
- **TS-076** — Renamed `org_id` → `workspace_id` across all modules, RLS helpers,
  and `core.db`; regenerated the migration chain as
  `migrations/versions/e26e85245237_workspace_tenant.py` with workspace-scoped
  RLS policies for PostgreSQL.
- **TS-077** — Workspace/project CRUD, sharing/invites, MFA method selection, and
  super-admin endpoints:
  - `POST/GET /api/auth/workspaces`
  - `POST/GET /api/auth/workspaces/{id}/members`
  - `POST/GET /api/auth/workspaces/{id}/projects`
  - `POST/GET /api/auth/projects/{id}/members`
  - `POST /api/auth/invitations` + `POST /api/auth/invitations/{token}/accept`
  - `POST /api/auth/mfa/enroll` + `POST /api/auth/mfa/verify`
  - `GET/POST /api/auth/admin/*` super-admin routes.
- **TS-078** — Updated `tests/test_auth_module.py` and frontend `api.ts` / `session.tsx`
  / `app/login/page.tsx` for `workspace_id`; verified `ruff`, `pytest`, `npm run build`,
  and `alembic upgrade head && downgrade base` all pass.
- Updated `README.md`, `docs/deployment.md`, `specs/modules/auth.md`, and
  `tasks/backlog.md` to reflect the new workspace/super-admin model.

### Done — 2026-07-26 (spec audit follow-up: Sprints 0–2)

- **TS-058..TS-070** — Spec-audit follow-up task IDs and `tasks/spec_audit_tracker.md` created.
- **TS-062** — `analytics` and `comparison` now publish `*.service_factory` capabilities
  via `module.py`, and their routers consume the factory when available.
- **TS-063** — Fixed route wording in `specs/modules/timeline.md` and `specs/modules/crossref.md`
  to match the implemented router paths.
- **TS-058..TS-061** — Added missing module specs:
  - `specs/modules/findings.md` (shared findings store and contract).
  - `specs/modules/export.md` (Bid Review Pack export with review gate).
  - `specs/modules/health.md` (health/capabilities endpoint).
  - `specs/modules/notifications.md` (deadline-digest sender abstraction).
- **TS-059 (code)** — `export` now publishes `export.service_factory` and the router
  consumes it, matching the pluggable pattern.
- **TS-064..TS-066** — Aligned `ingestion`, `risk`, and `drafting` public-interface
  specs with the capabilities and routes actually implemented.
- **TS-067** — Added tests for `export`, `health`, and `notifications`:
  - `test_export.py` covers review-gated XLSX export and bad-format handling.
  - `test_health.py` covers the `/api/health` module/capability report.
  - `test_notifications.py` covers deadline alert thresholds and `ConsoleSender`.

### Done — 2026-07-26 (Sprint 4 complete + TS-071)

- **TS-068** — Implemented `ingestion.doc_chunks` table + migration and the
  `ingestion.doc_text` capability (`DocTextService`), plus `GET /api/ingestion/documents/{id}/text`.
- **TS-070** — Added `invoices` table + migration, `GET /api/billing/invoices`, and the
  `billing.record_usage` capability; Razorpay `order.paid`/`subscription.charged` now generate a paid invoice.
- **TS-069** — Implemented assistant chat sessions (`chat_sessions` + `chat_messages`),
  history endpoints, and SSE `/api/assistant/sessions/{id}/stream`.
- **TS-071** — Implemented Sign in with Apple backend skeleton: `users.apple_id`,
  `GET /api/auth/apple/authorize`, `POST /api/auth/apple/callback`, client-secret
  generation, and id_token verification. Disabled until Apple Developer credentials
  are configured (`TS_APPLE_*`).
- Added integration tests for billing, ingestion doc chunks, assistant sessions, and
  Apple sign-in.

### Done — 2026-07-26 (Devin rules: TS-073)

- **TS-073** — Created `.devin/rules/*.mdc` and `DEVIN.md` so Devin follows the same
  mandatory workflow, architecture, and spec conventions as Cursor/Claude. Updated
  `CLAUDE.md` and `.cursor/rules/00-workflow.mdc` to reference the Devin rules.

### Done — 2026-07-26 (deployment helpers: TS-072)

- **TS-072** — Added `.env.local`, `.env.dev`, `.env.prod`, `scripts/run.sh`, and
  `docs/deployment.md` with local / Docker / prod setup instructions.

### Next

- TS-079 — Wire real email/SMS delivery for `email`/`sms` MFA methods, OTP codes, and
  password-reset links (replace dev-only token return).
- TS-036 — Complete Google OIDC login (`/api/auth/google/callback`) and live
  messaging-provider credentials.
- Configure Apple Developer credentials and test end-to-end Sign in with Apple.

### Done — 2026-07-26 (session 23 continued: TS-057)

- **TS-057** — Internal Accuracy Dashboard:
  - New `analytics` module with `GET /api/analytics/accuracy` (admin/owner only).
  - Aggregates review outcomes from the shared findings table and produces
    per-pattern and per-source precision proxies, false-positive counts, and
    a most-rejected patterns list.
  - Recall and true false negatives are reported as `null` because they require
    an external golden-label set; the shape is ready for that feed.
  - Added `FindingStore.list_for_org` to support org-wide analytics without
    direct table imports.
  - `specs/modules/analytics.md` and `tests/test_analytics.py` added.

### Next

- Phase 1 accuracy gate: validate the Bid Readiness score and weights against a
  real tender set and QS sign-off; no Phase-2 expansion until ≥70% QS acceptance.
- Golden-label import for true precision/recall in `analytics` (TS-057 follow-up).

### Done — 2026-07-26 (session 23 continued: TS-050)

- **TS-050** — Tender Comparison:
  - New `comparison` module with `GET /api/comparison/opportunities` returning a
    portfolio ranking table.
  - Aggregates per-opportunity counts (risk by severity, qualification gaps,
    BOQ defects, standard violations), earliest submission deadline, and the
    latest `bid_decision` score/recommendation from `drafting`.
  - Deterministic priority ranking: `proceed` > `proceed_with_conditions` >
    `do_not_proceed` > none, then bid score desc, critical risk asc,
    days-to-submission asc.
  - `specs/modules/comparison.md` and `tests/test_comparison.py` added.

### Done — 2026-07-26 (session 23 continued: TS-053 + TS-051)

- **TS-053** — Clause Cross-Reference:
  - New `crossref` module with `CrossRefService` and routes
    `GET /api/crossref/opportunities/{id}?q=...&limit=...`.
  - Token-level search across every clause in an opportunity, ranked by overlap,
    with provenance (document kind/filename, clause ref, heading, page, 300-char preview).
  - `specs/modules/crossref.md` and `tests/test_crossref.py` added.

- **TS-051** — Clause Change Detection:
  - `POST /api/crossref/opportunities/{id}/diff?document_id=...` compares two
    versions of a document and returns `added`, `removed`, and `changed` clauses.
  - Uses explicit `supersedes` chains when provided; falls back to the two most
    recent uploads of the same document kind.
  - Clause matching is deterministic: keyed by `clause_ref`, with text similarity
    on normalised clauses.
  - Wired into the ingestion clause store; no hard cross-module imports.

### Done — 2026-07-26 (session 23 continued: TS-048 + TS-049 + TS-052 + TS-054 + TS-055 + TS-056)

- **TS-052** — Tender Timeline:
  - New `timeline` module with `TimelineService` and routes
    `/api/timeline/opportunities/{id}/timeline` and `.ics` export.
  - Expanded `ingestion.deadlines` keywords to extract tender publication,
    technical/financial opening, EMD validity, BG submission, contract signing.
  - Timeline normalizes raw kinds to a canonical milestone vocabulary, includes a
    `tender_published` synthetic fallback, and sorts dated events.
  - `specs/modules/timeline.md` and `tests/test_timeline.py` added.

- **TS-049** — Qualification Compliance Matrix:
  - New `qualification` module with `QualificationService` and routes
    `GET/POST /api/qualification/opportunities/{id}`.
  - Deterministic extraction of 8 eligibility criteria (minimum turnover,
    similar project experience, equipment, engineer, certifications, EMD,
    bid security, experience years) with source quote + page.
  - Writes `qualification_gap` findings to the shared findings store; missing
    criteria are `not_met` (severity `high`), found criteria are `unknown`
    (severity `medium`) pending org evidence.
  - `specs/modules/qualification.md` and `tests/test_qualification.py` added.

- **TS-048** — Bid / No-Bid Recommendation:
  - Extended `drafting` to generate a `bid_decision` artifact from accepted
    findings only.
  - Deterministic score (0–100) with transparent weights over `risk_clause`,
    `qualification_gap`, `boq_defect`, and `standard_violation` findings.
  - Weights default to a documented table and can be overridden through the
    rule-pack playbook (`default_contractor.bid_decision_weights`).
  - Output: score, strengths, concerns, recommendation
    (`proceed` / `proceed_with_conditions` / `do_not_proceed`), and conditions.
  - Gated by review: no `proposed` or `needs_clarification` findings allowed.
  - Updated `specs/modules/drafting.md` and `tests/test_drafting.py`.

- **TS-056** — Organization Standards Enforcement:
  - Extended `standards` with `OrgCommercialStandard` (org-scoped, RLS) for
    per-org policy thresholds.
  - New routes:
    `GET/PUT/DELETE /api/standards/commercial/{key}` and
    `POST /api/standards/opportunities/{id}/check`.
  - `check_violations` extracts numbers from accepted findings (percent, days,
    amount) and returns violations; the endpoint persists `standard_violation`
    findings through the shared findings store.
  - `drafting` `bid_decision` consumes `standards.commercial_service_factory`
    and includes standard violations in score/concerns.
  - Updated `specs/modules/standards.md` and added `tests/test_standards.py`.

- **TS-054** — Risk Explainability:
  - `Finding` contract and `findings` table now carry an `explanation` JSON field.
  - `RiskPattern` schema accepts `industry_reason`; all five `in-works` India
    patterns updated with real, domain-appropriate reasons.
  - `risk.engine.run_pattern` builds an explanation object for every finding
    (`matched_pattern`, `evidence_quote`, `industry_reason`, `suggested_review`,
    `absence` flag).
  - `risk` and `review` API responses now include `explanation`.
  - Tests updated: `test_risk.py` asserts explanation shape.

- **TS-055** — Structured Review Outcomes:
  - `ReviewStatus` expanded: `accepted`, `edited`, `rejected`, `false_positive`,
    `needs_clarification`.
  - `findings` table and contract gain `review_reason`.
  - Review endpoint accepts `decision` + `review_reason`; audit logs both.
  - Export gate now blocks on `proposed` **and** `needs_clarification`.
  - Tests added for `false_positive`/`needs_clarification` and gate behavior.

- Migration `0012_review_explain.py` adds `review_reason` and `explanation`
  columns to `findings`; Alembic up/down verified.
- `specs/modules/risk.md` and `specs/modules/review.md` updated in the same change.
- `tasks/backlog.md` / `tasks/phase15_tracker.md`: TS-052, TS-054, TS-055 marked `done`.

### Done — 2026-07-26 (session 23: Phase 1.5 bid-decision extensions planning)

- Product requirements and roadmap for **Phase 1.5 — Bid-Decision Extensions**
  (`docs/TenderShield_Phase15_Extensions.md`). Maps the 10 requested
  capabilities to the existing modular architecture, defines domain/market
  rationale, priority, sprint sequencing, acceptance criteria, and module mapping.
- Task backlog updated with sequential IDs **TS-048…TS-057** for Bid / No-Bid
  Recommendation, Qualification Matrix, Tender Comparison, Clause Change
  Detection, Tender Timeline, Clause Cross-Reference, Risk Explainability,
  Structured Review Outcomes, Organization Standards Enforcement, and Internal
  Accuracy Dashboard (`tasks/backlog.md`).
- Progress tracker created (`tasks/phase15_tracker.md`) with sprint themes,
  acceptance gates, and blockers; Bid Decision Intelligence is the capstone
  feature with Sprint 0–2 inputs (explainability, review outcomes,
  qualification, timeline, org standards) sequenced first.

### Done — 2026-07-24 (session 22: org-custom standards + researched notice figures)

- **TS-047** — the third standards layer: a firm can publish **its own** notice
  regimes that either **prevail** over or run **side by side** with the
  universal + regional rule-pack standards (Doc §10 custom playbooks).
  - New pluggable `standards` module (backend): `org_notice_standards` table
    (org-scoped + RLS, one row/org), `GET/PUT/DELETE /api/standards/notice`
    (read = viewer, write = admin), boundary validation (bad mode → 400,
    duplicate keys → 409). Publishes `standards.org_notice_provider`.
  - `baseline` now merges three layers — universal → regional → org — when
    building the notice register + gaps. `prevail` overrides matching regimes
    (keeping base fields the org omits); `side_by_side` appends. Org regimes are
    tagged `origin="org"`; an expected org regime absent from a contract becomes
    a gap. Migration `0011`.
  - Frontend: `/standards` editor (mode toggle + editable regime rows), nav link,
    and a "your standard" badge on org-origin gaps in the Handover tab.
- **Researched, cited notice figures** (you asked me to do the QS research):
  the universal/India packs now carry real, sourced windows — **FIDIC 2017
  cl.20.2** (28-day notice / 84-day detailed claim), **NEC4 cl.61.3** (8-week /
  56-day compensation-event bar), **MSMED Act 2006 s.15** (45-day statutory
  payment cap), plus **CPWD cl.10CC** escalation and the hindrance-register EOT
  practice — with a `references.md`. All remain `confidence: unvalidated` pending
  a QS sign-off (Doc §14).
- Verified live (UI): the register shows the MSMED 45-day and CPWD 10CC figures
  from the India overlay, and a firm's own "Site handover" regime flowing through
  as an org-badged gap.
- 113 backend tests passing (7 new), ruff clean, frontend builds clean.

### Done — 2026-07-24 (session 21: layered contract-standards — universal-first, flexible)

- **TS-046** — the flexibility spine the geographic roadmap rides on: **layered
  notice standards** as versioned data (`rulepacks/in-works/notice_standards/`).
  - `base.yaml` (scope `universal`) defines the contract-form-agnostic notice
    regimes (claim, variation, EOT, payment, defect, termination, dispute) with
    typical windows, `expected` flags and keywords; `india.yaml` (scope `IN`) is
    an **overlay** that tightens the claim window (28→15d), retimes EOT to the
    hindrance-register practice, and adds the India-only escalation/star-rate
    regime.
  - `RulePackLoader.notice_standard(pack_id, region)` merges universal + regional:
    a regional category overrides the base **only in the fields it explicitly
    sets** (`exclude_unset`, so an omitted `expected` keeps the base value —
    this was a real bug, fixed), region-only categories append. **Adding a new
    market or an unexpected clause type is now a YAML file, not a code change** —
    the exact seam the future GCC (FIDIC) / UK (NEC/JCT) packs plug into.
  - The `baseline` notice register is now **standards-aware**: each extracted
    window is classified into a semantic category, and every *expected* regime
    with no window in the contract is flagged as a **gap** (the notice analogue
    of risk absence detection) — deterministic, no LLM. Region + gaps are frozen
    into the sealed snapshot and shown in the handover pack. Degrades to
    extraction-only when `rulepacks` is disabled.
  - Frontend Handover tab: "standard: universal + IN" badge, semantic categories,
    and an amber "expected notice regimes not found" panel.
  - Verified live (UI): a claims-only contract correctly flags Variation, EOT
    (hindrance-register, 15d), Payment, Termination and Price-escalation (30d) as
    gaps — the India overlay visibly in effect.
- 108 backend tests passing (3 new), ruff clean, frontend builds clean.

### Done — 2026-07-24 (session 20: Phase-2 baseline lock — end to end)

- **TS-041** — new pluggable `baseline` module (backend), the first Phase-2
  feature. At award it freezes the reviewed commercial state into an immutable,
  hash-sealed snapshot so tender knowledge survives handover (Doc §0.1 P2):
  - **Hash-sealed freeze** — SHA-256 over the canonical snapshot (accepted/edited
    findings with verbatim provenance + confirmed deadlines + opportunity meta).
    Append-only versions; `verify` recomputes the hash and reports tamper
    (the doc's "baseline freeze (hashes)" requirement).
  - **Freeze gate** — sealing is blocked until the `review` gate is satisfied
    (Doc §11.4), reusing the professional-liability spine; refused when `review`
    is disabled.
  - **Deterministic notice-rule register** — regex over the accepted findings
    **and the segmented contract clauses** extracts contractual notice windows
    ("within 14 days", "28 days' notice"), normalised to days, with page
    citations. No LLM (Doc §4) — populates from real contract text even with no
    API key. These seed the Phase-3 time-bar countdowns.
  - **Award-vs-tender delta** — diffs the latest tender seal against the latest
    award seal (added / dropped / changed findings). Deterministic.
  - **Commercial handover pack** — sealed hash, critical/high obligations, notice
    register and confirmed-deadline calendar from the latest baseline.
  - Cross-module only via capabilities (`findings`/`review`/`ingestion`); the app
    boots and Phase-1 flows pass with `baseline` disabled. Migration `0010`,
    org-scoped + RLS on PostgreSQL. 8 new tests (freeze gate, seal, verify,
    compare, handover, live-clause notice extraction).
- **TS-042** — frontend **Handover** tab on the opportunity workbench: freeze
  tender/award baselines (gated on review), sealed-baseline list with hashes,
  notice-rule register with citations, award-vs-tender delta, and the handover
  pack. Typed `baseline` client methods added.
- Verified end to end against a live server + browser: freeze refused before
  review (403), sealed v1 (64-char hash), `verify` intact, notice register
  extracting the 14-day and 28-day windows from clause text with p3 provenance,
  and the rendered Handover tab.
- 106 backend tests passing; ruff clean; frontend builds clean.
- **Phasing note:** the doc gates P2 behind the Phase-1 accuracy gate (§10);
  this ships as a config-flagged, fully decoupled module so it does not disturb
  Phase-1. The accuracy gate (5 real tenders + QS review) remains the real gate
  before P2 is *promoted*.

### Done — 2026-07-24 (session 19: in-app Help page + honest QS-lifecycle scope)

- **TS-040** — new static Help page at `/help` (`frontend/app/help/page.tsx`),
  linked from the header nav:
  - an 8-step **how-to-use** walkthrough (create workspace → open opportunity →
    upload full pack → confirm deadline wall → run risk review → run BOQ
    assurance → review/accept findings → generate & export);
  - the **rules it never breaks** (numbers from code not AI, every finding cited
    & quote-verified, human approves before export, data isolated per workspace);
  - an honest **QS-lifecycle coverage table** — states plainly that TenderShield
    owns the **pre-bid slice** (risk review, deadline extraction, BOQ arithmetic
    assurance, scope-gap detection, bid-decision artifacts) and deliberately does
    **not** do estimating, drawing take-off, BOQ authoring, interim valuations, or
    variations/claims/final account;
  - a not-legal / not-QS-certification **disclaimer** (Doc §11.4) reinforcing that
    findings are prompts for a qualified human, which is why the accept/reject
    step exists.
- **Scope framing corrected (same session):** the coverage table no longer
  flattens roadmap items into "not covered." It now uses three buckets —
  **Covered now** (Phase-1 pre-bid slice), **On the roadmap** (baseline lock,
  change/variation inbox + notice drafts, contractual time-bar engine incl.
  FIDIC 20.1 / NEC CE, cross-tender outcome graph — all from Doc §0.1/§1.2), and
  **Not ours** (takeoff, BIM/clash, live pricing, CPM, legal opinions — Doc §0.2).
  Added a "where it goes beyond typical QS tools" section (reads the contract,
  tracks the clock, playbook deviation, cross-tender learning, inspectable
  provenance, deterministic numbers). The AI assistant is not advertised since
  it is hidden from users.
- Spec `specs/frontend.md` updated (structure, B8, A2) to record the Help page,
  the hidden assistant, and human-label/typography decisions from session 18.
- Frontend builds clean; `/help` prerenders as static content.

### Done — 2026-07-24 (session 18: UI polish — hide assistant, human labels, fonts)

- **AI assistant hidden from users:** the Assistant tab, chat state, and handler
  removed from the opportunity workbench — user-facing tabs are now Overview /
  Risks / BOQ / Artifacts. (The backend module still exists; disable it fully by
  omitting `assistant` from `TS_ENABLED_MODULES`.)
- **No raw identifiers on screen:** new `lib/labels.ts` maps every internal code
  to a proper label — categories (`grand_total` → "Grand-total mismatch",
  `blank_rate` → "Blank rate", `ld` → "Liquidated damages", …), review status,
  deadline kinds, artifact kinds, opportunity status, doc kinds. Board + detail
  render through it; the BOQ tab label shows "BOQ" (not "Boq").
- **Proper typography:** app-wide Inter → system-UI font stack in Tailwind +
  legibility/feature settings in globals (drop in `next/font` Inter for an exact
  self-hosted face when building with network).

Frontend builds clean; backend unaffected (98 tests still passing).

### Done — 2026-07-23 (session 17: no-AWS scanned-table path)

- **TS-039** — the hard scanned-table BOQ case, **without AWS**: `RapidTableProvider`
  (rapid-table SLANet ONNX + RapidOCR, offline) reconstructs a table from a
  scanned/image BOQ page; a dependency-free HTML→rows parser + `scanned_boq_csv`
  maps it to canonical CSV; wired as the BOQ-upload fallback (`ingestion.scanned_boq_csv`,
  only when `TS_OCR_ENABLED`). The HTML→CSV conversion is unit-tested; the model
  downloads once on first use (blocked in this sandbox, so the recognition step is
  not sandbox-verified — works on a normal machine).
- **AWS is no longer required anywhere.** Textract removed as a dependency;
  TS-033 is now just tus resumable upload. Docs corrected. 99 tests passing.

### Done — 2026-07-23 (session 16: OCR + PDF table reading — no cloud)

- **TS-038** — real OCR + table extraction without AWS:
  - **pdfplumber** reads BOQ tables straight out of digital PDFs; new
    `POST /api/boq/opportunities/{id}/upload` accepts PDF/XLSX/CSV, detects the
    BOQ table, maps headers to canonical columns, and runs the deterministic
    checks. Tested end-to-end (duplicate + arithmetic caught from a PDF table).
  - pluggable **`OcrProvider`**: `RapidOcrProvider` (RapidOCR — ONNX, bundled
    models, **fully offline**; PyMuPDF rasterizes pages) reads scanned/image
    PDFs; `NullOcrProvider` default. Verified live: a text-free image PDF OCR'd
    back to its exact text.
  - **honest degradation** (Doc §12.4): a scanned PDF with no text layer is
    flagged `ocr_status="needs_ocr"` when OCR is off, instead of silently
    ingesting blank/garbage text. Enable with `TS_OCR_ENABLED=true` +
    `pip install -e ".[ocr]"`.
  - `file_to_boq_csv` + `ingestion.ocr` published as capabilities so BOQ reads
    tables without importing ingestion. OCR test skips where the `ocr` extra
    isn't installed (CI stays light).

Test suite: 98 passing, ruff clean; architecture test green.

### Done — 2026-07-23 (session 15: production hardening — implementable-now slice)

Built the parts of the hardening list that need no live credentials:

- **TS-026** — real multipart upload + text extraction: `extract.py` (PDF via
  pypdf, XLSX via openpyxl, CSV/text), `LocalStorage` (per-org, sha256), and
  `POST …/upload` that feeds the existing classify/segment/deadline pipeline.
  Tested end-to-end with a generated PDF (classified NIT, deadline extracted).
- **TS-030** — PDF export (reportlab): completes DOCX/PDF/XLSX; gated + stamped;
  `?format=pdf` returns a real `%PDF-`.
- **TS-029** — GST invoice computation (`gst.py`): CGST/SGST intra-state vs IGST
  inter-state (SAC 998313), sequential gap-free numbering. Pure + tested.
- **TS-028** — TOTP MFA (`mfa.py`, pyotp): enroll (secret + otpauth URI) +
  verify; `users.mfa_totp_secret` column (migration `0009`); `/auth/mfa/enroll`
  + `/verify`. Enforcement-at-login is a follow-up.
- **TS-027** — `notifications` module: pluggable `Sender` (ConsoleSender dev
  backend) + pure deadline-digest logic (alert windows 7/3/1/0 days). SES/MSG91
  adapters plug in behind the same interface (TS-035).
- **TS-031** — deploy scaffolding: `docker-compose.yml` (Postgres + backend +
  frontend), backend/frontend `Dockerfile`s, `.env.example`.
- **TS-032** — frontend CI job (npm ci + build) added to GitHub Actions.

Still needs live accounts (interfaces are built; see backlog TS-033…TS-037):
Textract OCR, tus resumable, Celery/Redis, SES/MSG91 send, Google OIDC/phone
OTP, Stripe. Migrations 0001→0009. **95 tests passing, ruff clean.**

### Handoff snapshot (for local takeover)

**All Phase-1 backlog tasks (TS-001…TS-025) are `done`.** 11 feature modules;
migrations 0001–0008; **88 backend tests passing, ruff clean; frontend builds
clean.** Full local run steps, env vars, and the end-to-end click-path are in
`README.md`. What remains is production infra (OCR/uploads/Postgres/payments/
alerts) and the non-code domain-accuracy gate (real tenders + QS + an
`ANTHROPIC_API_KEY`) — see "What's left" in `README.md` and below.

### Done — 2026-07-23 (session 14: assistant — the last module)

- **TS-024** — `assistant` module (Doc §8), grounded + tool-first:
  - pure `tools.py` (list_deadlines, filter_findings, missing_docs,
    rulepack_lookup) reading only the org's own data via capabilities.
  - `AssistantService` routes recognized intents (deadlines / findings by
    severity / missing docs) to **deterministic, cited answers that work with
    no API key**; off-topic questions are **refused** (grounded-only).
  - free-form questions use an injected `AnthropicAgent` only when
    `ANTHROPIC_API_KEY` is set, answering strictly from tool results.
  - `POST /api/assistant/chat`; frontend **Assistant tab** (ask box + grounded
    replies). Tests cover the deadline/findings/missing-doc intents + refusal.
- README rewritten as a local-takeover guide (run steps, env vars, click-path).

Test suite: 88 passing, ruff clean; frontend builds clean.

### Done — 2026-07-23 (session 13: BOQ write-through + BOQ workbench)

- **BOQ write-through** — `BoqRunner` parses an uploaded workbook (CSV), runs
  the deterministic engine + scope-gap checklists (spec text pulled from the
  opportunity's clauses via ingestion), and **persists defects to the shared
  findings register** (`producer='boq'`) via the findings store capability.
  `POST /api/boq/opportunities/{id}/run`.
- BOQ defects now flow through the same pipeline as risk findings: they count
  toward the review gate and appear in the exported Bid Review Pack.
- **Frontend BOQ tab**: "Load sample BOQ & check" runs the engine and lists the
  defects (arith / grand-total / duplicate / blank-rate, all "deterministic
  check"). Risks vs BOQ findings are split by `producer` in the UI.
- **TS-013a complete** — all per-module models + migrations (0001–0008) done;
  risk + BOQ persist findings; review/drafting/export/billing wired.

Test suite: 84 passing, ruff clean; frontend builds clean. Verified live.

### Done — 2026-07-23 (session 12: billing + export renderer)

- **TS-022** — `billing` module (Doc §7, §15):
  - pure `plans.py` (free→exhausted, paygo requires-payment, pro/scale quotas;
    money in paise) + `webhook.py` (HMAC-SHA256, constant-time) — unit-tested.
  - `usage_events`, `payment_log` (append-only ledger), `webhook_events`
    (idempotency) + migration `0008`.
  - **webhook is the only truth**: it logs receipt *before* trusting, verifies
    signature, is idempotent by event id, and only then activates a plan /
    credits a paid review; a tampered signature → 400 + a `failed` ledger row.
  - free-tier metering (`authorize-review` → free_first_review, then 402
    `free_exhausted`); reads/updates org plan via a new `auth.orgs_factory`
    capability (billing never imports auth).
- **TS-023** — `export` module: Bid Review Pack renderer (Doc §1.1(8), §11.4):
  - pure `render.py` → **XLSX** (openpyxl) + **DOCX** (python-docx), each
    carrying the "Prepared with TenderShield · reviewed … · pack …" stamp.
  - **export gate enforced**: blocked (403 `review_incomplete`) until
    `review.gate` opens; consumes review/findings/drafting/ingestion/rulepacks
    via capabilities only.
  - frontend Artifacts tab: Export .docx / .xlsx buttons (authenticated blob
    download), enabled only when the gate is open.
  - PDF (WeasyPrint) deferred — heavy system deps.

Test suite: 83 passing, ruff clean; frontend builds clean. 0001→0008 verified.

### Done — 2026-07-23 (session 11: drafting — artifacts + the three validators)

- **TS-020** — `drafting` module (Doc §6.5), the anti-hallucination spine:
  - **three validators** (pure, `validators.py`): reject invented quotes,
    uncited clauses, and invented numbers against a `FactTable` built only from
    accepted findings. Unit-tested for each failure mode + the passing case.
  - deterministic `generator.py`: assembles the **clarification letter** and
    **assumptions & exclusions register** from accepted findings (facts injected,
    structure built) — validators pass by construction, no LLM key needed; an
    LLM polish pass would be subject to the same validators.
  - `Artifact` model + migration `0007` (org-scoped, RLS; versioned,
    `UNIQUE(opportunity, kind, version)`); 0001→0007 verified up+down.
  - `DraftingService.generate` pulls accepted findings via the findings store
    capability, validates, and writes a NEW version (never mutates); refuses
    with `no_accepted_findings` until review has accepted something.
  - endpoints: generate / list / get; **frontend Artifacts tab** — generate
    (disabled until the export gate opens) and read the versioned letter/register.

Test suite: 74 passing, ruff clean; frontend builds clean.

### Done — 2026-07-23 (session 10: review workbench + audit + export gate)

- **TS-021** — `review` module, the professional-liability spine (Doc §11.4):
  - accept/edit/reject each finding — updates the review columns via the
    findings store capability (never imports findings); requires `reviewer`
    role; bad decision → 400, unknown finding → 404.
  - append-only `audit_log` table + migration `0006` (org-scoped, RLS on
    Postgres; 0001→0006 verified up+down); every decision writes an audit row.
  - **export gate**: `review.gate` returns `export_allowed` only when there are
    findings and none remain `proposed` — the block that stops export before a
    human has reviewed. Published as `review.service_factory` for drafting/export.
  - `GET queue` / `POST findings/{id}` / `GET gate` / `GET audit` endpoints.
  - **Frontend:** Risks tab now shows an export-gate banner and Accept/Reject
    buttons per finding; reviewed findings show their status.
  - Note: `BigInteger` PK uses a SQLite `Integer` variant so autoincrement works
    in tests while staying BIGSERIAL on Postgres.

Test suite: 68 passing, ruff clean; frontend builds clean.

### Done — 2026-07-23 (session 9: findings persistence)

- **TS-013a (findings slice)** — a new pluggable `findings` module owns the
  shared `findings` table (Doc §3.2): SQLAlchemy model + migration `0005`
  (org-scoped, RLS on Postgres; 0001→0005 verified up+down) + `FindingStore`.
  - Producers write via the `findings.store_factory` capability, scoped by a
    `producer` column so a re-run of one producer replaces only its own rows and
    never disturbs another's (unit-tested for idempotency + producer isolation).
  - `risk` now persists its findings on run (still returns them too) and gained
    `findings` as a soft dep — resolved lazily, so risk still runs (in-memory)
    if the findings module is disabled.
  - `GET /api/findings/opportunities/{id}` lists the register, severity-sorted.
  - **Frontend:** the Risks tab now reads the persisted register (with
    review-status), loaded on open and after a run.
  - No module imports another's models — the table stays pluggable behind the
    store capability + the core `Finding` contract.

Test suite: 65 passing, ruff clean; frontend builds clean.

### Done — 2026-07-23 (session 8: deadline extraction + deadline wall)

- **TS-015** — deadline extraction (Doc §6.2), the <3-minute promise:
  - pure `deadlines.py` — deterministic date parsing (DD/MM/YYYY, "15 Aug 2026",
    etc.) with keyword→kind classification (submission/pre-bid/clarification/
    validity/EMD/completion), `[pN]` page tracking, and noise control (bare
    dates with no deadline keyword are skipped). Dates are never invented; each
    carries its verbatim source line + page. LLM/relative-formula resolution are
    follow-ups — the deterministic pass already lights up the wall with no key.
  - `Deadline` model + migration `0004` (org-scoped, RLS on Postgres); also adds
    `submission_due`/`clarification_due` to `opportunities`. 0001→0004 verified.
  - extraction runs on document upload; sets the opportunity's `submission_due`
    from the earliest submission date; `GET …/deadlines` + confirm-chip endpoint.
  - **Frontend:** deadline wall on the opportunity overview (countdown colouring
    red<3d/amber<7d, page citations, confirm chips) and the board countdown
    badge now lights up from `submission_due`.
  - Verified full-stack live: uploading a NIT extracted bid submission (2d, red),
    pre-bid and clarification (1d) with page citations; board shows "2d to
    submission" in red. Screenshots captured.

Test suite: 62 passing, ruff clean; frontend builds clean.

### Done — 2026-07-23 (session 7: frontend skeleton — the UI)

- **TS-025** — Next.js 15 + TypeScript + Tailwind app (`frontend/`), Doc §9:
  - landing page (countdown-wall design + sample risk register), auth
    (signup/login), opportunity **board** (countdown badges: red <3d, amber <7d),
    and opportunity **detail** (document checklist + risk workbench tabs);
  - typed API client (`lib/api.ts`), session context (access token in memory +
    localStorage mirror; production uses httpOnly refresh cookie per Doc §5);
  - tri-state provenance badges (extracted fact / deterministic check / AI
    suggestion) as components, not copy (Doc §11.4);
  - `next build` clean (6 routes); bumped Next to 15.5.x (patched CVE).
- **Backend for the SPA:** `GET /api/ingestion/opportunities` (org-scoped list)
  + CORS middleware (`TS_CORS_ORIGINS`, configurable).
- **Verified full-stack, live:** ran FastAPI + Next together and drove a real
  signup → create two opportunities → upload a document flow with a headless
  browser. Screenshots captured: the uploaded doc classified as NIT and the
  missing-doc checklist flagged GCC/BOQ — all through the real API with RLS
  org-scoping (a second org's board is isolated, covered by a new test).

Test suite: 58 passing, ruff clean. Frontend builds clean.

### Done — 2026-07-23 (session 6: clause segmentation + risk engine)

- **TS-016** — clause segmentation (extends ingestion): pure `segment.py`
  (`segment_clauses` — header detection for Clause/GCC/SCC, `[pN]` page
  tracking, cross-ref extraction), `Clause` model + migration `0003_clauses`
  (org-scoped, RLS on Postgres; 0001→0002→0003 chain verified up+down).
  Documents are segmented on registration; `GET …/clauses` lists them.
- **TS-017** — `risk` module, the pattern engine (Doc §6.3):
  - `severity.py` — **deterministic** severity via a sandboxed AST evaluator
    over the pack's `severity_rule` strings (severity keywords resolve to
    themselves, facts from context, missing → 0, malformed → safe default).
    Severity never comes from the LLM.
  - `engine.py` — anchor retrieval, quote verification (normalized + fuzzy
    ≥0.85), absence detection, finding assembly. Pure over dicts.
  - `classifier.py` — injected LLM boundary: `NullClassifier` (no key → absence
    detection still works) / `AnthropicClassifier` (JSON-only, temp 0, tender
    text as untrusted data). Never returns severity.
  - `RiskService` consumes ingestion + rulepacks purely via registry
    capabilities; `POST /api/risk/opportunities/{id}/run`.
  - **Ran live** on the synthetic tender: correct deterministic severities
    (LD/escalation/termination critical, defect high), quotes verified against
    clause text, and a deliberately-wrong quote flagged unverified.
  - Fixed the synthetic payment clause to 120 days (unambiguous `high`); the
    "is 90 days high or medium?" boundary is a QS-validation calibration item.

Test suite: 57 passing, ruff clean.

### Done — 2026-07-23 (session 5: ingestion module + auth boundary hardening)

- **Auth boundary refactor** — the generic request dependencies (`get_session`,
  `current_principal`, `require`) moved to `app/core/deps.py`, which resolves
  auth purely by capability name. Auth now publishes a plain
  `auth.authenticate(request, session)` + `auth.check_role` (instead of
  Depends-wrapped internals). Result: any module gets auth+RBAC+RLS without
  importing auth; auth's own router consumes the same core deps. 43→still green.
- **TS-014** — `ingestion` module, the opportunity aggregate owner:
  - pure `classify.py` (`classify_text` rules-first anchors, `missing_documents`)
    with DB-free unit tests;
  - `Opportunity` + `Document` models (org-scoped, RLS) + migration
    `0002_ingestion_tables` (RLS emitted on PostgreSQL only; up/down verified on
    the 0001→0002 chain);
  - `IngestionService`: create opportunity, classify+register document,
    missing-doc checklist — all scoped by `org_id` (defense-in-depth with RLS),
    consuming `rulepacks.loader` as a lazy soft dep with built-in fallback
    anchors;
  - routes under `/api/ingestion/opportunities`, auth-gated via `core.deps`.
  - First real cross-module consumer: ingestion uses auth through the registry,
    proven by an org-isolation test (org B gets 404 on org A's opportunity) and
    a soft-dep test (works with rulepacks disabled).

Test suite: 49 passing, ruff clean.

### Done — 2026-07-23 (session 4: auth module)

- **TS-011 / TS-012** — `auth` module (Doc §5), built for isolated testing +
  refactoring:
  - **Pure security primitives** (`security.py`): argon2id hashing, RS256 JWT
    mint/decode with `kid`, ephemeral-keypair generation for dev. `refresh.py`:
    token generation + `evaluate_refresh()` (the reuse-detection *verdict* as a
    DB-free pure function). `rbac.py`: roles + `role_at_least`. All covered by
    `test_auth_security.py` with **no DB and no FastAPI** — rewritable in place.
  - **Module internals** (`models.py`, `service.py`, `deps.py`, `router.py`):
    signup/login/refresh/logout/me/add-member; rotating refresh with
    whole-family revocation on replay; RBAC guard; per-request RLS binding
    (`bind_org_context`). Only capabilities (`auth.current_principal`,
    `auth.require`, `auth.keys`) are exposed — consumers never import internals.
  - **TS-013a (auth slice)** — first real Alembic migration `0001_auth_tables`
    (orgs, users, org_members, refresh_tokens), portable across SQLite/Postgres;
    verified up + down.
- Ruff configured for FastAPI's `Depends`-in-defaults idiom; email fields kept
  as plain `str` to avoid an extra dependency.

Test suite: 43 passing, ruff clean. Added argon2-cffi + PyJWT[crypto].

### Done — 2026-07-23 (session 3: deterministic BOQ engine + synthetic tender)

- **Synthetic sample tender** (`evals/in-works/sample_tender/`): a hand-written
  fixture with deliberately planted traps — `boq.csv` (9 rows), `conditions.md`
  (5 clause traps + `[pN]` markers), and `gold_answer.yaml` as its own ground
  truth. Lets the pipeline be proven end-to-end without a real tender or API key.
- **TS-018** — `boq` module: deterministic engine (Doc §6.4, zero LLM) —
  `normalize()` (unit-canon folding + `amount_calc`), DuckDB `run_checks()`
  (arithmetic error, blank rate, duplicate, quantity outlier, grand-total /
  carry-forward mismatch). Findings use the new shared `Finding` contract in
  `app/core/contracts/findings.py`, tagged `deterministic_check`.
- **TS-019** — scope-gap engine: `SpecTextIndex` + trade-checklist cross-
  reference; a gap fires only when a spec trigger is present AND no BOQ line
  matches. `boq` consumes `rulepacks.loader` as a lazily-resolved soft dep and
  degrades to built-in defaults when rulepacks is disabled.
- **Ran it live:** the engine catches exactly the planted defects (duplicate ×2,
  arithmetic, blank rate, grand-total) and 5 civil scope gaps with zero false
  positives (waterproofing correctly NOT flagged). `test_boq.py` asserts this
  against the gold answer, including a determinism (identical-rerun) check.
- **Accuracy harness** now accepts `.md`/`.txt` (not just PDF), so the LLM half
  runs on `conditions.md` directly with an API key.

Test suite: 30 passing, ruff clean. pandas + duckdb added.

### Done — 2026-07-22 (session 2: Phase-0 completion + DB foundation)

- **TS-009** — 3 trade checklists (civil_structure, electrical, hvac) for
  scope-gap detection, drafted from public sources with `confidence:
  unvalidated`; loader parses `boq/trade_checklists/*.yaml` into typed schemas.
- **TS-006** — Phase-0 Week-2 accuracy harness (`scripts/phase0_accuracy_test.py`,
  throwaway by design): runs the 5 in-works patterns over tender PDFs at
  temperature 0, verifies every quote verbatim (invented quote → RED_FLAG),
  wraps tender text as untrusted data.
- **TS-010** — Eval golden-set scaffold `evals/in-works/`
  (classification, deadlines, risk_patterns, boq, drafting) + the scored
  pass/fail bar in `scorecard.md` (Doc §19.5, §11.5).
- **TS-013** — DB foundation in `app/core/db.py`: declarative `Base`,
  `OrgScopedMixin` (org_id + RLS self-registration), `TimestampMixin`,
  `rls_statements()`, `bind_org_context()`, engine/session builders published
  as `db.engine`/`db.sessionmaker` registry capabilities. Alembic scaffold with
  pluggable per-module model discovery; CI gains an up/down migration check.
  Per-module models split out to **TS-013a** (land with each module).

Test suite: 23 passing, ruff clean.

### Done — 2026-07-22 (session 1: project bootstrap)

- **TS-001** — Repo bootstrapped: mandatory AI workflow rules for Claude
  (`CLAUDE.md`) and Cursor (`.cursor/rules/` — workflow, architecture,
  specs/tasks conventions); build blueprint v1.0 vendored to
  `docs/TenderShield_Full_Build_Doc.md` as the requirement source of truth.
- **TS-002** — Task backlog `TS-001`–`TS-025` derived from the blueprint
  (bootstrap + Phase 0 + Phase 1, in the doc's value order; Phase 2+ excluded
  by design until gates pass).
- **TS-003** — Spec suite generated in `specs/`: product overview, data-model
  ownership map, Phase-0 accuracy test, frontend, and per-module specs (core,
  rulepacks, auth, ingestion, risk, boq, drafting, review, billing, assistant),
  each citing its build-doc sections and defining capabilities/events.
- **TS-004** — Backend core: pluggable module framework (FastAPI modular
  monolith). `ModuleSpec` plugin contract, fail-isolated loader
  (`TS_ENABLED_MODULES` boots any subset), `ServiceRegistry` + `EventBus` as
  the only cross-module channels, `health` module, and an architecture test
  that fails the build on any hard cross-module import. 13 tests.
- **TS-005** — CI: ruff + pytest on every push (GitHub Actions).
- **TS-007** — `rulepacks/in-works/` scaffold: pack.yaml, doc-type anchors +
  expected-doc set, BOQ unit-canon map + check thresholds, default contractor
  playbook; backend `rulepacks` module with Pydantic-validated loader
  (malformed YAML skipped, never fatal), `validated_only` filter, REST
  endpoints, `rulepacks.loader` capability.
- **TS-008** — First 5 Phase-0 risk patterns from public sources (payment
  terms, price escalation, LD cap, defect liability/retention, termination
  for convenience) — all `confidence: unvalidated` with `source:` citations
  (Doc §14.1). Test suite now 18 passing, ruff clean.

### Next

The Phase-1 feature engine is complete end-to-end (upload → classify →
deadlines → clauses → risk register → BOQ checks → review → clarification
letter/assumptions → gated DOCX/XLSX/PDF export → billing), the `assistant`
module is built (hidden from the UI by product choice), and the first Phase-2
feature — **baseline lock** (TS-041/042) — now ships end to end. Next:

- **Phase-2 continuation (natural follow-ons to baseline lock):**
  - **TS-043** — notice-deadline countdowns + alerts driven by the notice-rule
    register (the register now exists; wire it to the deadline/notification
    path). Doc §0.1 (P3), §10.
  - **TS-044** — award-document ingestion: parse the negotiated contract/award
    letter so the award baseline is sealed from real award text (today it seals
    the reviewed state). Doc §0.1 (P2/P3).
  - **TS-045** — handover-pack file export (DOCX/PDF) reusing the export
    renderer (today the pack is structured JSON in the UI).
- **The real gate (not code):** domain-accuracy validation — 5 real tenders +
  gold answers + a QS review (Doc §18.3/§19.2) — is the gate that *promotes*
  Phase 2 out of "built-ahead". Set `ANTHROPIC_API_KEY` to turn on the LLM
  classifier + the Week-2 accuracy harness. Founder still needs to collect the
  5 real tenders + gold answers — code can't substitute for these.
- **Production hardening (infra, not logic):** tus resumable upload, Celery/Redis
  streaming, Postgres/RDS deploy, email/WhatsApp send adapters, phone-OTP/Google
  OIDC, live Razorpay/Stripe keys — all logic-ready behind existing interfaces
  (TS-033/034/035/036/037), pending external creds.
- Frontend follow-ups: PDF.js source-page view, a frontend lint/build step in CI.
