# Internal Accuracy Dashboard — Spec

**Status:** implemented (TS-057)  
**Requirement refs:** Phase 1.5 doc §10  
**Task ref:** TS-057

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
- **Events:** none.
- **API routes** (prefix `/api/analytics`):
  - `GET /accuracy` — admin-only accuracy dashboard.

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

## Out of scope

- Golden-label import and true recall computation (requires labelled evaluation
  set, P3).
- Real-time streaming; the dashboard is computed on request.
- Cross-org analytics (P3).
