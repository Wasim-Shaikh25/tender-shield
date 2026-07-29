# TS-020 — `drafting` module: clarification letter + assumptions register + 3 validators

**Status:** done
**Requirement:** Doc §6.5
**Spec(s) updated:** `specs/modules/drafting.md`
**Module(s):** `drafting`
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

The first generated artifacts (clarification letter, assumptions register)
plus the three validators every generated artifact must pass before display
— the spine CLAUDE.md §4 calls out: "no invented quotes, no uncited
clauses, no invented numbers in generated artifacts."

## Implementation

```python
# backend/app/modules/drafting/generator.py
def build_body(kind: str, opportunity_title: str, findings: list[dict], weights=None) -> dict: ...
def _clarification(title: str, findings: list[dict]) -> dict: ...
def _assumptions(title: str, findings: list[dict]) -> dict: ...
def render_text(body: dict) -> str: ...
```

```python
# backend/app/modules/drafting/validators.py
class DraftError(Exception): ...

class FactTable:
    """Every citable quote/number/clause the generated prose is allowed to
    reference — built strictly from confirmed findings, never from the
    LLM's own output."""

def validate(prose: str, facts: FactTable) -> str:
    """Three checks: (1) every quoted string appears verbatim in FactTable,
    (2) every clause reference resolves to a real clause, (3) every number
    in prose matches a FactTable value — raises DraftError on any mismatch."""
```

## Files touched

- `backend/app/modules/drafting/{generator,validators,service,router,models}.py`

## Tests

- `backend/tests/modules/drafting/test_validators.py`, `test_generator.py`

## Acceptance criteria

- [x] A clarification letter/assumptions register is generated per
      opportunity from confirmed findings.
- [x] `validate()` rejects prose containing an invented quote, an unresolved
      clause reference, or a number not present in the fact table.

## Commit

Predates commit-granular history (PR #10 bulk import).
