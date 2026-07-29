# TS-052 — Tender Timeline: milestone calendar

**Status:** done
**Requirement:** Phase 1.5 doc §5
**Spec(s) updated:** `specs/modules/timeline.md`
**Module(s):** `ingestion`, `timeline`
**Severity / Gate:** P0 · Phase 1.5

## What this builds

A milestone calendar view distinct from the raw deadline wall (TS-015):
pre-bid meeting, clarification deadline, submission, technical/financial bid
opening, EMD/BG validity window, contract signing — ordered chronologically
as one timeline per opportunity.

## Implementation

```python
# backend/app/modules/timeline/service.py
def _normalize(kind: str) -> str:
    """Maps ingestion's raw deadline-kind labels (TS-015's _classify) to the
    timeline's fixed milestone vocabulary."""

@dataclass
class TimelineEvent:
    kind: str
    date: datetime
    source_quote: str

class TimelineService:
    """Reads ingestion's extracted deadlines (soft-consumed capability) and
    projects them onto the milestone calendar — no separate extraction
    pass."""
```

## Files touched

- `backend/app/modules/timeline/{service,router,module}.py`

## Tests

- `backend/tests/modules/timeline/test_service.py`

## Acceptance criteria

- [x] Every milestone on the timeline traces back to a TS-015 deadline
      extraction with its source quote.
- [x] Milestones render in chronological order regardless of extraction
      order.

## Commit

Predates commit-granular history (PR #10 bulk import).
