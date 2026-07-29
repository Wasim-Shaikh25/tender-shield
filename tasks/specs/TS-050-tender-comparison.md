# TS-050 — Tender Comparison: portfolio dashboard

**Status:** done
**Requirement:** Phase 1.5 doc §5
**Spec(s) updated:** `specs/modules/comparison.md`
**Module(s):** `comparison`
**Severity / Gate:** P2 · Phase 1.5

## What this builds

A portfolio-level view ranking all of a workspace's open opportunities by
risk exposure, BOQ quality, deadline pressure, and bid readiness — so a
reviewer triages across many tenders, not just within one.

## Implementation

```python
# backend/app/modules/comparison/service.py
class ComparisonService: ...

def _priority_score(row: dict) -> float:
    """Deterministic composite of risk severity mix, BOQ defect count,
    days-to-deadline, and bid readiness score (TS-048) — reuses each
    module's own computed values rather than re-deriving them."""

def _rank(rows: list[dict]) -> list[dict]: ...
```

## Files touched

- `backend/app/modules/comparison/{service,router,module}.py`

## Tests

- `backend/tests/modules/comparison/test_service.py`

## Acceptance criteria

- [x] Every opportunity in the workspace appears in the ranked list.
- [x] Ranking is a deterministic function of each opportunity's existing
      risk/BOQ/deadline/readiness data, not separately re-computed.

## Commit

Predates commit-granular history (PR #10 bulk import).
