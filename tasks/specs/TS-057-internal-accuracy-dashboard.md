# TS-057 — Internal Accuracy Dashboard

**Status:** done
**Requirement:** Phase 1.5 doc §5
**Spec(s) updated:** `specs/modules/analytics.md`
**Module(s):** `analytics`
**Severity / Gate:** P3 · Phase 1.5

## What this builds

An admin-only dashboard turning TS-055's structured review outcomes into
precision/recall-style telemetry per risk pattern — `false_positive`
outcomes count against a pattern's precision, giving a data-driven signal
for which `confidence: unvalidated` patterns (TS-008) need rule-pack tuning.

## Implementation

```python
# backend/app/modules/analytics/service.py
class AnalyticsService:
    """Aggregates review.AuditLog rows (TS-021) grouped by finding pattern_id
    and review decision (TS-055's DECISIONS) into per-pattern counts:
    accepted, false_positive, needs_clarification, edited, rejected."""
```

Gated to `is_superadmin`/workspace-admin only — this is an internal
product-quality tool, not a customer-facing feature.

## Files touched

- `backend/app/modules/analytics/{service,models,router,module}.py`

## Tests

- `backend/tests/modules/analytics/test_service.py`

## Acceptance criteria

- [x] Each risk pattern's false-positive rate is computable from real
      review-outcome data, not simulated.
- [x] The dashboard is not reachable by a non-admin caller.

## Commit

Predates commit-granular history (PR #10 bulk import).
