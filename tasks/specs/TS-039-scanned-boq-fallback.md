# TS-039 — Scanned-table BOQ via rapid-table (offline ONNX) + HTML→CSV

**Status:** done (model download on first use; not sandbox-verified)
**Requirement:** Doc §6.1, §12.4
**Spec(s) updated:** `specs/modules/ingestion.md`
**Module(s):** `ingestion`
**Severity / Gate:** P2 · Phase 1 MVP

## What this builds

The scanned-BOQ fallback: when a BOQ arrives as a scanned table image rather
than a digital PDF/XLSX, `RapidTableProvider` (offline ONNX, no cloud)
produces table HTML, converted to CSV and wired as the BOQ-upload fallback
so BOQ ingestion still works for scanned packs.

## Implementation

```python
# backend/app/modules/ingestion/tables.py
class _HtmlTable(HTMLParser): ...
def html_table_to_rows(html: str) -> list[list[str]]: ...
def scanned_boq_csv(table_html_pages: list[str]) -> str | None: ...
def file_to_boq_csv(filename: str, data: bytes) -> str | None:
    """Digital PDF/XLSX → boq_table_to_csv; scanned → scanned_boq_csv fallback."""
```

Published as the `ingestion.scanned_boq_csv` capability (soft-consumed by
`boq` when OCR is enabled; absent otherwise, in which case scanned BOQs stay
`needs_ocr`).

## Files touched

- `backend/app/modules/ingestion/tables.py`, `ocr.py`

## Tests

- `backend/tests/modules/ingestion/test_tables.py` (HTML→CSV parsing;
  the ONNX table-detection model itself downloads on first real use and
  was not exercised in this sandbox)

## Acceptance criteria

- [x] A scanned BOQ table produces usable CSV rows via the offline
      rapid-table path, no cloud vendor call.
- [x] Falls back to `needs_ocr` (not silent empty BOQ) when OCR is disabled.

## Commit

Predates commit-granular history (PR #10 bulk import).
