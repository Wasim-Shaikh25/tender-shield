# Internal Accuracy Dashboard — Spec

**Status:** implemented (TS-057, expanded TS-174)  
**Requirement refs:** Phase 1.5 doc §10, user request (end-to-end scenarios §64)  
**Task refs:** TS-057, TS-174, TS-268

## Purpose

An internal, admin-only dashboard for the TenderShield team to monitor rule and
review quality. It aggregates review outcomes on the shared findings table and
produces precision/recall proxies, false-positive signals, and per-pattern
performance telemetry.

## Public interface

- **Capability published:** `analytics.service_factory`.
- **Capabilities consumed (soft):**
  - `findings.store_factory` — all org findings and review states.
  - `ingestion.service_factory` — opportunity list (optional, for per-opportunity
    roll-ups).
  - `baseline.sealed_opportunity_count` — distinct opportunities with ≥1 sealed baseline
    (TS-242).
  - `review.baseline_activity_metrics` — weekly active baseline users and projects from
    the append-only audit log (TS-242).
  - `claims.cycle_metrics` — claim cycle time and notice-timeliness per opportunity
    (TS-268).
- **Events:** none.
- **API routes** (prefix `/api/analytics`):
  - `GET /accuracy` — admin-only accuracy dashboard.
  - `GET /baseline-adoption` — admin-only baseline adoption telemetry (TS-242).
  - `GET /risk-summary` — workspace risk findings grouped by severity and category.
  - `GET /deadline-dashboard` — opportunities expiring in 7/15/30 days and overdue.
  - `GET /boq-defect-summary` — BOQ defects by trade and defect type.
  - `GET /claim-metrics` — claim cycle time, notice timeliness, and status counts
    (TS-268; consumed from `claims.cycle_metrics`).
  - `POST /reports/export` — export a filtered report to CSV/XLSX/PDF.

## Data owned

None. Read-only aggregator over findings and opportunities.

## Behavior

- **B1 — Admin-only.** Route guarded by `require("admin")` / `owner`.
- **B2 — Summary telemetry.** Total findings and counts by review status
  (`proposed`, `accepted`, `edited`, `rejected`, `false_positive`,
  `needs_clarification`).
- **B3 — Precision proxy.** `precision = accepted / (accepted + rejected + false_positive)`.
  Recall and false negatives are reported as `null` unless an external golden
  label feed is supplied, because true negatives and missed clauses cannot be
  inferred from review outcomes alone.
- **B4 — Per-pattern breakdown.** Grouped by `pattern_id` (falling back to `kind`)
  with status counts and the same precision proxy.
- **B5 — Per-source (producer) breakdown.** Grouped by `producer` (risk, boq,
  qualification, standards, etc.) to spot which pipeline produces the most
  rejections / false positives.
- **B6 — Most-rejected patterns.** Patterns ranked by `rejected + false_positive`
  descending.
- **B7 — Graceful degradation.** If `findings` is unavailable the dashboard
  returns zeros/nulls, never 500.
- **B8 — Risk summary.** `GET /risk-summary` returns counts of findings by
  `severity` and `category` for the workspace, plus a total exposure in minor units.
- **B9 — Deadline dashboard.** `GET /deadline-dashboard` returns opportunities
  grouped by `overdue`, `7_days`, `15_days`, `30_days`, and `later`, based on the
  earliest `submission_due` for each opportunity.
- **B10 — BOQ defect summary.** `GET /boq-defect-summary` returns BOQ findings
  (`producer='boq'`) grouped by `affected_trades` and `category`.
- **B11 — Report export.** `POST /reports/export` accepts `format` (`csv|xlsx|pdf`)
  and `filter` (`risk|boq|deadlines|all`) and returns a downloadable file. Export
  runs are bounded by the workspace context and respect date-range filters.
- **B12 — Baseline adoption (TS-242).** `GET /baseline-adoption` reports:
  - `opportunities_with_sealed_baseline` — distinct opportunities with ≥1 sealed baseline.
  - `weekly_active_baseline_users` — distinct users with `baseline.sealed` or
    `export.handover_created` audit events in the rolling 7-day window.
  - `weekly_active_baseline_opportunities` — distinct opportunities with baseline activity
    in the same window (measures the Phase 18 unlock gate: *two projects use baseline
    weekly*).
  - `phase_18_gate.met` — `true` when `weekly_active_baseline_opportunities >= 2`.
  Degrades to zeros when `baseline` or `review` capabilities are absent.

## Response shape

```jsonc
{
  "summary": {
    "total_findings": 120,
    "by_status": { "accepted": 80, "rejected": 20, "false_positive": 10, "needs_clarification": 5, "proposed": 5 },
    "precision": 0.73,
    "recall": null,
    "false_positive_count": 10,
    "false_negative_count": null
  },
  "per_pattern": [
    { "pattern_id": "payment-delay-30", "kind": "risk_clause", "total": 12, "accepted": 9, "rejected": 2, "false_positive": 1, "precision": 0.75 }
  ],
  "per_source": [
    { "producer": "risk", "total": 60, "accepted": 45, "rejected": 10, "false_positive": 5 }
  ],
  "most_rejected": [
    { "pattern_id": "ld-cap-high", "rejections": 8 }
  ]
}
```

## Acceptance criteria

- A1: `GET /api/analytics/accuracy` returns 200 for an `admin`/`owner` and 403
  for a non-admin viewer.
- A2: Summary counts match the org's findings review states.
- A3: Per-pattern precision is consistent with the summary formula.
- A4: The dashboard degrades to zeros when no findings exist.
- A5: `GET /risk-summary` matches the workspace's findings by severity/category.
- A6: `GET /deadline-dashboard` buckets opportunities by submission due date.
- A7: `GET /boq-defect-summary` groups only findings with `producer='boq'`.
- A8: `POST /reports/export` returns a downloadable file and rejects unsupported
  formats with `400`.
- A9 (TS-242): `GET /baseline-adoption` returns sealed-opportunity count and weekly
  active baseline users; `403` for non-admin; degrades to zeros when `baseline` is
  disabled.

## Out of scope

- Golden-label import and true recall computation (requires labelled evaluation
  set, P3).
- Real-time streaming; the dashboard is computed on request.
- Cross-org analytics (P3).
