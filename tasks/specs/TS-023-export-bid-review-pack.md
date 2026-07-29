# TS-023 — Export renderer: Bid Review Pack (DOCX/XLSX) with review-approval stamp

**Status:** done
**Requirement:** Doc §1.1(8), §11.4
**Spec(s) updated:** `specs/modules/export.md`
**Module(s):** `drafting` (renderer), `export`
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

The first exportable artifact — a Bid Review Pack combining findings +
generated drafts into DOCX/XLSX, stamped with the review approval that
unlocked it (TS-021's `gate()`), so an exported file always carries proof it
passed review. PDF was still pending at this task (added by TS-030).

## Implementation

```python
# backend/app/modules/export/render.py
def stamp_line(meta: dict) -> str:
    """Renders the review-approval stamp (reviewer, timestamp, opportunity)
    embedded in every exported file — proof of the review gate, not just a
    watermark."""

def render_xlsx(opportunity_title: str, findings: list[dict], meta: dict) -> bytes: ...
def _add_docx_watermark_header(doc: Document) -> None: ...
def render_docx(...) -> bytes: ...
```

```python
# backend/app/modules/export/service.py
class ExportError(Exception): ...
class ExportService:
    """Calls review.gate() before rendering; raises ExportError (not a
    silent partial export) when the gate isn't satisfied."""
```

## Files touched

- `backend/app/modules/export/{render,service,router,module}.py`

## Tests

- `backend/tests/modules/export/test_render.py`

## Acceptance criteria

- [x] DOCX and XLSX exports both carry the review-approval stamp.
- [x] Export raises `ExportError` (not a partial/unstamped file) when the
      review gate isn't satisfied.

## Commit

Predates commit-granular history (PR #10 bulk import).
