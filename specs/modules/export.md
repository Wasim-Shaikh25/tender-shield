# Export (Bid Review Pack) — Spec

**Status:** implemented
**Requirement refs:** Doc §1.1(8), §6.5, §11.4
**Task refs:** TS-023, TS-030, TS-045

## Purpose

Assemble the signed-off Bid Review Pack into a downloadable file the estimating
or commercial team can attach to a bid submission or hand to legal/QS. The
export is gated by the review workbench: nothing leaves the system until a
reviewer marks the opportunity as reviewed.

## Public interface

- **Capabilities published:**
  - `export.service_factory` → `ExportService(session, ...)` with `export(org_id,
    opportunity_id, format)` returning `(filename, media_type, bytes)`.
- **Capabilities consumed (soft):**
  - `review.service_factory` (gate check)
  - `findings.store_factory`
  - `drafting.service_factory`
  - `ingestion.service_factory`
  - `rulepacks.loader` (pack version for stamp)
- **Events emitted:** none.
- **Events consumed:** none.
- **API routes** (prefix `/api/export`):
  - `GET /opportunities/{opportunity_id}?format={xlsx|docx|pdf}` (estimator) —
    download the Bid Review Pack. Returns `403` if review is incomplete.

## Data owned

None. The module is a read-only assembler over review, findings, drafting,
ingestion, and rulepack capabilities.

## Behavior

- **B1 — Export gate:** `ExportService._gate_ok` calls `review.service_factory`
  and checks `export_allowed`. If the gate is false, `ExportError("review_incomplete")`
  is raised and the router returns HTTP 403.
- **B2 — Pack contents:** The pack includes the opportunity title, the review
  stamp (date, pack version, disclaimer), the full findings register, and the
  generated artifacts (clarification letter, assumptions register, bid/no-bid
  decision) from drafting.
- **B3 — Formats:** `xlsx` (risk register spreadsheet), `docx` (narrative report
  with artifacts), `pdf` (same narrative rendered with reportlab). Any other
  format returns `ExportError("bad_format")` (HTTP 400).
- **B4 — Watermark:** Free-tier exports include a "DRAFT — TenderShield"
  watermark / disclaimer. (Currently implemented in the stamp line for all
  exports; billing-driven tiered watermarking is a P2 refinement.)
- **B5 — No numbers from the LLM:** All pack content comes from accepted
  findings and generated artifacts that have already passed the validators.

## Acceptance criteria

- A1: Export before review completion returns 403 with code `review_incomplete`.
- A2: Export in `xlsx` returns a valid `.xlsx` byte stream with the opportunity
  title and the findings register.
- A3: Export in `pdf` returns a valid PDF byte stream including accepted findings
  and artifact sections.

## Out of scope

- UI preview of the pack (frontend P2).
- Cloud storage upload / signed download URLs (P2).
- Handover-pack export from baseline (TS-045) reuses this renderer but is
  triggered from the `baseline` module.
