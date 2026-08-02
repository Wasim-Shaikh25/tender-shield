# Phase 20 — Commercial Control Tower & Portfolio Intelligence — Tracker

**Requirement source:** Research Doc §4.H, §12.2; `docs/TenderShield_Roadmap_Stage1_to_5.md` §4 Stage 5
**Specs:** `specs/modules/controltower.md` (primary), `specs/modules/analytics.md`
**Backlog:** `tasks/backlog.md` §Phase 20 (TS-271 – TS-280)
**Master roadmap:** `docs/TenderShield_Roadmap_Stage1_to_5.md` · `tasks/roadmap_tracker.md`

**Phase goal.** Aggregate project-level claim, change, evidence, and deadline data into a
commercial control tower that exposes at-risk revenue, unnotified change, submitted/certified
claim value, ageing, and cash exposure.

**Unlock gate:** Phase 19 in production use with at least one customer.

**Phase exit gate.** A contractor can open the control tower and see, per project and across the
workspace: exposure totals, a deadline/evidence-health dashboard, and a portfolio rollup without
invented numbers.

---

## Sprint map

| Sprint | Theme | Tasks | Exit gate | Status |
|---|---|---|---|---|
| **0** | **Spec + scaffold** | TS-271, TS-272 | `controltower.md` agreed; module boots; exposure model computed | done |
| **1** | **Dashboard** | TS-273 | Deadline + evidence-health dashboard per opportunity | done |
| **2** | **Portfolio + forecast** | TS-274, TS-275, TS-276 | Portfolio rollup; response-time analytics; clause trends | done |
| **3** | **Payment + economics** | TS-277, TS-278, TS-279, TS-280 | Payment control; executive summaries; economics metrics | done |

### Why this order

**Spec before tables (TS-271 → TS-272).** The exposure model defines what data must be aggregated
before the dashboard can render it.

**Exposure before dashboard (TS-272 → TS-273).** The dashboard layers deadline and evidence-health
information on top of the exposure numbers.

---

## Task table

| ID | Title | Module | Priority | Status | Acceptance (short) | Blockers |
|---|---|---|---|---|---|---|
| TS-271 | Spec: `controltower` module | `controltower` | P0 | done | Spec in `specs/modules/controltower.md` | Phase 19 |
| TS-272 | Commercial exposure model | `controltower` | P0 | done | Deterministic submitted/certified/rejected/unnotified/ageing/cash exposure | TS-271 |
| TS-273 | Project deadline + evidence-health dashboard | `controltower` | P1 | done | Per-opportunity deadline list + evidence-health + unclaimed events | TS-272 |
| TS-274 | Risk-adjusted forecast at completion | `controltower` | P1 | done | Explicit assumptions block; deterministic | TS-273 |
| TS-275 | Client / consultant response-time analytics | `controltower` + `analytics` | P1 | done | Response-time percentiles per counterparty | TS-272 |
| TS-276 | Portfolio clause trends and loss-reason analysis | `analytics` | P1 | done | Cross-project pattern rollup | TS-273 |
| TS-277 | Executive summaries with source links | `controltower` | P1 | done | Drill-down to source documents | TS-273 |
| TS-278 | Payment control | `controltower` | P1 | done | RA/progress bill checklist, retention, ageing | TS-272 |
| TS-279 | Economics metrics | `analytics` | P1 | done | Paid conversion, gross margin, CAC payback | TS-278 |
| TS-280 | Customer-outcome metrics | `analytics` | P1 | done | Risks priced, bad bids declined, omissions corrected | TS-276 |

---

## Product invariants (Phase 20)

- **Numbers never from the LLM** — exposure, ageing, and cash exposure are deterministic code
  (`CLAUDE.md` §4).
- **Explicit contract value** — `Opportunity.contract_value_minor` must be set before at-risk
  revenue is reported; otherwise the metric is omitted, not invented.
- **No cross-module imports** — `controltower` consumes `claims`, `change`, `evidence`, `outcomes`,
  and `ingestion` only through the registry.
