# Specs

Specifications generated from the requirement source of truth,
`docs/TenderShield_Full_Build_Doc.md` (the "Doc"). Specs are binding: code that
contradicts its spec is a defect in one of the two — fix the mismatch in the same
change (`CLAUDE.md` §1.2).

## Index

| Spec | Covers | Doc refs |
|---|---|---|
| `000-product-overview.md` | Wedge, personas, scope fences, phase gates | §0, §1, §10, §12 |
| `data-model.md` | Canonical PostgreSQL data model + RLS | §3.2 |
| `phase0-accuracy-test.md` | Week-2 accuracy de-risk experiment | §19 |
| `frontend.md` | Next.js app structure + UX principles | §9 |
| `modules/core.md` | Pluggable module framework (registry, events, loader) | §3.1 |
| `modules/rulepacks.md` | Contract rule-packs: structure, governance, loader | §2, §14 |
| `modules/auth.md` | AuthN/AuthZ, orgs, RBAC, RLS binding | §5 |
| `modules/ingestion.md` | Upload, classification, deadlines, clause segmentation | §3.3, §6.1–6.2 |
| `modules/risk.md` | Risk-pattern engine | §6.3 |
| `modules/boq.md` | Deterministic BOQ engine + scope gaps | §6.4 |
| `modules/drafting.md` | Artifact generation + validators + export | §6.5, §11.4 |
| `modules/review.md` | Review workbench, audit log, export gating | §1.1(7), §11.4 |
| `modules/billing.md` | Metering, paywall, Razorpay/Stripe, payment_log | §7, §15, §16.5 |
| `modules/assistant.md` | Grounded in-app assistant | §8 |
| `modules/baseline.md` | Baseline lock: freeze, watchlist, notice register, cost codes, handover | §0.1, §10, Research §4.E |
| `modules/standards.md` | Org-custom notice standards (prevail / side-by-side layer) | §10, §0.1, §2 |
| `modules/findings.md` | Shared findings table + store capability | §3.2, §6.3, §6.4, §11.4 |
| `modules/export.md` | Bid Review Pack export (DOCX/XLSX/PDF) with review gate | §1.1(8), §6.5, §11.4 |
| `modules/health.md` | Health / module discovery / capabilities endpoint | §11.1 |
| `modules/notifications.md` | Deadline-digest notification sender abstraction | §11.6, §11.7 |
| `eval-at-scale.md` | Automated evaluation on 1,000+ real tenders across countries (M1–M5 scoring, corpus, runner) | §11.5, §19; Strategy §A.2 |
| `modules/marketdata.md` | Employer Behaviour Graph from public award records | Strategy §C.1 |
| `modules/pricing-intel.md` | Risk-to-price loading, SOR benchmarking, cashflow model | Strategy §C.2–C.4 |
| `modules/express-report.md` | Pay-per-report lane (no subscription) | §7, §15, §11.4; Strategy §F.2 |
| `modules/outcomes.md` | Bid outcome + risk materialization capture | §1.1(9), §11.5; Strategy §C.6 |
| `900-production-readiness-audit-fixes.md` | Cross-cutting hardening and product completeness from audit | `PRODUCTION_READINESS_AUDIT.md` |
| `901-post-audit-remaining-fixes.md` | Second batch of audit fixes after TS-083–TS-092 | `PRODUCTION_READINESS_AUDIT.md` |
| `902-changelog-check.md` | CI gate enforcing `CHANGELOG.md` updates on code-changing PRs | `CLAUDE.md` §1.5 |

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
