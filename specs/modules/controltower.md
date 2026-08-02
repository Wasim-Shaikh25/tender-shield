# Control Tower — Spec

**Status:** draft
**Requirement refs:** Research Doc §4.H; `docs/TenderShield_Roadmap_Stage1_to_5.md` §4 Stage 5
**Task refs:** TS-271, TS-272, TS-273

## Purpose

A portfolio-level commercial control tower for construction contractors. It aggregates claim,
change, baseline, deadline, and evidence data into deterministic exposure metrics so a commercial
manager can see at-risk revenue, unnotified change, submitted/certified/rejected claim value,
ageing, and cash exposure per project and across the workspace.

## Public interface

### Capabilities published

- `controltower.service_factory` → `ControlTowerService(session)`.
- `controltower.exposure_for_opportunity` — deterministic exposure snapshot for one opportunity.
- `controltower.dashboard_for_opportunity` — deadline + evidence-health summary for one opportunity.
- `controltower.portfolio_summary` — workspace-level rollup of exposure, claim status counts, and
  evidence-health averages.

### Capabilities consumed (soft)

| Capability | Use |
|---|---|
| `ingestion.service_factory` | List opportunities and contract value (when `Opportunity.contract_value_minor` is set). |
| `claims.service_factory` / `claims.list_for_opportunity` | Claim value and status. |
| `change.events_for_opportunity` | Unnotified / unclaimed change events. |
| `evidence.completeness_for_event` | Evidence-health score per change event. |
| `outcomes.service_factory` / `outcomes.margin_protected` | Workspace north-star context. |

### Events emitted

- `controltower.exposure_computed` — emitted after a per-opportunity exposure snapshot is
  generated, with the totals and timestamp.

### API routes (prefix `/api/controltower`)

- `GET /exposure?opportunity_id={id}` (viewer) — per-project exposure model.
- `GET /dashboard?opportunity_id={id}` (viewer) — deadline + evidence-health dashboard.
- `GET /portfolio` (viewer) — workspace rollup.

## Data owned

None for the first slice (TS-271–TS-273). The control tower reads from other modules via the
registry and computes live snapshots. A future slice may persist `ct_exposure_snapshots` for
trending.

## Behavior

### Exposure model (B1–B7, TS-272)

The model is deterministic and uses only explicit values already in the platform. No numbers are
invented.

- **B1 — Contract value anchor.** If `Opportunity.contract_value_minor` is set, it is used as
the revenue base; otherwise the revenue base is `None` and at-risk revenue is omitted.
- **B2 — Submitted value.** Sum of `claim_amount_minor` for all claims on the opportunity with
status in `submitted`, `under_review`, `negotiated`, or `disputed`.
- **B3 — Certified value.** Sum of `recovered_amount_minor` for claims with status `settled`.
- **B4 — Rejected/withdrawn value.** Sum of `claim_amount_minor` for claims with status `rejected`
or `withdrawn`.
- **B5 — Unnotified change value.** Sum of `claim_amount_minor` on linked `draft` claims that have
a `change_event_id` but are not yet `submitted`. For change events with no linked claim, the value
is reported as an unclaimed event count, not a rupee value.
- **B6 — Ageing.** For each unsettled claim (status `submitted`, `under_review`, `negotiated`,
`disputed`), `age_days = today - submitted_at`; average and max are exposed.
- **B7 — Cash exposure (financing cost).** Sum over unsettled claims of
`claim_amount_minor * age_days * (cost_of_capital_pa / 365)`. `cost_of_capital_pa` is a
query parameter defaulting to `0.12` (12%) and is never assumed without being explicit.

### Deadline + evidence-health dashboard (B8–B11, TS-273)

- **B8 — Deadline list.** All `deadlines` for the opportunity, sorted by `due_at`, with status
`overdue`, `due_soon` (< 7 days), or `ok`.
- **B9 — Evidence health.** For every confirmed change event on the opportunity, compute evidence
completeness via `evidence.completeness_for_event`. Average the score and list events whose
completeness is below 100%.
- **B10 — Unclaimed change events.** Confirmed change events with no linked submitted claim are
surfaced as notices at risk.
- **B11 — Degradation.** If `change` or `evidence` is disabled, the dashboard omits those sections
and returns an explicit `unavailable` flag.

### Portfolio summary (B12)

- **B12 — Workspace rollup.** Sum the per-opportunity exposure totals across all opportunities in
the workspace; also count opportunities by evidence-health tier (`healthy` ≥ 80,
`at_risk` 50–79, `poor` < 50).

## Acceptance criteria

- A1 (TS-271): `GET /api/controltower/exposure?opportunity_id=...` returns deterministic totals
  without invented numbers.
- A2 (TS-272): `submitted_minor`, `certified_minor`, `rejected_minor`, `unnotified_minor`,
  `age_days_avg`, and `cash_exposure_minor` are present in the exposure response.
- A3 (TS-273): `GET /api/controltower/dashboard?opportunity_id=...` returns deadlines,
  evidence-health score, and unclaimed change events.
- A4 (TS-273): `GET /api/controltower/portfolio` returns a workspace rollup.
- A5: Disabling `claims` or `change` does not crash the control tower; unavailable sections are
  marked.

## Out of scope

- TS-274 risk-adjusted forecast at completion.
- TS-275 client/consultant response-time analytics.
- TS-276 portfolio clause trends and loss-reason analysis.
- TS-277 executive summaries with source links and drill-down.
- TS-278 payment control (RA/progress bills, retention, collection).
- TS-279 economics metrics (paid conversion, gross margin, CAC).
- TS-280 customer-outcome metrics.

## Assumptions

- `assumption:` `Opportunity.contract_value_minor` is added as part of the Phase 20 foundation
  (tracks TS-296) because at-risk revenue cannot be computed without an explicit contract value.
- `assumption:` `claims` exposes a list capability so `controltower` never imports the claims
  module directly.
