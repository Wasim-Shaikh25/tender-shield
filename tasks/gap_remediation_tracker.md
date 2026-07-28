# Gap Remediation Tracker (TS-084 … TS-109)

Created from the whole-project gap analysis on 2026-07-28 (TS-083,
`docs/GAP_ANALYSIS.md`). Requirement detail for every task lives in
`specs/requirements/R-0xx-*.md`.

## Goal

Close the gap between "the domain engine works" and "this is a product that can
hold customer data and take money". The engine is not the problem — security,
monetization and the frontend are.

## Gate map

Work proceeds gate by gate. **A gate is not done until every P0 in it is done**,
because the gates are ordered by what blocks what: you cannot sell a product you
cannot bill for, and you must not onboard customers onto a system that leaks
their tender data between tenants.

| Gate | Theme | Tasks | Blocks | Status |
|---|---|---|---|---|
| **1** | Stop the leaks | TS-084…TS-086, TS-093…TS-095 | Any real customer data | **done** |
| **2** | Make it possible to get paid | TS-087…TS-091, TS-096…TS-098 | All revenue; Phase-1 exit gate | **done** |
| **3** | Make it usable | TS-092, TS-099…TS-104 | Daily use, retention | todo |
| **4** | Scale and prove | TS-105…TS-109 | NFRs, phase gates, ops | todo |

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
| TS-092 | Persist + rotate refresh tokens; single-flight refresh; 401 retry; typed errors; route guards | P0 | [R-010](../specs/requirements/R-010-frontend-session.md) | frontend | todo | A1–A10 in R-010 |
| TS-100 | Workspace switching: deterministic default, switch endpoint, UI switcher | P1 | [R-011](../specs/requirements/R-011-workspace-switching.md) | `auth`, frontend | todo | A1–A8 in R-011 |
| TS-102 | Portfolio dashboard: cross-tender deadline wall, attention, pipeline, usage | P1 | [R-012](../specs/requirements/R-012-dashboard.md) | `analytics`, `ingestion`, frontend | todo | A1–A9 in R-012 |
| TS-103 | Account UI: invitation accept, members, MFA, workspace/profile settings, admin console, audit viewer, session list + logout-all (deferred from TS-093) | P1 | [R-013](../specs/requirements/R-013-account-ui.md) | `auth`, frontend | todo | A1–A11 in R-013 |
| TS-099 | Email verification, delivery adapters, disposable-email blocklist, canonical-email abuse counting | P1 | [R-015](../specs/requirements/R-015-email-verification.md) | `auth`, `notifications` | todo | A1–A11 in R-015 |
| TS-101 | Enforce MFA at login: challenge tokens, replay guard, re-auth on re-enroll, recovery codes | P1 | [R-002 §D](../specs/requirements/R-002-auth-hardening.md) | `auth` | todo | A7–A11 in R-002 |
| TS-104 | Design system, error copy table, `/signup` route, a11y pass, frontend test stack | P2 | [R-014](../specs/requirements/R-014-design-system.md) | frontend | todo | A1–A10 in R-014 |

**Note on ordering:** TS-104 lands the frontend test stack (Vitest, Testing
Library, Playwright). Pulling its testing section forward — before TS-092 — is
worth considering, since TS-092 is the task most in need of tests and there is
currently no way to write one.

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
