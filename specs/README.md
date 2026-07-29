# Specs

Specifications generated from the requirement source of truth,
`docs/TenderShield_Full_Build_Doc.md` (the "Doc"). Specs are binding: code that
contradicts its spec is a defect in one of the two — fix the mismatch in the same
change (`CLAUDE.md` §1.2).

**Start at [`SYSTEM.md`](SYSTEM.md)** — the living entry point: business goal,
architecture overview, and a module/requirement index with current status.
This file is the per-module/per-doc detail SYSTEM.md's index points into.

## Index

| Spec | Covers | Doc refs |
|---|---|---|
| `000-product-overview.md` | Wedge, personas, scope fences, phase gates | §0, §1, §10, §12 |
| `data-model.md` | Canonical PostgreSQL data model + RLS | §3.2 |
| `phase0-accuracy-test.md` | Week-2 accuracy de-risk experiment | §19 |
| `frontend.md` | Next.js app structure + UX principles | §9 |
| `modules/core.md` | Pluggable module framework (registry, events, loader) | §3.1 |
| `modules/rulepacks.md` | Contract rule-packs: structure, governance, loader | §2, §14 |
| `modules/auth.md` | AuthN/AuthZ, workspaces/projects, RBAC, RLS binding | §5 |
| `modules/ingestion.md` | Upload, classification, deadlines, clause segmentation | §3.3, §6.1–6.2 |
| `modules/risk.md` | Risk-pattern engine | §6.3 |
| `modules/boq.md` | Deterministic BOQ engine + scope gaps | §6.4 |
| `modules/drafting.md` | Artifact generation + validators + export | §6.5, §11.4 |
| `modules/review.md` | Review workbench, audit log, export gating | §1.1(7), §11.4 |
| `modules/billing.md` | Metering, paywall, Razorpay/Stripe, payment_log | §7, §15, §16.5 |
| `modules/assistant.md` | Grounded in-app assistant | §8 |
| `modules/baseline.md` | Baseline lock: hash-sealed freeze, notice register, handover | §0.1, §10, §1.2 |
| `modules/standards.md` | Org-custom notice standards (prevail / side-by-side layer) | §10, §0.1, §2 |
| `modules/findings.md` | Shared findings table + store capability | §3.2, §6.3, §6.4, §11.4 |
| `modules/export.md` | Bid Review Pack export (DOCX/XLSX/PDF) with review gate | §1.1(8), §6.5, §11.4 |
| `modules/health.md` | Health / module discovery / capabilities endpoint | §11.1 |
| `modules/notifications.md` | Deadline-digest notification sender abstraction | §11.6, §11.7 |
| `modules/qualification.md` | Bid eligibility/qualification extraction (Phase 1.5) | Phase 1.5 doc §5 |
| `modules/timeline.md` | Milestone calendar + `.ics` export (Phase 1.5) | Phase 1.5 doc §5 |
| `modules/crossref.md` | Cross-document clause search + change detection (Phase 1.5) | Phase 1.5 doc §5 |
| `modules/comparison.md` | Cross-tender ranking (Phase 1.5) | Phase 1.5 doc §5 |
| `modules/analytics.md` | Internal accuracy dashboard (Phase 1.5) | Phase 1.5 doc §5 |

## Requirements (`specs/requirements/`)

Implementation-ready requirement documents (`R-001`…`R-023` and counting)
derived from two audits: the gap analysis (`docs/GAP_ANALYSIS.md`, TS-083,
Gates 1–4 — what exists and is defective) and the product-discovery audit
(`docs/PRODUCT_DISCOVERY_GAPS.md`, TS-126, Gates 5–7 — what was never built
at all). They sit between the build doc and the module specs: business/
behavior-level (Purpose, target behavior, acceptance criteria) — code-level
detail lives in the task file(s) that implement them
(`tasks/specs/TS-###-*.md`), never blended into the requirement doc itself.
Index and conventions: `specs/requirements/README.md`. Master tracker (the
one place to see done vs. left): `tasks/TRACKER.md`, checked by
`python scripts/check_tracker.py`.

A requirement doc names the module specs it changes; those specs must be updated
in the same commit as the implementation (`CLAUDE.md` §1.2).

## Template (use for every new spec)

```markdown
# <Name> — Spec

**Status:** draft | agreed | implemented
**Requirement refs:** Doc §…
**Task refs:** TS-…

## Purpose
One paragraph: why this exists.

## Public interface
- **Capabilities published** (service registry names) / **consumed** (soft deps)
- **Events emitted / consumed**
- **API routes**

## Data owned
Tables/files this module owns. Other modules reference by ID + events only.

## Behavior
The rules. Number them so tests and reviews can cite them (B1, B2, …).

## Acceptance criteria
Checkable statements (A1, A2, …) — these become tests.

## Out of scope
What this deliberately does not do (and which phase it's deferred to).

## Assumptions
Anything not backed by the Doc, marked explicitly.
```
