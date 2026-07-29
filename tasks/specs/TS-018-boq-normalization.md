# TS-018 — `boq` module: normalization (unit canon map) + deterministic checks

**Status:** done
**Requirement:** Doc §6.4
**Spec(s) updated:** `specs/modules/boq.md`
**Module(s):** `boq`
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

BOQ arithmetic and unit normalization as pure deterministic code — zero LLM
in the numeric path, per CLAUDE.md §4 ("Numbers never come from the LLM").

## Implementation

```python
# backend/app/modules/boq/engine.py
def normalize(df: pd.DataFrame, unit_canon: dict[str, str]) -> pd.DataFrame:
    """Maps raw unit strings (e.g. "sq.m", "SQM", "Sq. Mtr") to a canonical
    unit via the rule-pack's unit_canon map — pure pandas, no LLM call."""

def _defect(category: str, severity: Severity, title: str, detail: str, row) -> Finding: ...

def run_checks(df: pd.DataFrame, ...) -> list[Finding]:
    """Deterministic defect checks: qty/rate/amount arithmetic mismatches,
    missing units, duplicate item codes — all computed, never LLM-judged."""
```

```python
# backend/app/modules/boq/service.py
class BoqEngine: ...
class BoqRunner: ...
```

## Files touched

- `backend/app/modules/boq/{engine,service,router,module}.py`

## Tests

- `backend/tests/modules/boq/test_engine.py`

## Acceptance criteria

- [x] Unit normalization uses the rule-pack's canon map, not free-text LLM
      guessing.
- [x] Every arithmetic-defect finding (qty × rate ≠ amount, etc.) is computed
      by code.

## Commit

Predates commit-granular history (PR #10 bulk import).
