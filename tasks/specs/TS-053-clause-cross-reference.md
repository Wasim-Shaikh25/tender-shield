# TS-053 — Clause Cross-Reference: cross-document citation search

**Status:** done
**Requirement:** Phase 1.5 doc §5
**Spec(s) updated:** `specs/modules/crossref.md`
**Module(s):** `crossref`
**Severity / Gate:** P2 · Phase 1.5

## What this builds

Search for every clause across all of an opportunity's documents (GCC, SCC,
addenda, spec) that touches a given topic — e.g. "find every mention of
liquidated damages," surfacing GCC/SCC conflicts where SCC silently amends
a GCC clause.

## Implementation

```python
# backend/app/modules/crossref/service.py
class CrossRefService:
    """Anchor-phrase search (same style as risk's retrieve_candidates,
    TS-017) across every clause of every document in the opportunity,
    grouped by document so a GCC-vs-SCC conflict is visible side by side."""
```

## Files touched

- `backend/app/modules/crossref/{service,router,module}.py`

## Tests

- `backend/tests/modules/crossref/test_service.py::test_cross_document_search`

## Acceptance criteria

- [x] A search term returns matching clauses from every document in the
      opportunity, not just one.
- [x] Results are grouped by source document so conflicting clauses across
      documents are visible together.

## Commit

Predates commit-granular history (PR #10 bulk import).
