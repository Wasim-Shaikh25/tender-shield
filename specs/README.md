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
| `modules/baseline.md` | Baseline lock: hash-sealed freeze, notice register, handover | §0.1, §10, §1.2 |
| `modules/standards.md` | Org-custom notice standards (prevail / side-by-side layer) | §10, §0.1, §2 |

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
