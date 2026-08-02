# Tender Comparison — Spec

**Status:** implemented (TS-050)  
**Requirement refs:** Phase 1.5 doc §3  
**Task ref:** TS-050

## Purpose

A portfolio-level pre-bid view that ranks every opportunity in the org so
estimators can decide where to spend their time. It surfaces the same signals
that already exist in the product — risk, qualification, BOQ quality, deadline,
bid readiness — as a single sorted list.

## Public interface

- **Capability published:** `comparison.service_factory`.
- **Capabilities consumed (soft):**
  - `ingestion.service_factory` — opportunities + deadlines.
  - `findings.store_factory` — risk / qualification / BOQ / standard findings.
  - `drafting.service_factory` — latest `bid_decision` artifact.
- **Events:** none.
- **API routes** (prefix `/api/comparison`):
  - `GET /opportunities` — portfolio comparison for the caller's org.
  - `GET /opportunities/{opportunity_id}/deviation` — per-clause deviation scoring
    against the workspace commercial standard/playbook (TS-317).

## Data owned

None. The module is a read-only aggregator over other modules' tables, accessed
through their service factories.

## Behavior

- **B1 — Read-only aggregation.** For each org opportunity, collect:
  - `submission_due` / `days_to_submission` from the opportunity or earliest
    `bid_submission` deadline.
  - Finding counts by `kind` and `severity` from the shared findings store.
  - Latest `bid_decision` artifact `score` and `recommendation` from `drafting`.
- **B2 — Normalised metrics.** The response exposes raw counts so the frontend
  can render its own table, plus a backend-computed `priority_score` and `rank`
  for stable default sorting.
- **B3 — Ranking.** Sort order is deterministic:
  1. `recommendation` (`proceed` > `proceed_with_conditions` > `do_not_proceed` > none).
  2. `bid_readiness_score` descending (treat missing as 0).
  3. Risk `critical` count ascending.
  4. `days_to_submission` ascending (missing last).
- **B4 — Org isolation.** All reads are scoped to the authenticated `org_id` by
  delegating to ingestion/findings/drafting services, which enforce their own
  org filters.
- **B5 — Graceful degradation.** Missing factories or ungenerated bid decisions
  produce `null`/`0` values, never 500 errors.
- **B6 — Clause deviation scoring (TS-317).** The service consumes
  `standards.commercial_service_factory` and `ingestion.service_factory`. For each
  clause, it checks the workspace's commercial policies (`applies_to` keywords and
  numeric thresholds) and computes a normalised `deviation_score` when the clause
  violates a policy. Scores are positive for `gt`/`gte` violations and negative for
  `lt`/`lte` violations. The response returns per-clause rows plus an
  `overall_deviation_score`.

## Response shape

```jsonc
{
  "opportunities": [
    {
      "id": "<uuid>",
      "title": "Bridge",
      "submission_due": "2026-08-05T17:00:00",
      "days_to_submission": 10,
      "risk": {"critical": 0, "high": 1, "medium": 2, "low": 0, "info": 0},
      "qualification_gaps": 1,
      "boq_defects": 0,
      "standard_violations": 0,
      "bid_readiness_score": 74,
      "recommendation": "proceed_with_conditions",
      "priority_score": 74.0,
      "rank": 1
    }
  ]
}
```

`priority_score` is a float derived from the sorting keys for stable ranking.

## Acceptance criteria

- A1: `GET /api/comparison/opportunities` returns all org opportunities with
  the fields above.
- A2: Opportunities with a generated `bid_decision` outrank those without.
- A3: Sort is stable and deterministic across identical data.
- A4: The endpoint works even when `drafting` is disabled (score/recommendation
  `null`).
- A5 (TS-317): `GET /api/comparison/opportunities/{id}/deviation` returns per-clause
  scores and an overall score; clauses that do not violate any policy show a score of `0`.

## Out of scope

- Cross-org portfolio views (admin only, P3).
- Margins / estimating data (requires estimating module, not Phase 1.5).
- Real-time updates; the comparison is computed on request.
