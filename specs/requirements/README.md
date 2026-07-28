# Requirements — gap remediation (R-001 … R-016)

Detailed, implementation-ready requirement documents derived from
`docs/GAP_ANALYSIS.md` (TS-083). Each one is scoped to a single change, cites the
exact code it replaces, and carries acceptance criteria that become tests.

These sit **between** the build doc and the module specs:

```
docs/TenderShield_Full_Build_Doc.md   ← requirement source of truth (why)
specs/requirements/R-0xx-*.md         ← this layer (what exactly, with code)
specs/modules/<name>.md               ← module contract (updated by the change)
backend/app/modules/<name>/           ← implementation
```

## How to work one of these

1. Move its tasks to `in-progress` in `tasks/gap_remediation_tracker.md`.
2. Read the R-doc fully. It states the current code, the target code, the data
   model delta and the tests.
3. Update the affected `specs/modules/*.md` **in the same change** (`CLAUDE.md` §1.2).
4. Implement, run `ruff check . && pytest -q`, commit with the `TS-###` in the body.
5. Tick the acceptance criteria in the tracker; add the CHANGELOG entry.

Code snippets in these documents are **reference implementations**, not
copy-paste-and-ship. They show the intended shape, the module-boundary rules they
must respect, and the edge cases that must be handled.

## Index

### Gate 1 — Stop the leaks (blocks any real customer data)

| Doc | Covers | Tasks | Severity |
|---|---|---|---|
| [R-001](R-001-tenant-isolation.md) | Workspace/project membership authorization + RLS that actually isolates | TS-084, TS-086 | P0 |
| [R-002](R-002-auth-hardening.md) | Reset-token echo, session revocation, rate limiting, MFA enforcement | TS-085, TS-093, TS-094, TS-101 | P0/P1 |
| [R-003](R-003-upload-safety.md) | Streaming uploads, size cap before buffering, type allowlist, quotas | TS-095 | P1 |

### Gate 2 — Make it possible to get paid

| Doc | Covers | Tasks | Severity |
|---|---|---|---|
| [R-004](R-004-paywall-enforcement.md) | Metering inside the review path + free-tier watermark | TS-087, TS-088 | P0 |
| [R-005](R-005-payments-checkout.md) | Real Razorpay orders, server-side plan/amount binding, full webhook coverage | TS-089, TS-097 | P0 |
| [R-006](R-006-coupons-discounts.md) | Coupons, discounts, referral credits, trials, pilot comps | TS-090 | P1 |
| [R-007](R-007-gst-invoicing.md) | Wire `gst.py` into invoices: tax columns, statutory series, PDF | TS-096 | P1 |
| [R-008](R-008-billing-ui.md) | Pricing page, checkout, paywall interstitial, invoices, usage meter | TS-091 | P0 |
| [R-009](R-009-plan-entitlements.md) | Seat limits, top-ups, billing-anniversary periods, entitlement service | TS-098 | P1 |

### Gate 3 — Make it usable

| Doc | Covers | Tasks | Severity |
|---|---|---|---|
| [R-010](R-010-frontend-session.md) | Refresh-token storage, 401 interceptor, token custody | TS-092 | P0 |
| [R-011](R-011-workspace-switching.md) | `POST /auth/workspaces/{id}/switch` + UI switcher | TS-100 | P1 |
| [R-012](R-012-dashboard.md) | Portfolio dashboard consuming the unused `analytics` module | TS-102 | P1 |
| [R-013](R-013-account-ui.md) | Invitation accept, members, MFA, workspace CRUD, admin console | TS-103 | P1 |
| [R-014](R-014-design-system.md) | Component primitives, tokens, `/signup`, error copy, a11y, tests | TS-104 | P2 |
| [R-015](R-015-email-verification.md) | Email verification, delivery adapters, anti-abuse | TS-099 | P1 |

### Gate 4 — Scale and prove

| Doc | Covers | Tasks | Severity |
|---|---|---|---|
| [R-016](R-016-platform-scale.md) | Async pipeline, S3 storage, observability, product metrics | TS-105…TS-108 | P1/P2 |

## Conventions used in every doc

- **`Current`** blocks quote the code as it exists today, with `file:line`.
- **`Target`** blocks are the reference implementation.
- **B-numbered behaviors** and **A-numbered acceptance criteria** match the
  `specs/README.md` template so they can be cited from tests and reviews.
- Module-boundary rule (`CLAUDE.md` §2) is respected throughout: no
  `app.modules.<other>` imports — cross-module calls go through the service
  registry or the event bus.
- Money is always minor units (paise). Numbers never come from an LLM.
