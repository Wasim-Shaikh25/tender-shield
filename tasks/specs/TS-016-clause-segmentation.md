# TS-016 — Clause segmentation → `clauses` rows with refs + defined terms

**Status:** done
**Requirement:** Doc §3.3
**Spec(s) updated:** `specs/modules/ingestion.md`
**Module(s):** `ingestion`
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

Splits a document's extracted text into addressable clause records — the
unit every downstream module (risk, BOQ scope-gap, assistant Q&A) cites
against for provenance (CLAUDE.md §4: every extracted fact carries
`source_page`/`source_quote`).

## Implementation

```python
# backend/app/modules/ingestion/segment.py
@dataclass
class ClauseSeg:
    ref: str | None       # clause/section number, when present
    text: str
    page: int

def _finalize(seg: ClauseSeg) -> ClauseSeg: ...
def segment_clauses(text: str) -> list[ClauseSeg]:
    """Splits on numbered-clause/heading patterns; falls back to paragraph
    breaks when no clause numbering is detected."""
```

## Files touched

- `backend/app/modules/ingestion/segment.py`, `models.py` (`Clause` table)

## Tests

- `backend/tests/modules/ingestion/test_segment.py`

## Acceptance criteria

- [x] Every clause record carries its source page and (when present) a
      clause reference number.
- [x] Segmentation degrades gracefully (paragraph fallback) on documents
      without numbered clauses.

## Commit

Predates commit-granular history (PR #10 bulk import).
