# TS-044 — Award-document ingestion

**Status:** todo
**Requirement:** Doc §0.1 (P2/P3)
**Spec(s) updated:** `specs/modules/baseline.md` (to be updated when built)
**Module(s):** `baseline`
**Severity / Gate:** P2 · Phase 1 MVP

## What this builds

Parses the negotiated contract / award letter itself so `compare()`'s
award-vs-tender delta (TS-041) is seeded from real award text, not manually
entered values.

## Implementation (reference plan — not yet built)

- Reuse `ingestion.extract_text`/`classify_text` (TS-014/026) against the
  award document, tagged as a new doc type in `doc_types.yaml`.
- Extract the fields `compare()` currently expects the user to enter by hand
  (final contract value, revised dates, amended clauses) via the same
  clause-segmentation + pattern-match approach as `risk`/`boq`.

## Files touched (planned)

- `backend/app/modules/baseline/service.py`
- `rulepacks/in-works/doc_types.yaml` (new `award_letter` type)

## Tests (planned)

- `backend/tests/modules/baseline/test_award_ingestion.py`

## Acceptance criteria

- [ ] An uploaded award letter is classified and its key fields extracted
      with source-quote provenance, same as any other tender document.
- [ ] `compare()` can seed its delta from the parsed award document instead
      of requiring manual entry.

## Commit

Not yet implemented.
