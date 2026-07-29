# TS-059 — Spec: `export` module

**Status:** done
**Requirement:** spec audit; Doc §1.1(8), §6.5
**Spec(s) updated:** `specs/modules/export.md`
**Module(s):** `export`
**Severity / Gate:** P1 · Spec audit

## What this builds

A spec-audit finding: `export`'s renderer (TS-023/030's DOCX/XLSX/PDF Bid
Review Pack, review gate, watermark stamp) had no dedicated module spec.

## Implementation

`specs/modules/export.md` written against the real implementation:
`render.render_{docx,xlsx,pdf}`, `stamp_line`/`_stamp_pdf_page`,
`ExportService`'s call to `review.gate()` before rendering (documented in
TS-021/023/030).

## Files touched

- `specs/modules/export.md` (new)

## Tests

None — documentation task.

## Acceptance criteria

- [x] `specs/modules/export.md` documents all three export formats and the
      review-gate/stamp behavior matching the real code.

## Commit

Predates commit-granular history (PR #10 bulk import).
