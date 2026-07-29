# TS-014 — `ingestion` module: upload → rules-first classification + missing-doc checklist

**Status:** done
**Requirement:** Doc §6.1, §3.3
**Spec(s) updated:** `specs/modules/ingestion.md`
**Module(s):** `ingestion`
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

The opportunity aggregate plus the first pipeline step: classify each
uploaded document by anchor-phrase matching (deterministic, not an LLM call)
and report which of the tender pack's expected document kinds are missing.

## Implementation

```python
# backend/app/modules/ingestion/classify.py
def classify_text(text: str, doc_type_anchors: Mapping[str, Iterable[str]]) -> str | None:
    """Anchor-phrase match against each doc type's known phrases — rules-first,
    deterministic; no LLM in the classification path."""

def missing_documents(present_kinds: Iterable[str], expected_kinds: Iterable[str]) -> list[str]:
    return [k for k in expected_kinds if k not in present_kinds]
```

`doc_type_anchors` comes from the rule-pack's `doc_types.yaml` (TS-007), kept
as consumed data rather than hardcoded so anchors can be tuned per
jurisdiction without a code change.

## Files touched

- `backend/app/modules/ingestion/{classify,models,router,service,module}.py`

## Tests

- `backend/tests/modules/ingestion/test_classify.py`

## Acceptance criteria

- [x] A document's type is determined by anchor-phrase match, not LLM
      judgment.
- [x] Missing expected document kinds are reported per opportunity.

## Commit

Predates commit-granular history (PR #10 bulk import).
