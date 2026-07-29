# TS-051 — Clause Change Detection: diff between document versions

**Status:** done
**Requirement:** Phase 1.5 doc §5
**Spec(s) updated:** `specs/modules/crossref.md`
**Module(s):** `crossref`
**Severity / Gate:** P2 · Phase 1.5

## What this builds

Diffs clauses between two versions of the same document (e.g. a tender
addendum against the original NIT) to surface added/removed/changed clauses
— catching amendments a manual re-read might miss.

## Implementation

Built on `ingestion.segment_clauses` (TS-016) output for both document
versions: matches clauses by `ref` where present, falls back to fuzzy text
match otherwise, and classifies each pairing as added/removed/changed
(text-diff) — string comparison, not LLM judgment.

## Files touched

- `backend/app/modules/crossref/{service,router,module}.py`

## Tests

- `backend/tests/modules/crossref/test_service.py::test_clause_diff`

## Acceptance criteria

- [x] A clause present in only one version is reported as added/removed.
- [x] A clause present in both but with changed text is reported as
      changed, with both versions' text shown.

## Commit

Predates commit-granular history (PR #10 bulk import).
