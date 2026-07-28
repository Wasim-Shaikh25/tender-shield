# Export (Bid Review Pack) — Spec

**Status:** implemented
**Requirement refs:** Doc §1.1(8), §6.5, §11.4
**Task refs:** TS-023, TS-030, TS-045, TS-088

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
  - `billing.export_entitlement` (TS-088) — decides the free-tier watermark
    server-side; absent → no watermark (matches spec core B2, degrades
    gracefully when billing is disabled).
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
- **B4 — Watermark (TS-088):** `ExportService._watermark` asks
  `billing.export_entitlement` whether the workspace is on the free plan and
  sets `meta["watermark"]` accordingly — never from client input (a `?format=`
  query string or any other caller-supplied value cannot turn it off). Applied
  per format, not just the stamp line: XLSX gets a tinted title cell plus the
  mark repeated in the printed header/footer (`ws.oddHeader`/`oddFooter`, so it
  survives a copy-paste into a new sheet); DOCX gets it in the page header
  (every page); PDF gets a diagonal grey page stamp via a reportlab `onPage`
  callback (every page). The watermark marks the *document*, never the
  content — findings, quotes, page citations and severities are identical
  between a free and a paid export of the same opportunity.
- **B5 — No numbers from the LLM:** All pack content comes from accepted
  findings and generated artifacts that have already passed the validators.

## Acceptance criteria

- A1: Export before review completion returns 403 with code `review_incomplete`.
- A2: Export in `xlsx` returns a valid `.xlsx` byte stream with the opportunity
  title and the findings register.
- A3: Export in `pdf` returns a valid PDF byte stream including accepted findings
  and artifact sections.
- A4: a free-plan workspace's `xlsx` export carries the watermark text in its
  printed header/footer; a paid-plan workspace's export of the same
  opportunity does not.
- A5: the findings content of a free-plan export and a paid-plan export of the
  same opportunity are identical — only the watermark differs.

## Out of scope

- UI preview of the pack (frontend P2).
- Cloud storage upload / signed download URLs (P2).
- Handover-pack export from baseline (TS-045) reuses this renderer but is
  triggered from the `baseline` module.
