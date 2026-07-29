# TenderShield — System Overview (living doc)

**This is the entry point.** One place to see the business goal, the
architecture, and — at a glance — what's built vs. left, before drilling
into a specific module spec or requirement doc.

**Update this file in the same commit as any change that shifts a module's
status, closes a requirement, or adds a new one** — the same discipline
`specs/modules/*.md` already has for code-level detail (`CLAUDE.md` §1.2),
extended to this one summary layer. For the authoritative done/left count,
run `python scripts/check_tracker.py` rather than trusting a stale count
here — the tables below are a snapshot for a human skimming, the tracker is
the checked source of truth.

---

## 1. Business

TenderShield is contractor commercial intelligence: ingest a tender pack
(NIT/RFP, GCC/SCC, specs, BOQ, addenda), surface risk clauses, deadline traps
and BOQ defects with exact citations, and generate bid-decision artifacts —
before bid submission.

- **Full detail:** [`specs/000-product-overview.md`](000-product-overview.md)
  — wedge, personas (P1 mid-market GC, P2 small contractor, P3 QS
  consultancy, P4 EPC team/Phase 3+), business model (one free review, then
  paygo/Pro/Scale via Razorpay), NFRs, phase/kill gates.
- **Source of truth for product decisions:**
  `docs/TenderShield_Full_Build_Doc.md` (the "Doc" — every spec cites which
  section it derives from).
- **Two audits sit above the module-level work:**
  - `docs/GAP_ANALYSIS.md` (TS-083) — what exists and is defective. Closed
    Gates 1–4.
  - `docs/PRODUCT_DISCOVERY_GAPS.md` (TS-126) — what was never built at all.
    Open Gates 5–7. **Headline finding: no user can currently upload their
    own tender** — the hardened upload endpoint has no UI, so the product
    today only analyses its own built-in sample.

## 2. Architecture

Modular monolith. Every feature area is a self-contained, pluggable module
under `backend/app/modules/<name>/`, exposing exactly one entry point
(`module.py`'s `ModuleSpec`). A module imports **only** `app.core.*` and its
own package — cross-module calls go through the service registry
(`app.core.registry`) or the event bus (`app.core.events`), never a direct
import. `soft_deps` degrade gracefully; the app must boot with any subset of
modules enabled (`TS_ENABLED_MODULES`).

Tenant isolation is PostgreSQL Row-Level Security, bound per-request from the
JWT's `workspace` claim (`app.core.db`, `auth/deps.py`) — a documented no-op
on SQLite, which is why every isolation-sensitive change in this project is
verified against real, non-superuser Postgres with FORCE RLS live, not just
the SQLite test suite.

- **Full detail:** [`specs/data-model.md`](data-model.md) (canonical Postgres
  schema + RLS), [`specs/modules/core.md`](modules/core.md) (loader,
  registry, event bus, config).
- **Frontend:** Next.js 15 (App Router) + TypeScript + Tailwind. See
  [`specs/frontend.md`](frontend.md).
- **Full rules:** `CLAUDE.md` (mirrored in `.cursor/rules/` and
  `.devin/rules/`+`DEVIN.md` — keep all in sync when editing).

## 3. Product-critical invariants (never violate)

Restated here so a new reader doesn't have to open `CLAUDE.md` first — the
canonical copy lives there (§4).

- **Numbers never come from the LLM.** BOQ arithmetic, date arithmetic,
  severity scoring are deterministic code.
- **Every extracted fact carries provenance** (`source_page`, verbatim
  `source_quote` ≤200 chars) and passes quote verification before display.
- **Validators are the spine:** no invented quotes, no uncited clauses, no
  invented numbers in generated artifacts.
- **RLS / workspace isolation on every workspace-scoped table.** Cross-tenant
  leakage is company-ending.
- **Webhook is the only billing truth** — client redirects never activate
  anything.
- Tender text is **untrusted input** — prompt-injection defenses apply
  everywhere document text meets an LLM.
- Money in **minor units** (paise), never float.

## 4. Module index

Status reflects the module's own spec (`specs/modules/<name>.md`), which is
the code-level depth layer — read that file for behavior, capabilities,
acceptance criteria. "UI" notes whether the module has a frontend surface at
all (several are backend-only and fully dark — see Gate 7 in
`tasks/TRACKER.md`).

| Module | Purpose | UI? | Spec |
|---|---|---|---|
| `core` | Module loader, service registry, event bus, config, RLS/DB helpers | n/a | [core.md](modules/core.md) |
| `auth` | AuthN/Z, workspaces/projects, RBAC, RLS binding, MFA, invitations, super-admin | partial | [auth.md](modules/auth.md) |
| `billing` | Metering, paywall, Razorpay, GST invoicing, coupons/credits/referrals, entitlements | yes | [billing.md](modules/billing.md) |
| `ingestion` | Upload, classification, clause segmentation, deadline extraction | **no UI for real uploads** (Gate 5, TS-110) | [ingestion.md](modules/ingestion.md) |
| `risk` | Risk-pattern engine (retrieve → classify → verify), deterministic severity | yes | [risk.md](modules/risk.md) |
| `boq` | Deterministic BOQ checks + scope-gap engine, zero LLM | yes | [boq.md](modules/boq.md) |
| `findings` | Shared findings store + `Finding` contract | n/a (consumed by others) | [findings.md](modules/findings.md) |
| `review` | Review workbench, audit log, export gating | **no queue UI** (Gate 5, TS-119) | [review.md](modules/review.md) |
| `drafting` | Artifact generation (clarification letter, assumptions register, bid score) + validators | yes | [drafting.md](modules/drafting.md) |
| `export` | Bid Review Pack export (DOCX/XLSX/PDF), review-gated, watermarked | yes | [export.md](modules/export.md) |
| `baseline` | Hash-sealed baseline freeze, notice register, award-vs-tender delta, handover pack | yes | [baseline.md](modules/baseline.md) |
| `standards` | Org-custom notice standards (prevail / side-by-side) | yes | [standards.md](modules/standards.md) |
| `assistant` | Grounded in-app Q&A, citations mandatory | **deliberately unsurfaced** (product decision — confirm still holds) | [assistant.md](modules/assistant.md) |
| `qualification` | Bid eligibility/qualification extraction | **no UI** (Gate 7, TS-120) | [qualification.md](modules/qualification.md) |
| `timeline` | Milestone calendar + `.ics` export | **no UI** (Gate 7, TS-118 — feed is finished, unreachable) | [timeline.md](modules/timeline.md) |
| `crossref` | Cross-document clause search + change detection | **no UI** (Gate 7, TS-122) | [crossref.md](modules/crossref.md) |
| `comparison` | Cross-tender ranking | **no UI** (Gate 7, TS-121 — build with the dashboard) | [comparison.md](modules/comparison.md) |
| `analytics` | Internal accuracy dashboard (precision/recall/FP/FN by pattern) | **no UI** (Gate 7, TS-102/121) | [analytics.md](modules/analytics.md) |
| `rulepacks` | Versioned risk-pattern/checklist data + loader | **no transparency UI** (Gate 7, TS-123) | [rulepacks.md](modules/rulepacks.md) |
| `notifications` | Deadline-digest logic + pluggable sender | **zero callers** (Gate 5, TS-113 — logic is finished, never runs) | [notifications.md](modules/notifications.md) |
| `health` | Health/module-discovery/capabilities endpoint | n/a | [health.md](modules/health.md) |

## 5. Requirement index

Status matches `tasks/TRACKER.md` (run `python scripts/check_tracker.py` for
the checked, current count — this table is a snapshot).

| Req | Covers | Status |
|---|---|---|
| [R-001](requirements/R-001-tenant-isolation.md) | Workspace/project membership authorization + RLS | done |
| [R-002](requirements/R-002-auth-hardening.md) | Token echo, session revocation, rate limiting, MFA-at-login enforcement | in progress (TS-101 open) |
| [R-003](requirements/R-003-upload-safety.md) | Streaming uploads, size cap, type allowlist, quotas | done (quota/ZIP guards explicitly deferred) |
| [R-004](requirements/R-004-paywall-enforcement.md) | Metering inside the review path + free-tier watermark | done |
| [R-005](requirements/R-005-payments-checkout.md) | Real Razorpay orders, server-side plan/amount binding, webhook coverage | done |
| [R-006](requirements/R-006-coupons-discounts.md) | Coupons, discounts, referral credits, trials, pilot comps | done |
| [R-007](requirements/R-007-gst-invoicing.md) | GST invoicing: tax columns, statutory series, PDF | done |
| [R-008](requirements/R-008-billing-ui.md) | Pricing page, checkout, paywall, invoices, usage meter | done |
| [R-009](requirements/R-009-plan-entitlements.md) | Seat limits, top-ups, billing-anniversary periods | done |
| [R-010](requirements/R-010-frontend-session.md) | Refresh-token storage, 401 interceptor, token custody | done |
| [R-011](requirements/R-011-workspace-switching.md) | Deterministic login workspace, switch endpoint, UI switcher | done |
| [R-012](requirements/R-012-dashboard.md) | Portfolio dashboard consuming the unused `analytics` module | todo (TS-102) |
| [R-013](requirements/R-013-account-ui.md) | Invitation accept, members, MFA, workspace CRUD, admin console | todo (TS-103) |
| [R-014](requirements/R-014-design-system.md) | Component primitives, tokens, `/signup`, error copy, a11y, tests | todo (TS-104; Vitest already seeded by TS-092) |
| [R-015](requirements/R-015-email-verification.md) | Email verification, delivery adapters, anti-abuse | todo (TS-099) |
| [R-016](requirements/R-016-platform-scale.md) | Async pipeline, S3 storage, observability, product metrics | todo (TS-105…TS-109) |
| [R-017](requirements/R-017-document-upload-journey.md) | Real document upload journey (the top release blocker) | todo (TS-110) |
| [R-018](requirements/R-018-opportunity-lifecycle.md) | Opportunity lifecycle + bid/no-bid decision record | todo (TS-111) |
| [R-019](requirements/R-019-record-lifecycle.md) | Archive / delete / restore | todo (TS-112) |
| [R-020](requirements/R-020-deadline-alerting.md) | Deadline alerts actually delivered | todo (TS-113) |
| [R-021](requirements/R-021-audit-and-data-rights.md) | Audit trail beyond review decisions; DPDP data rights | todo (TS-114, TS-115) |
| [R-022](requirements/R-022-team-lifecycle-and-run-recovery.md) | Member removal; processing-failure visibility + retry | todo (TS-116, TS-117) |
| [R-023](requirements/R-023-unexposed-capabilities.md) | Seven finished backends with no UI (timeline, review queue, qualification, comparison, crossref, rulepacks, ops console) | todo (TS-118…TS-125) |

## 6. How this fits the workflow

Every change follows **Requirement → Task → Spec → Implement → Commit →
Changelog** (`CLAUDE.md` §1). Concretely:

1. Find or create the task's row in [`tasks/TRACKER.md`](../tasks/TRACKER.md)
   and its [`tasks/specs/TS-###-*.md`](../tasks/specs/) task file.
2. Read the requirement doc (`specs/requirements/R-0xx-*.md`) if one exists.
3. Update the affected `specs/modules/*.md` **in the same change**.
4. Implement; update the task file's code snippets/tests; run
   `ruff check . && pytest -q` (backend) / `tsc --noEmit && next build`
   (frontend).
5. Flip the `TRACKER.md` row to `done`, update `CHANGELOG.md`, and run
   `python scripts/check_tracker.py` before pushing.
6. Update this file (§4/§5) if the change shifted a module's or
   requirement's status.
