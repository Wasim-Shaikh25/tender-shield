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
| **1** | Stop the leaks | TS-084…TS-086, TS-093…TS-095 | Any real customer data | todo |
| **2** | Make it possible to get paid | TS-087…TS-091, TS-096…TS-098 | All revenue; Phase-1 exit gate | todo |
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
| TS-094 | Rate limiting on auth endpoints + capped per-account lockout | P1 | [R-002 §C](../specs/requirements/R-002-auth-hardening.md) | `core`, `auth` | todo | A5, A6 in R-002 |
| TS-095 | Stream uploads; enforce size cap before buffering; type allowlist; ZIP guards; storage quota | P1 | [R-003](../specs/requirements/R-003-upload-safety.md) | `ingestion` | todo | A1–A6 in R-003 |

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

**Gate 1 exit:** all six done; the Postgres CI job is green; a cross-tenant read
attempt is covered by an automated test. Remaining: TS-094, TS-095.

---

## Gate 2 — Make it possible to get paid

TS-087 and TS-088 are the two that matter most in the whole backlog: without
them every other billing task is decoration, because the paywall is unenforced
and the free tier produces paid-grade output.

| ID | Task | Sev | Req | Module(s) | Status | Acceptance gate |
|---|---|---|---|---|---|---|
| TS-087 | Enforce metering inside the review path via a `meter()` capability guard | P0 | [R-004 §A](../specs/requirements/R-004-paywall-enforcement.md) | `core`, `risk`, `billing` | todo | A1–A5 in R-004 |
| TS-088 | Apply the free-tier watermark in all three export renderers | P0 | [R-004 §B](../specs/requirements/R-004-paywall-enforcement.md) | `export`, `billing` | todo | A6, A7 in R-004 |
| TS-089 | Real provider orders + `payment_intents` + server-side plan/amount binding | P0 | [R-005 §A–B](../specs/requirements/R-005-payments-checkout.md) | `billing` | todo | A1–A4, A9 in R-005 |
| TS-097 | Webhook coverage: refunds, failures, disputes, dunning/grace, dedupe without event id | P1 | [R-005 §C](../specs/requirements/R-005-payments-checkout.md) | `billing` | todo | A5–A8, A10 in R-005 |
| TS-090 | Coupons, discounts, credits, referrals, trials, pilot comps | P1 | [R-006](../specs/requirements/R-006-coupons-discounts.md) | `billing` | todo | A1–A12 in R-006 |
| TS-096 | GST invoicing: wire `gst.py`, tax columns, gap-free FY series, PDF, credit notes | P1 | [R-007](../specs/requirements/R-007-gst-invoicing.md) | `billing` | todo | A1–A10 in R-007 |
| TS-091 | Billing UI: pricing, paywall component, checkout, invoices, usage meters | P0 | [R-008](../specs/requirements/R-008-billing-ui.md) | frontend | todo | A1–A9 in R-008 |
| TS-098 | Entitlement service: seats, top-ups, billing-anniversary periods, plan changes | P1 | [R-009](../specs/requirements/R-009-plan-entitlements.md) | `billing`, `auth` | todo | A1–A9 in R-009 |

**Suggested order:** TS-087 → TS-088 → TS-089 → TS-091 (a thin but complete
paid path) → TS-096 → TS-098 → TS-097 → TS-090.

**Gate 2 exit:** a test customer can hit the paywall, pay, receive a GST invoice
and export without a watermark — end to end, through the UI.

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
| 1 | 4 | 6 |
| 2 | 0 | 8 |
| 3 | 0 | 7 |
| 4 | 0 | 5 |
| **Total** | **4** | **26** |
