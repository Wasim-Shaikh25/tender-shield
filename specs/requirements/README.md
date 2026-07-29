# Requirements — R-001 … R-023 (and counting)

Detailed requirement documents from two audits: the gap analysis
(`docs/GAP_ANALYSIS.md`, TS-083 — Gates 1–4, what exists and is defective) and
the product-discovery audit (`docs/PRODUCT_DISCOVERY_GAPS.md`, TS-126 — Gates
5–7, what was never built at all). Each is scoped to a single change and
carries acceptance criteria that become tests.

These sit **between** the build doc and the module specs — and, since the
requirement/task restructure, **above** the task files that hold the
code-level detail:

```
docs/TenderShield_Full_Build_Doc.md   ← requirement source of truth (why)
specs/requirements/R-0xx-*.md         ← this layer (business/behavior: what, and why it matters)
tasks/specs/TS-###-*.md               ← code-level detail (current vs. target code, file:line, tests)
specs/modules/<name>.md               ← module contract (updated by the change)
backend/app/modules/<name>/           ← implementation
```

**Note on the transition:** requirement docs written before this restructure
(most of R-001…R-016) still carry large `Current`/`Target` code blocks
inline — that detail is being moved out into each doc's task file(s) as part
of the retrofit (see `tasks/TRACKER.md`'s intro). A doc that still has its
code blocks inline hasn't been split yet; that's in progress, not a
different convention.

## How to work one of these

1. Find or create the task's row in `tasks/TRACKER.md` (single master
   tracker) and its file at `tasks/specs/TS-###-*.md`.
2. Read the R-doc fully for the requirement; read the task file for the
   code-level detail (current code, target code, tests) once it exists.
3. Update the affected `specs/modules/*.md` **in the same change** (`CLAUDE.md` §1.2).
4. Implement, run `ruff check . && pytest -q` (backend) or
   `tsc --noEmit && next build` (frontend); commit with the `TS-###` in the body.
5. Tick the acceptance criteria in the task file and tracker row; add the
   CHANGELOG entry; run `python scripts/check_tracker.py`.

Code snippets — wherever they currently live — are **reference
implementations**, not copy-paste-and-ship. They show the intended shape,
the module-boundary rules they must respect, and the edge cases that must be
handled.

## Index

Status matches `tasks/TRACKER.md` — see `specs/SYSTEM.md` §5 for a
requirement-level status table, or run `python scripts/check_tracker.py` for
the checked, per-task count.

### Gate 1 — Stop the leaks (blocks any real customer data) — done

| Doc | Covers | Tasks | Severity |
|---|---|---|---|
| [R-001](R-001-tenant-isolation.md) | Workspace/project membership authorization + RLS that actually isolates | TS-084, TS-086 | P0 |
| [R-002](R-002-auth-hardening.md) | Reset-token echo, session revocation, rate limiting, MFA enforcement | TS-085, TS-093, TS-094, TS-101 | P0/P1 |
| [R-003](R-003-upload-safety.md) | Streaming uploads, size cap before buffering, type allowlist, quotas | TS-095 | P1 |

### Gate 2 — Make it possible to get paid — done

| Doc | Covers | Tasks | Severity |
|---|---|---|---|
| [R-004](R-004-paywall-enforcement.md) | Metering inside the review path + free-tier watermark | TS-087, TS-088 | P0 |
| [R-005](R-005-payments-checkout.md) | Real Razorpay orders, server-side plan/amount binding, full webhook coverage | TS-089, TS-097 | P0 |
| [R-006](R-006-coupons-discounts.md) | Coupons, discounts, referral credits, trials, pilot comps | TS-090 | P1 |
| [R-007](R-007-gst-invoicing.md) | Wire `gst.py` into invoices: tax columns, statutory series, PDF | TS-096 | P1 |
| [R-008](R-008-billing-ui.md) | Pricing page, checkout, paywall interstitial, invoices, usage meter | TS-091 | P0 |
| [R-009](R-009-plan-entitlements.md) | Seat limits, top-ups, billing-anniversary periods, entitlement service | TS-098 | P1 |

### Gate 3 — Make it usable — in progress (2/7)

| Doc | Covers | Tasks | Severity |
|---|---|---|---|
| [R-010](R-010-frontend-session.md) | Refresh-token storage, 401 interceptor, token custody | TS-092 | P0 |
| [R-011](R-011-workspace-switching.md) | `POST /auth/workspaces/{id}/switch` + UI switcher | TS-100 | P1 |
| [R-012](R-012-dashboard.md) | Portfolio dashboard consuming the unused `analytics` module | TS-102 | P1 |
| [R-013](R-013-account-ui.md) | Invitation accept, members, MFA, workspace CRUD, admin console | TS-103 | P1 |
| [R-014](R-014-design-system.md) | Component primitives, tokens, `/signup`, error copy, a11y, tests | TS-104 | P2 |
| [R-015](R-015-email-verification.md) | Email verification, delivery adapters, anti-abuse | TS-099 | P1 |

### Gate 4 — Scale and prove — todo

| Doc | Covers | Tasks | Severity |
|---|---|---|---|
| [R-016](R-016-platform-scale.md) | Async pipeline, S3 storage, observability, product metrics, legal surface | TS-105…TS-109 | P1/P2 |

### Gate 5 — Make the core journey real — todo

| Doc | Covers | Tasks | Severity |
|---|---|---|---|
| [R-017](R-017-document-upload-journey.md) | Real document upload journey — no UI exists for the hardened upload endpoint | TS-110 | P0 |
| [R-018](R-018-opportunity-lifecycle.md) | Opportunity lifecycle + bid/no-bid decision record | TS-111 | P0 |
| [R-019](R-019-record-lifecycle.md) | Archive / delete / restore | TS-112 | P0 (archive) |
| [R-020](R-020-deadline-alerting.md) | Deadline alerts actually delivered (`digest.py` has zero callers) | TS-113 | P0 |
| [R-023](R-023-unexposed-capabilities.md) | Review queue + audit viewer UI (gates the paid export path) | TS-119 | P0 |

### Gate 6 — Trust, recovery and compliance — todo

| Doc | Covers | Tasks | Severity |
|---|---|---|---|
| [R-021](R-021-audit-and-data-rights.md) | Audit trail beyond review decisions; DPDP data rights | TS-114, TS-115 | P1 |
| [R-022](R-022-team-lifecycle-and-run-recovery.md) | Member removal + invitation lifecycle; processing-failure recovery | TS-116, TS-117 | P0/P1 |

### Gate 7 — Expose what is already built — todo

| Doc | Covers | Tasks | Severity |
|---|---|---|---|
| [R-023](R-023-unexposed-capabilities.md) | Six more finished backends with no UI: timeline/`.ics`, qualification, comparison, crossref, rulepacks, ops console | TS-118, TS-120…TS-125 | P1/P2 |

## Conventions used in every doc

- **`Current`** blocks (where still present — see the transition note above)
  quote the code as it exists today, with `file:line`.
- **`Target`** blocks (ditto) are the reference implementation.
- **B-numbered behaviors** and **A-numbered acceptance criteria** match the
  `specs/README.md` template so they can be cited from tests, task files, and
  reviews.
- Module-boundary rule (`CLAUDE.md` §2) is respected throughout: no
  `app.modules.<other>` imports — cross-module calls go through the service
  registry or the event bus.
- Money is always minor units (paise). Numbers never come from an LLM.
- Findings from the discovery audit (R-017…R-023) additionally carry a
  classification — Confirmed Missing Requirement / Strongly Implied /
  Domain-Expected / Clarification Required — explained in
  `docs/PRODUCT_DISCOVERY_GAPS.md`.
