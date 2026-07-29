# TS-054 — Risk Explainability: structured `explanation` object on every finding

**Status:** done
**Requirement:** Phase 1.5 doc §5
**Spec(s) updated:** `specs/modules/risk.md`
**Module(s):** `risk`, frontend
**Severity / Gate:** P0 · Phase 1.5

## What this builds

Every risk finding gets a structured `explanation` object — not just a
severity label — so a reviewer sees *why* something was flagged without
opening the rule-pack YAML themselves.

## Implementation

```python
# backend/app/modules/risk/engine.py
def _build_explanation(pattern, quote: str | None, *, absence: bool = False) -> dict:
    """{ pattern_id, category, evidence (the verified quote or 'absent'),
    industry_reason (from the rule-pack's industry_reason field),
    suggested_clarification } — all sourced from the pattern's own YAML
    fields (TS-008), never generated fresh by an LLM."""
```

Called from both the quote-based path (`quote[:200] if verified else
quote`) and the absence-detection path (`_absence_finding`), so absence
findings get the same explanation depth as quote-based ones.

## Files touched

- `backend/app/modules/risk/engine.py`
- frontend finding-card component (explanation display)

## Tests

- `backend/tests/modules/risk/test_engine.py::test_explanation_shape`

## Acceptance criteria

- [x] Every finding (quote-based or absence) carries a non-empty
      `explanation` object.
- [x] `industry_reason`/`suggested_clarification` come from the rule-pack
      pattern data, not freshly generated LLM text.

## Commit

Predates commit-granular history (PR #10 bulk import).
