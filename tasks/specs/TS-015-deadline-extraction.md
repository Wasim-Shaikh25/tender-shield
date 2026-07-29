# TS-015 — Deadline extraction (deterministic) + deadline wall + confirm chips

**Status:** done
**Requirement:** Doc §6.2
**Spec(s) updated:** `specs/modules/ingestion.md`
**Module(s):** `ingestion`
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

The "<3-minute deadline wall" promise: deterministic date-arithmetic
extraction of every deadline in a tender pack, each carrying its verbatim
source quote, plus a frontend confirm-chip flow so a reviewer accepts/edits
before it's treated as ground truth. Per CLAUDE.md §4, date arithmetic is
deterministic code — never the LLM.

## Implementation

```python
# backend/app/modules/ingestion/deadlines.py
@dataclass
class DeadlineExtraction:
    label: str
    date: datetime
    source_quote: str
    source_page: int

def parse_date(text: str) -> datetime | None: ...
def _classify(line: str) -> str | None: ...   # bid-submission / pre-bid-meeting / EMD / ...
def extract_deadlines(text: str) -> list[DeadlineExtraction]: ...
```

Every `DeadlineExtraction` carries `source_quote`/`source_page` (CLAUDE.md §4
provenance requirement) and passes quote verification before the frontend
deadline wall displays it as a confirm chip.

## Files touched

- `backend/app/modules/ingestion/deadlines.py`, `router.py`, `service.py`
- frontend deadline-wall + confirm-chip components (TS-025)

## Tests

- `backend/tests/modules/ingestion/test_deadlines.py`

## Acceptance criteria

- [x] Every extracted deadline carries a verbatim source quote + page.
- [x] Date math (e.g. relative deadlines) is computed by code, never the LLM.
- [x] A reviewer can confirm or edit an extracted deadline before it's final.

## Commit

Predates commit-granular history (PR #10 bulk import).
