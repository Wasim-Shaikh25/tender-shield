# TS-019 — Scope-gap engine: trade checklist × spec/BOQ cross-reference

**Status:** done
**Requirement:** Doc §6.4
**Spec(s) updated:** `specs/modules/boq.md`
**Module(s):** `boq`
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

Cross-references the trade checklists (TS-009) against the spec text and
BOQ line items: when a checklist item's `triggers` phrase appears in the
spec but none of its `boq_patterns` appear as a BOQ line, that's a scope-gap
finding — an item the contractor would otherwise price for free.

## Implementation

```python
# backend/app/modules/boq/engine.py
class SpecTextIndex:
    """Indexed spec text for trigger-phrase lookup."""

def scope_gaps(df: pd.DataFrame, spec: SpecTextIndex, checklist) -> list[Finding]:
    """For each checklist item: if any trigger phrase is present in the spec
    and none of its boq_patterns match a BOQ line item description, emit a
    scope-gap finding at the checklist item's severity."""
```

Deterministic string/pattern matching — the judgment is in the rule-pack
data (trigger/pattern lists), not in an LLM call.

## Files touched

- `backend/app/modules/boq/engine.py`, `service.py`

## Tests

- `backend/tests/modules/boq/test_engine.py::test_scope_gaps`

## Acceptance criteria

- [x] A checklist item whose trigger is present in the spec but whose
      pattern is absent from the BOQ produces a scope-gap finding.
- [x] A checklist item with no matching trigger produces no finding
      (no false positives from irrelevant trades).

## Commit

Predates commit-granular history (PR #10 bulk import).
