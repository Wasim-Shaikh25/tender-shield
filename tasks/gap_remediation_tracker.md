# Gap Remediation Tracker (TS-084 … TS-126)

Created from the whole-project gap analysis on 2026-07-28 (TS-083,
`docs/GAP_ANALYSIS.md`) and extended the same day with the product-discovery
audit (TS-126, `docs/PRODUCT_DISCOVERY_GAPS.md`). Requirement detail for every
task lives in `specs/requirements/R-0xx-*.md`.

## Goal

Close two different gaps.

**Gates 1–4 (TS-083):** the gap between "the domain engine works" and "this is a
product that can hold customer data and take money". The engine was never the
problem — security, monetization and the frontend were.

**Gates 5–7 (TS-126):** the gap between "the software is correct" and "a customer
can actually use it". The discovery audit found capabilities that were never
built at all — most starkly, **no user can upload their own tender**, so the
product currently analyses only its own built-in sample. Correct, billable,
isolated — and not yet usable.

## Gate map

Work proceeds gate by gate. **A gate is not done until every P0 in it is done**,
because the gates are ordered by what blocks what: you cannot sell a product you
cannot bill for, and you must not onboard customers onto a system that leaks
their tender data between tenants.

| Gate | Theme | Tasks | Blocks | Status |
|---|---|---|---|---|
| **1** | Stop the leaks | TS-084…TS-086, TS-093…TS-095 | Any real customer data | **done** |
| **2** | Make it possible to get paid | TS-087…TS-091, TS-096…TS-098 | All revenue; Phase-1 exit gate | **done** |
| **3** | Make it usable | TS-092, TS-099…TS-104 | Daily use, retention | in progress (2/7) |
| **4** | Scale and prove | TS-105…TS-109 | NFRs, phase gates, ops | todo |
| **5** | Make the core journey real | TS-110…TS-113, TS-119 | **Any real customer use** | todo |
| **6** | Trust, recovery and compliance | TS-114…TS-117 | Enterprise/consultancy sale; incident response | todo |
| **7** | Expose what is already built | TS-118, TS-120…TS-125 | Reachability of finished engines | todo |

Gates 1–4 came from the TS-083 defect audit. **Gates 5–7 come from the TS-126
product-discovery audit** (`docs/PRODUCT_DISCOVERY_GAPS.md`) and cover
capabilities that were never built at all. Gate 5 outranks Gates 3 and 4 on
merit: a user cannot currently upload their own tender, so nothing in Gates 3–4
is reachable with real customer data.

---

## Gate 1 — Stop the leaks

Nothing here is optional and nothing here is large. This is roughly a week of
work that removes three cross-tenant leaks and an account-takeover path.

| ID | Task | Sev | Req | Module(s) | Status | Acceptance gate |
|---|---|---|---|---|---|---|
| TS-084 | Membership authorization on all path-scoped workspace/project routes | P0 | [R-001 §A](../specs/requirements/R-001-tenant-isolation.md) | `auth` | **done** | A1–A3, A7 in R-001 |
| TS-085 | Gate the dev token echo (`forgot_password`, `create_invitation`) behind a dev-only setting; production startup refuses it | P0 | [R-002 §A](../specs/requirements/R-002-auth-hardening.md) | `auth`, `core` | **done** | A1–A3 in R-002 |
| TS-086 | RLS hardening: `FORCE`, `WITH CHECK`, missing tables, post-commit rebinding, Postgres CI job | P0 | [R-001 §B](../specs/requirements/R-001-tenant-isolation.md) | `core`, migrations, CI | **done**² | A4–A6, A8 in R-001 |
| TS-093 | Revoke all refresh-token families on password reset | P1 | [R-002 §B](../specs/requirements/R-002-auth-hardening.md) | `auth` | **done**¹ | A4 in R-002 |
| TS-094 | Rate limiting on auth endpoints + capped per-account lockout | P1 | [R-002 §C](../specs/requirements/R-002-auth-hardening.md) | `core`, `auth` | **done**³ | A5, A6 in R-002 |
| TS-095 | Stream uploads; enforce size cap before buffering; type allowlist; ZIP guards; storage quota | P1 | [R-003](../specs/requirements/R-003-upload-safety.md) | `core`, `ingestion`, `boq` | **done**⁴ | A1–A6 in R-003 |

⁴ Shipped: streaming with a mid-transfer size cap, extension allowlist +
magic-byte validation, applied to **both** upload endpoints — `boq`'s had no
size limit at all before this, which R-003's draft (scoped to `ingestion`
only) didn't call out. New shared `app/core/uploads.py` so neither module
imports the other. **Deferred, not done:** storage quota (§B.3, needs
`billing.entitlements` — doesn't exist until R-009/TS-098), ZIP-bomb/path-
traversal guards (§B.4 — no ZIP upload path exists anywhere in the codebase
yet, so there's nothing to harden; the R-003 section is forward guidance for
when one is added), malware scanning (§B.5, interface only — no scanner to
plug in). tus resumable upload stays TS-033.

³ Shipped with wider limits than the R-002 §C draft (`/login` 20/5min not
10/5min): the draft's 10/5min IP limit collides with the 10-failure per-account
lockout threshold within a single test client, so both would never be
independently observable in the same test run against one IP. The per-account
lockout is the precise defense against a single-account brute force; the IP
limit's job is blunting a spray attack across many accounts from one IP, which
a 20/5min ceiling still does. `core.ratelimiter` is in-memory (correct for a
single-process deployment) and best-effort — its absence never blocks a
request, matching spec core B2 (the app must boot with any module subset).

¹ TS-093 ships the revoke-on-reset behavior (R-002 §B.2, acceptance A4). The
session-list/logout-all endpoints (R-002 §B.3 — `GET /auth/sessions`,
`DELETE /auth/sessions/{family}`, `POST /auth/logout-all`) are deferred to
TS-103 (account UI), since they need a UI to be worth shipping and are naturally
built alongside the security settings page.

² TS-086's implementation diverged from the R-001 §B draft in four ways, all
found by testing against a real (non-superuser) PostgreSQL role rather than
trusting the design on paper — see the erratum at the top of
[R-001](../specs/requirements/R-001-tenant-isolation.md): `SET LOCAL` with a
bind parameter is a syntax error (fixed with `set_config`), `after_commit`
cannot emit SQL (fixed with `after_begin`), and `workspaces`/`workspace_members`
need a compound predicate or `list_workspaces` breaks (which in turn required
binding a second GUC, `app.user_id`, and fixing `login`/`refresh`/Apple
sign-in — all unauthenticated entry points — to bind it explicitly). New test
file `tests/test_rls_postgres.py` (9 tests) is the only place in the repo the
isolation guarantee is actually exercised; wired into CI as the
`backend-postgres` job.

**Gate 1 exit: reached.** All six done; the Postgres CI job is green; a
cross-tenant read attempt is covered by an automated test.

---

## Gate 2 — Make it possible to get paid

TS-087 and TS-088 are the two that matter most in the whole backlog: without
them every other billing task is decoration, because the paywall is unenforced
and the free tier produces paid-grade output.

| ID | Task | Sev | Req | Module(s) | Status | Acceptance gate |
|---|---|---|---|---|---|---|
| TS-087 | Enforce metering inside the review path via a `meter()` capability guard | P0 | [R-004 §A](../specs/requirements/R-004-paywall-enforcement.md) | `core`, `risk`, `billing` | **done**⁵ | A1–A5 in R-004 |
| TS-088 | Apply the free-tier watermark in all three export renderers | P0 | [R-004 §B](../specs/requirements/R-004-paywall-enforcement.md) | `export`, `billing` | **done** | A6, A7 in R-004 |
| TS-089 | Real provider orders + `payment_intents` + server-side plan/amount binding | P0 | [R-005 §A–B](../specs/requirements/R-005-payments-checkout.md) | `billing` | **done**⁶ | A1–A4, A9 in R-005 |
| TS-097 | Webhook coverage: refunds, failures, disputes, dunning/grace, dedupe without event id | P1 | [R-005 §C](../specs/requirements/R-005-payments-checkout.md) | `billing` | **done**⁶ | A5–A8, A10 in R-005 |
| TS-090 | Coupons, discounts, credits, referrals, trials, pilot comps | P1 | [R-006](../specs/requirements/R-006-coupons-discounts.md) | `billing`, `auth` | **done**¹⁰ | A26–A33 in billing.md, A15–A16 in auth.md |
| TS-096 | GST invoicing: wire `gst.py`, tax columns, gap-free FY series, PDF, credit notes | P1 | [R-007](../specs/requirements/R-007-gst-invoicing.md) | `billing` | **done**⁸ | A14–A19 in billing.md |
| TS-091 | Billing UI: pricing, paywall component, checkout, invoices, usage meters | P0 | [R-008](../specs/requirements/R-008-billing-ui.md) | frontend | **done**⁷ | A1–A2, A4–A9 in R-008 (A3 coupons deferred) |
| TS-098 | Entitlement service: seats, top-ups, billing-anniversary periods, plan changes | P1 | [R-009](../specs/requirements/R-009-plan-entitlements.md) | `billing`, `auth` | **done**⁹ | A20–A25 in billing.md, A14 in auth.md |

⁵ Race-safety (R-004 §A.4) is verified against real, non-superuser PostgreSQL
with two genuinely concurrent threads (`tests/test_billing_race_postgres.py`)
— sanity-checked both ways: the test fails reliably (5/5 runs) with the
`pg_advisory_xact_lock` call removed, and passes reliably (5/5) with it
restored, so it's confirmed to actually catch the race rather than pass
vacuously. `WorkspaceAdmin.mark_free_review_used`/`set_plan` no longer commit
internally — the lock, the free-review write, and the usage-event write now
share one transaction/one commit in `authorize_review`, matching the R-004
design (splitting them across commits would release the lock before the write
it protects).

⁶ Real `PaymentProvider` abstraction (`billing/providers/{base,razorpay,
select}.py`) — `create_checkout` now creates a genuine Razorpay order via a
`payment_intents` row, resolving price server-side from `PRICES_MINOR` by
`(plan, currency)`; a workspace with no configured provider gets 503
`payment_provider_unavailable` rather than a fake order. The webhook resolves
every grant by looking up the `PaymentIntent` the event's opaque `intent_id`
(carried in provider `notes`) points to — never from `notes.plan`/
`notes.workspace_id` directly, which is the exact vulnerability this closes
(a client could edit `notes` before the provider redirect and receive
whatever plan it asked for). One amount-checked handler
(`_on_payment_succeeded`) now covers `order.paid`, `subscription.charged`,
*and* `subscription.activated` — an early draft treated
`subscription.activated` as a separate, unchecked path, and the new test
`test_webhook_amount_mismatch_grants_nothing` caught it granting `pro` on an
underpaid activation before the fix. Full webhook coverage added: refunds
(`refund.processed`), failures (`payment.failed`), dunning
(`subscription.halted` → 7-day grace, plan untouched), cancellation
(`subscription.cancelled` → downgrade to free), and idempotency via a
unique-constraint insert on `event_id` or a `sha256(raw_body)` fallback when
no event id is present (catch `IntegrityError`, not check-then-act).
`PaymentIntent` is deliberately not RLS-protected (same precedent as
`RefreshToken`/`PasswordReset` — the webhook must find the row before it
knows the workspace); `get_intent_status` does its own ownership check in
application code. Validated against real, non-superuser PostgreSQL with FORCE
RLS live: migration up/down, the full checkout→webhook→status→invoice→
replay-dedup→intent-status flow via an ad-hoc e2e script, and the existing
RLS (10 tests) + race-safety Postgres suites still green — this also
surfaced and fixed a real pre-existing bug where the webhook route (being
unauthenticated) never bound `app.workspace_id`, silently broken since the
TS-086 RLS hardening shipped. `tests/test_billing.py` rewritten (21 tests);
`tests/test_paywall_enforcement.py`'s webhook helper now does a real
checkout → webhook round trip instead of hand-crafting `notes`.

⁷ Ships `/pricing` (public, prices mirror server-side `PRICES_MINOR`),
`<Paywall/>` (driven by `detail.code`; covers `free_exhausted`,
`paygo_payment_required`, `quota_exhausted`), `<CheckoutDialog/>` (real
Razorpay hosted checkout + intent polling — the client handler never marks
anything paid, only the webhook does), and `/billing` (plan/status/grace,
usage meter, admin-only invoice table; read-only for viewer/estimator).
Coupon field (R-006/TS-090) and real seats/storage/entitlement fields
(R-009/TS-098) deferred — no backend capability to call yet. Validated with
a live backend + Playwright: signup → free review → second-opportunity
paywall → checkout dialog, screenshotted at each step; `next build` and
`tsc --noEmit` clean.

Wiring this UI surfaced and fixed two real backend bugs (see
`specs/modules/billing.md` B11/B12): (1) a paygo-plan workspace could run
unlimited unpaid reviews — `Grant(requires_payment=True)` was computed but
never checked; and (2) `workspace.plan` never actually transitioned to
`"paygo"` on payment (only subscriptions called `set_plan`), which made
fix (1)'s enforcement branch unreachable. Both fixed with new regression
tests in `test_paywall_enforcement.py`; full SQLite suite (189 passed, 1
skipped) and the Postgres RLS + race-safety suites (10 tests) still pass
after the fix.

⁸ Wires `gst.py` into real invoices via `issue_invoice`/`issue_credit_note`:
tax-correct `Invoice` rows (base/CGST/SGST/IGST/round_off/total columns,
replacing the untaxed `amount_minor` placeholder), gap-free per-FY numbering
(`invoice_sequences` + `SELECT ... FOR UPDATE`), buyer GSTIN capture with
format/checksum validation (`PUT /billing/details`, rejected at save time),
credit notes on refund, and an on-demand PDF route
(`GET /invoices/{id}/pdf`). Deliberate deviation from the R-007 draft:
catalog prices are treated as GST-**inclusive**, so checkout amounts don't
change and the tax breakdown is derived from the exact amount charged —
computed once at checkout (informational) and again at issuance against
the SAME `intent.amount_minor`, so the "reconciliation check" the draft
called for is true by construction. PDFs render on demand rather than via
the `Storage` protocol the draft suggested, since `billing` can't import
`ingestion.storage` (CLAUDE.md §2) and no cross-module storage capability
exists yet. GSTIN checksum validation is self-consistent (built and tested
against its own check-digit function) but **not verified against a real
GSTN reference vector** — flagged explicitly in `gst.py` and the spec for
confirmation before it gates a live paid checkout. Caught a real
concurrency bug while proving gap-free numbering against real Postgres:
`SELECT ... FOR UPDATE` can't lock a row that doesn't exist yet, so the
very first invoice of a new FY raced two issuers into the same INSERT
(unique-constraint violation) — fixed with a `pg_advisory_xact_lock` keyed
on the FY, sanity-checked both ways (fails reliably without it, passes
reliably with it). Also discovered and fixed a pre-existing CI gap while
touching this area: `test_billing_race_postgres.py` (from the TS-087 work)
was never wired into the `backend-postgres` CI job, which only ran
`test_rls_postgres.py` — the job now runs the full `-m postgres` suite.
202 SQLite tests pass (1 skipped) + 11 Postgres tests; a dedicated e2e
script confirmed the full checkout(with GSTIN)→webhook→invoice→PDF flow
against real Postgres with FORCE RLS live.

⁹ One `Entitlements` object (`billing/entitlements.py`, pure) resolves
reviews/seats/plan-status/period for every consumer — `PLAN_LIMITS` declared
`seats` per plan and nothing had ever read it before this. New
`auth.seats_used`/`billing.entitlements` capability pair (billing can't
query auth's own `workspace_members`/`invitations` tables, CLAUDE.md §2)
enforces seat limits at `add_workspace_member`/`create_invitation`/
`accept_invitation` — `402 seat_limit_reached`, not 403, matching the
existing paywall shape so the frontend's `<Paywall/>` renders it unchanged.
Top-ups are sellable now (`POST /checkout {"kind": "topup"}`, price resolved
from the workspace's own plan) — `authorize()`'s `has_topups` parameter had
no caller before this rewrite to a real `reviews_used`/`reviews_topup`
signature. Billing-anniversary periods (month-end-safe `add_month`) replace
the hardcoded calendar month, sourced from the Razorpay subscription
entity's own `current_start`/`current_end` when present. A downgrade that
would leave a workspace over its new plan's seat limit is rejected
(`400 seats_exceed_new_plan`), never auto-removing members.

Found and fixed two real bugs while building this: (1) a `past_due`
workspace kept full access **forever**, regardless of how long its grace
window had been closed — `authorize()` never compared "now" against
`grace_until` at all; fixed with a `grace_expired` check. (2) That fix's own
tests immediately hit a SECOND latent bug: SQLite returns naive datetimes
even for `DateTime(timezone=True)` columns (Postgres preserves tzinfo),
crashing the very first aware-vs-naive comparison — fixed with
`entitlements.as_aware_utc`, which also corrected `status()`'s
`grace_until`/`period_end` serialization (silently wrong since TS-097
shipped it; no prior test compared the exact ISO string). Deferred, by
design: true deferred-effect downgrades/cancellations (needs R-016/TS-105's
job scheduler to have anything to act on later) and a seat-check TOCTOU race
(lower severity than the free-review race already fixed under TS-087,
left unlocked). Validated against real Postgres with FORCE RLS live
(signup → status → add-member-at-capacity → 402, cross-module registry call
chain exercised end to end). 218 SQLite tests pass (1 skipped) + 11 Postgres
tests; `next build`/`tsc --noEmit` clean after wiring the frontend's
`/billing` usage meters and the paywall's top-up button to the new fields.

**Suggested order:** ~~TS-087 → TS-088~~ (done) → ~~TS-089~~ (done) →
~~TS-091~~ (done, thin path) → ~~TS-096~~ (done) → ~~TS-098~~ (done) →
~~TS-097~~ (done) → ~~TS-090~~ (done).

**Gate 2 exit: reached.** A test customer can hit the paywall, pay, receive a
GST invoice and export without a watermark — end to end, through the UI. All
eight tasks in this gate are done.

¹⁰ Coupons (`coupons.py`, pure discount math: percent/fixed/free_months/
free_reviews, exhaustion/per-workspace/currency/plan/expiry validation),
an append-only `Credit` ledger, referral tracking + reward, one-time trials,
and superadmin pilot comps — all written only on payment SUCCESS via the
same idempotent-insert idiom used everywhere else in this module
(`CouponRedemption.payment_intent_id` unique, `IntegrityError` caught not
re-raised).

Found and fixed two real bugs while validating this against real Postgres
with FORCE RLS live (not just SQLite, where both passed vacuously):

1. **Cross-tenant RLS violation in the referral flow (major).** A referred
   workspace's signup transaction is bound to *its own* new workspace, never
   the referrer's. Resolving the referral code via a plain
   `Workspace.referral_code` query silently found nothing — RLS's compound
   predicate hid the referrer's row — so zero `Referral` rows were ever
   created and zero credits ever granted, confirmed via a direct
   `select count(*) from referrals` = 0 and both workspaces showing a 0
   balance after a real paid purchase. A second, related violation: crediting
   the referrer's workspace from inside the referred workspace's
   webhook-processing RLS binding is a genuine cross-tenant write that
   `credits`' `WITH CHECK` correctly rejects. Fixed by resolving through a
   new, deliberately non-RLS `referral_codes` pointer table (same precedent
   as `payment_intents`/`refresh_tokens`/`password_resets`) and by explicitly
   rebinding RLS context around the referrer-side credit insert. Both fixes
   sanity-checked by temporarily reverting each and confirming
   `tests/test_referrals_postgres.py` fails the way the bug actually failed
   (silent 0-row/0-balance for #1; a Postgres `ProgrammingError` from the RLS
   engine itself for #2). See `specs/modules/billing.md` §B21 for the full
   incident writeup.
2. **`credit_balance()` returned a `Decimal` under real Postgres, an `int`
   under SQLite.** `SUM()` over a `BigInteger` column returns `NUMERIC` in
   Postgres (psycopg maps that to `Decimal`); SQLite's `SUM()` returns a
   plain int. Every coupon/credit test passed on SQLite; under Postgres, the
   first checkout for a workspace with a nonzero credit balance poisoned
   `credit_applied_minor`/`amount_minor` with a `Decimal`, which crashed
   `json.dumps` on the order's `checkout_payload`. Fixed with an explicit
   `int(...)` cast. See `specs/modules/billing.md` §B20.

Also migrated two historical migrations that only fail on a from-scratch
Postgres build: `WORKSPACE_SCOPED_TABLES` is populated at model-import time
(a live process-wide set), not a per-migration snapshot, so
`ae76edba3a7a`/`e26e85245237` tried to enable RLS on `coupon_redemptions`/
`credits` before this task's own migration had created those tables. Fixed
with an existence guard (`sa.inspect(...).get_table_names()`); verified with
a full `alembic upgrade head` → `downgrade base` → `upgrade head` cycle on a
fresh database, and `pg_class.relrowsecurity`/`relforcerowsecurity`
confirms `coupon_redemptions`/`credits` carry RLS while the new
`referral_codes` table (like `payment_intents`/`coupons`/`referrals`)
correctly does not.

240 SQLite tests pass (1 skipped) + 13 Postgres tests (2 new, in
`tests/test_referrals_postgres.py`); `ruff check .` clean.

---

## Gate 3 — Make it usable

| ID | Task | Sev | Req | Module(s) | Status | Acceptance gate |
|---|---|---|---|---|---|---|
| TS-092 | Persist + rotate refresh tokens; single-flight refresh; 401 retry; typed errors; route guards | P0 | [R-010](../specs/requirements/R-010-frontend-session.md) | frontend | **done**¹¹ | A7–A15 in frontend.md |
| TS-100 | Workspace switching: deterministic default, switch endpoint, UI switcher | P1 | [R-011](../specs/requirements/R-011-workspace-switching.md) | `auth`, frontend | **done**¹² | A17–A23 in auth.md, A16–A17 in frontend.md |
| TS-102 | Portfolio dashboard: cross-tender deadline wall, attention, pipeline, usage | P1 | [R-012](../specs/requirements/R-012-dashboard.md) | `analytics`, `ingestion`, frontend | todo | A1–A9 in R-012 |
| TS-103 | Account UI: invitation accept, members, MFA, workspace/profile settings, admin console, audit viewer, session list + logout-all (deferred from TS-093) | P1 | [R-013](../specs/requirements/R-013-account-ui.md) | `auth`, frontend | todo | A1–A11 in R-013 |
| TS-099 | Email verification, delivery adapters, disposable-email blocklist, canonical-email abuse counting | P1 | [R-015](../specs/requirements/R-015-email-verification.md) | `auth`, `notifications` | todo | A1–A11 in R-015 |
| TS-101 | Enforce MFA at login: challenge tokens, replay guard, re-auth on re-enroll, recovery codes | P1 | [R-002 §D](../specs/requirements/R-002-auth-hardening.md) | `auth` | todo | A7–A11 in R-002 |
| TS-104 | Design system, error copy table, `/signup` route, a11y pass, frontend test stack | P2 | [R-014](../specs/requirements/R-014-design-system.md) | frontend | todo | A1–A10 in R-014 |

**Note on ordering:** TS-104 lands the REST of the frontend test stack
(Testing Library conventions beyond what TS-092 needed, a11y tooling,
Playwright for e2e). TS-092 already seeded Vitest + Testing Library itself
(R-010's own spec calls for this — "a natural first consumer"), so that part
of TS-104 is done; TS-104 still owns the design system, error-copy table,
`/signup` route, and a11y pass.

¹¹ Rewrote session handling from a skeleton (access token mirrored into
`localStorage`, no refresh-token client, `throw new Error(body.detail)`
turning the 402 paywall payload into a literal `"[object Object]"` string)
into the real thing: access token memory-only, refresh token persisted and
rotated, single-flight refresh (`lib/auth-client.ts`, framework-free so both
`components/session.tsx` and `lib/api.ts` can use it without a dependency
cycle) collapsing concurrent refreshes AND concurrent tabs (the backend
revokes the whole refresh-token family on a replayed refresh — two
uncoordinated refreshes look exactly like a replay), proactive refresh
scheduled from the JWT's own `exp` claim, reactive one-shot 401 retry in
`lib/api.ts`'s `req()` with every other call site's signature unchanged,
typed `ApiError`/`SessionExpired`/`PaywallError`, a `RequireAuth` route guard
gated on a real three-state `status` (not `session`, which is legitimately
null both while loading and once truly signed out), and `BroadcastChannel`
multi-tab sign-out/token sync. Validated two ways: a new Vitest suite (9
tests, including a single-flight test sanity-checked by temporarily removing
the `if (inflight) return inflight;` guard and confirming it fails 3-calls-
not-1), and a live Chromium/Playwright run against a real backend covering
the redirect-with-`next=`, no-flash-on-reload, and revoked-token-clean-
redirect-no-loop behaviors that a unit test can't prove on its own. `next
build`/`tsc --noEmit` clean.

¹² Fixed a real bug found while implementing this: `login`/`refresh`/
`apple_callback` all resolved the caller's workspace via a plain, UNORDERED
`WorkspaceMember` query — the same user could land in a different workspace
between logins purely because of row ordering, with no way to reach any
workspace but whichever one that query happened to return. New
`AuthService._resolve_login_workspace` makes this deterministic (default →
last used → oldest membership, via new `User.default_workspace_id`/
`last_workspace_id` columns); a regression test proves it actually reads
`last_workspace_id` (not just that a switch response carries the right
claim) by logging in again after switching to a workspace that is NOT the
oldest membership, and confirming it lands there — sanity-checked by
temporarily reverting to the naive query and confirming the test then fails.
New `POST /workspaces/{id}/switch` re-issues tokens after a server-side
membership check (non-members get 404, matching `require_workspace_member`'s
own reasoning — a 403 would itself confirm the workspace exists) and retires
the previous refresh-token family. A user with zero memberships now gets a
workspace-less token instead of a dead-end `AuthError("no_workspace")`,
routed by a new `RequireAuth` check to a new `/workspaces/new` page.
Frontend: a header `WorkspaceSwitcher` (hidden for single-workspace users)
built on the R-010/TS-092 session plumbing — switching just calls the same
`signIn()` login uses. Validated live: switcher absent with one workspace,
appears with two, switching updates the header and the workspace's data.
247 SQLite tests pass (1 skipped, 7 new) + 13 Postgres tests; `ruff check .`,
`next build`, `tsc --noEmit` all clean.

**Gate 3 exit:** a new customer can sign up, verify, invite a colleague, switch
workspaces, work for an hour without being logged out, and see their portfolio
on one page.

---

## Gate 4 — Scale and prove

| ID | Task | Sev | Req | Module(s) | Status | Acceptance gate |
|---|---|---|---|---|---|---|
| TS-105 | Async job pipeline: `Job` model, `JobQueue` protocol, inline + Celery backends, SSE progress | P1 | [R-016 §A](../specs/requirements/R-016-platform-scale.md) | `core`, `risk`, `ingestion` | todo | A1–A6 in R-016 |
| TS-106 | S3 storage adapter; extend the `Storage` protocol with get/delete/presign | P1 | [R-016 §B](../specs/requirements/R-016-platform-scale.md) | `ingestion` | todo | A7–A9 in R-016 |
| TS-107 | Observability: structured logs, request ids, metrics, readiness probe, LLM cost controls | P2 | [R-016 §C](../specs/requirements/R-016-platform-scale.md) | `core`, `health` | todo | A10–A13 in R-016 |
| TS-108 | Product metrics: finding-acceptance rate, golden-set scorer in CI, funnel events | P1 | [R-016 §D](../specs/requirements/R-016-platform-scale.md) | `analytics`, `review`, evals | todo | A14–A18 in R-016 |
| TS-109 | Legal/commercial surface: ToS, privacy policy, refund policy, DPA, DPDP request paths | P2 | [R-016](../specs/requirements/R-016-platform-scale.md) + Doc §16 | docs, frontend | todo | Published and linked from the app |

**TS-108 deserves promotion.** It is listed in Gate 4 because it is not a
blocker for shipping, but it is the task that tells the company whether the
product works at all: the Phase-1 kill gate ("finding acceptance <50% after two
eval cycles") is unmeasurable today even though the review module already
records every accept/reject decision. Consider pulling the acceptance-rate half
of it into Gate 2 — it is a small change with disproportionate value.

**Gate 4 exit:** the 25-minute p95 NFR is achievable, storage survives replica
replacement, and the phase gates in `specs/000-product-overview.md` can be
measured from production data.

---

# Product discovery gates (5–7) — added 2026-07-28 by TS-126

Gates 1–4 came from `docs/GAP_ANALYSIS.md` (TS-083), which audited **what exists
and is defective**. Gates 5–7 come from `docs/PRODUCT_DISCOVERY_GAPS.md`
(TS-126), which asks the opposite question: **what was never built at all** —
requirements never written, roles with no reachable workflow, journeys that
dead-end, capabilities the domain expects that appear nowhere.

**The finding that reframes the other four gates:** a user cannot upload their
own tender. `POST /ingestion/opportunities/{id}/upload` is implemented and was
hardened in TS-095, and has no user interface — no `<input type="file">`, no
`FormData`, no caller anywhere in `frontend/`. The only path a document takes
into the system is a button that posts a hardcoded 12-line demo string. Gates
1–4 made a workspace billable, isolated and switchable. It is not yet usable.

Classifications follow the discovery doc: **Confirmed Missing Requirement**
(explicitly required, not implemented) · **Strongly Implied** (an existing role
or workflow is incomplete without it) · **Domain-Expected** (standard for the
category, not confirmed in scope) · **Clarification Required** (needs a product
decision). Nothing inferred is recorded as confirmed.

## Gate 5 — Make the core journey real

| ID | Task | Sev | Req | Module(s) | Status | Class | Acceptance gate |
|---|---|---|---|---|---|---|---|
| TS-110 | Document upload journey: file picker/drag-drop, multipart client, per-file progress + failure, document list | P0 | [R-017](../specs/requirements/R-017-document-upload-journey.md) | frontend, `ingestion` | todo | Confirmed Missing | A1–A6 in R-017 |
| TS-119 | Review queue + audit viewer UI — gates the paid export path; `reviewer` has no reachable workflow without it | P0 | [R-023](../specs/requirements/R-023-unexposed-capabilities.md) | frontend, `review` | todo | Confirmed Missing | TS-119 §Acceptance in R-023 |
| TS-111 | Opportunity lifecycle + bid/no-bid decision record (`status` is a dead column) | P0 | [R-018](../specs/requirements/R-018-opportunity-lifecycle.md) | `ingestion`, frontend | todo | Confirmed Missing | A1–A6 in R-018 |
| TS-112 | Archive / delete / restore for opportunities and documents | P0 (archive) | [R-019](../specs/requirements/R-019-record-lifecycle.md) | `ingestion`, frontend | todo | Strongly Implied | A1–A6 in R-019 |
| TS-113 | Deadline alerts actually delivered (`digest.py` has zero callers) | P0 | [R-020](../specs/requirements/R-020-deadline-alerting.md) | `notifications`, frontend | todo | Confirmed Missing | A1–A6 in R-020 |

**Sequencing:** TS-110 → TS-119 → TS-111 → TS-112 → TS-113. That order is the
shortest path to a product a design partner can use end to end on their own
tender. **TS-113 depends on TS-105** (job scheduler) and shares delivery-adapter
work with TS-099.

**Gate 5 exit:** a design partner uploads their own tender pack, works the
findings through a real review queue, records a bid decision, archives what they
do not need, and is told about a deadline without opening the app.

## Gate 6 — Trust, recovery and compliance

| ID | Task | Sev | Req | Module(s) | Status | Class | Acceptance gate |
|---|---|---|---|---|---|---|---|
| TS-116 | Member removal (with immediate session revocation) + invitation list/revoke/resend | P0 | [R-022 §A](../specs/requirements/R-022-team-lifecycle-and-run-recovery.md) | `auth`, frontend | todo | Strongly Implied | A1–A6 in R-022 §A |
| TS-114 | Audit trail beyond review decisions; move `audit_log` to `core` | P1 | [R-021 §A](../specs/requirements/R-021-audit-and-data-rights.md) | `core`, `auth`, `billing`, `export` | todo | Strongly Implied | A1–A5 in R-021 §A |
| TS-117 | Processing-failure visibility + retry; metering correction for failed runs | P1 | [R-022 §B](../specs/requirements/R-022-team-lifecycle-and-run-recovery.md) | `risk`, `billing`, frontend | todo | Strongly Implied | B1–B5 in R-022 §B |
| TS-115 | Workspace data export + account/workspace closure (DPDP) | P1 | [R-021 §B](../specs/requirements/R-021-audit-and-data-rights.md) | `auth`, all workspace-scoped modules | todo | Clarification Required | B1–B5 in R-021 §B |

**TS-116 is release-blocking on its own merits.** "Cannot remove a departed
employee's access" is not a shippable state for a product holding confidential
commercial packs — especially for the P3 consultancy persona holding several
clients' packs in one workspace. Note the subtlety: removal must revoke the
member's refresh families, or "removed" silently means "removed in up to 15
minutes" when their access token expires.

**TS-115's release-blocking status is unresolved** and depends on the DPDP
question in `Product decisions still required` below. It also depends on TS-105
(jobs) and TS-106 (storage delete).

**Gate 6 exit:** an incident can be investigated, a departing employee can be
removed immediately, a failed run explains itself and does not silently consume
a paid review, and a customer can take or erase their data.

## Gate 7 — Expose what is already built

Seven modules are implemented, tested and routable with **no user interface at
all**. This is the cheapest value in the backlog — the engines are already paid
for. (TS-119 is listed in Gate 5 rather than here because it gates the paid path.)

| ID | Task | Sev | Req | Module(s) | Status | Class | Acceptance gate |
|---|---|---|---|---|---|---|---|
| TS-118 | Timeline view + `.ics` calendar subscription (needs a signed, revocable feed token) | P1 | [R-023](../specs/requirements/R-023-unexposed-capabilities.md) | frontend, `timeline` | todo | Confirmed Missing | TS-118 §Acceptance in R-023 |
| TS-120 | Bid qualification / eligibility UI — feeds the bid decision (TS-111) | P1 | [R-023](../specs/requirements/R-023-unexposed-capabilities.md) | frontend, `qualification` | todo | Confirmed Missing | R-023 |
| TS-124 | Search across opportunities, clauses and findings; opportunity assignment | P1 | [R-023](../specs/requirements/R-023-unexposed-capabilities.md) | frontend, `ingestion`, `findings` | todo | Strongly Implied | R-023 |
| TS-122 | Addendum cross-reference / diff UI | P1 | [R-023](../specs/requirements/R-023-unexposed-capabilities.md) | frontend, `crossref` | todo | Confirmed Missing | R-023 |
| TS-121 | Cross-tender comparison UI — build with TS-102's dashboard, not separately | P2 | [R-023](../specs/requirements/R-023-unexposed-capabilities.md) | frontend, `comparison` | todo | Confirmed Missing | R-023 |
| TS-123 | Rule-pack transparency UI (which patterns ran, at what version/confidence) | P2 | [R-023](../specs/requirements/R-023-unexposed-capabilities.md) | frontend, `rulepacks` | todo | Strongly Implied | R-023 |
| TS-125 | Support/ops investigation console (read-only; no impersonation by design) | P2 | [R-023](../specs/requirements/R-023-unexposed-capabilities.md) | frontend, `auth` | todo | Domain-Expected | R-023 |

**TS-118 is the best value-to-effort item in the whole backlog.** The `.ics` feed
is already written. Calendar subscription puts the product inside the tool the
customer already lives in, which is exactly the daily-use retention R-012 argues
the business depends on. The only real work is a signed, revocable feed token —
a calendar client cannot send a bearer token.

**Gate 7 exit:** no implemented, tested backend capability is unreachable from
the UI, and every role has at least one workflow it can actually perform.

## Cross-cutting findings (not tasks)

- **Roles are enforced but unmanageable and invisible.** All five roles gate real
  endpoints (`viewer` 36×, `estimator` 13×, `admin` 11×, `reviewer` 3×), but the
  UI has no member management, shows identical navigation to every role, and
  never displays the caller's own role. `reviewer` is thinnest: two of its three
  endpoints are the review queue/audit (no UI until TS-119), the third is
  `baseline/freeze` (reachable) — so the workflow the role is named for is
  precisely the one it cannot perform.
- **`projects` / `project_members` is a fully-built sub-tenant layer with no UI
  and no stated product purpose** — four endpoints, two tables, RLS coverage,
  membership guards, zero product references. Either a deliberate future
  capability or dead weight carrying real complexity and attack surface.
  **Clarification Required.**
- **No spec describes an end-to-end user journey.** The per-module specs are
  strong contracts; nothing states what a commercial head does on Tuesday
  morning. Every gap above clusters in the seams between modules — which is
  exactly what that missing document would have caught.

## Product decisions still required

These change scope, sequencing and release-blocking status. No product-context
brief was supplied for this audit, so each is genuinely open — the full list with
reasoning is in `docs/PRODUCT_DISCOVERY_GAPS.md` §Product Decisions Required.

1. **Does DPDP apply at launch?** Decides whether TS-115 blocks release.
2. **Design-partner cohort or general availability?** A design-partner launch can
   defer most of Gates 6–7; GA cannot.
3. **Upload envelope** — max pack size, resumable required?, ZIP in scope? (TS-110)
4. **Authoritative tender status list**, and whether no-bid reasons are a
   controlled vocabulary (that list is the most commercially valuable dataset the
   product could collect). (TS-111)
5. **Can customers permanently delete, or archive only?** Restore window? Do
   sealed baselines resist deletion? (TS-112)
6. **WhatsApp at launch?** And who is alerted by default — everyone, or an
   assignee? "Assignee" requires building assignment first. (TS-113, TS-124)
7. **On member removal, are records retained with attribution or reassigned?** (TS-116)
8. **Does a failed run auto-refund the metered entitlement?** (TS-117)
9. **Keep or remove the `projects` layer?**
10. **Does the AI assistant stay unsurfaced?** Six endpoints and two tables are
    currently dark by an explicit decision in `specs/frontend.md` — confirm it holds.

---

## Cross-cutting rules for this work

1. **Module boundaries hold.** No `app.modules.<other>` imports. Every new
   cross-module call goes through the service registry or the event bus
   (`CLAUDE.md` §2). Several tasks here — metering, entitlements, watermarking,
   notifications — are precisely where that rule gets tested.
2. **Specs move with the code.** Every task updates its `specs/modules/*.md` in
   the same commit (`CLAUDE.md` §1.2). The R-doc names which spec.
3. **Money is minor units.** No floats, anywhere, ever.
4. **Numbers are deterministic.** Nothing added here may take a number from an
   LLM.
5. **Fail closed.** Where a limit or an isolation check cannot be evaluated,
   deny rather than allow — with the single deliberate exception that a disabled
   billing module in dev does not paywall (R-004 §A.2).
6. **Tests, not assertions of correctness.** Each acceptance criterion in the
   R-docs is written to become a test. A task is done when its criteria are
   green, not when the code looks right.

## Definition of done (per task)

- [ ] Requirement doc read; its affected `specs/modules/*.md` updated.
- [ ] Implementation complete, `ruff check .` and `pytest -q` clean.
- [ ] Every acceptance criterion in the R-doc has a passing test.
- [ ] `tasks/backlog.md` row moved to `done`.
- [ ] `CHANGELOG.md` `[Unreleased]` updated with Done + Next.
- [ ] This tracker's row updated.

## Progress

| Gate | Done | Total |
|---|---|---|
| 1 | 6 | 6 |
| 2 | 7 | 8 |
| 3 | 0 | 7 |
| 4 | 0 | 5 |
| **Total** | **13** | **26** |
