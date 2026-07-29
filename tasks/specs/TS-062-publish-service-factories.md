# TS-062 — Publish `analytics.service_factory` and `comparison.service_factory`

**Status:** done
**Requirement:** spec audit
**Spec(s) updated:** `specs/modules/analytics.md`, `specs/modules/comparison.md`
**Module(s):** `analytics`, `comparison`
**Severity / Gate:** P0 · Spec audit

## What this builds

A spec-audit finding: `analytics` and `comparison` built their service
objects internally but never published a `service_factory` capability, so
no other module (or future test) could resolve them via the registry per
CLAUDE.md §2's cross-module contract.

## Implementation

```python
# backend/app/modules/analytics/module.py
reg.provide(
    "analytics.service_factory",
    lambda session: AnalyticsService(
        session,
        ingestion_factory=reg.get("ingestion.service_factory"),
    ),
)
```

```python
# backend/app/modules/comparison/module.py
reg.provide(
    "comparison.service_factory",
    lambda session: ComparisonService(
        session,
        ingestion_factory=reg.get("ingestion.service_factory"),
        drafting_factory=reg.get("drafting.service_factory"),
    ),
)
```

Both factories resolve their own soft dependencies (`ingestion`/`drafting`)
via `reg.get()` at call time, not at module-import time — absence degrades
gracefully rather than crashing `setup()`.

## Files touched

- `backend/app/modules/analytics/module.py`, `comparison/module.py`

## Tests

- `backend/tests/test_architecture.py` (registry capability presence)

## Acceptance criteria

- [x] `registry.get("analytics.service_factory")` and
      `registry.get("comparison.service_factory")` both resolve when their
      modules are enabled.

## Commit

Predates commit-granular history (PR #10 bulk import).
