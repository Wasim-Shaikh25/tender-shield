# TS-030 — PDF export (reportlab) — completes the DOCX/PDF/XLSX trio

**Status:** done
**Requirement:** Doc §1.1(8)
**Spec(s) updated:** `specs/modules/export.md`
**Module(s):** `export`
**Severity / Gate:** P1 · Phase 1 MVP

## What this builds

The third export format for the Bid Review Pack (TS-023 shipped DOCX/XLSX;
this adds PDF), gated and stamped identically to the other two formats — no
format-specific bypass of the review-approval requirement.

## Implementation

```python
# backend/app/modules/export/render.py
def render_pdf(...) -> bytes: ...
def _stamp_pdf_page(canvas, doc) -> None:
    """Same review-approval stamp as DOCX/XLSX (stamp_line), rendered on
    every page via reportlab's canvas callback — not just the first page."""
```

## Files touched

- `backend/app/modules/export/render.py`, `service.py`, `router.py`

## Tests

- `backend/tests/modules/export/test_render.py::test_render_pdf`

## Acceptance criteria

- [x] PDF export carries the same review-approval stamp on every page.
- [x] PDF export is blocked by the same `review.gate()` check as DOCX/XLSX.

## Commit

Predates commit-granular history (PR #10 bulk import).
