# BOQ Engine — Spec

**Status:** implemented — engine core + scope gaps + write-through (BoqRunner parses an uploaded workbook, runs checks, persists defects via findings.store, producer='boq')
**Requirement refs:** Doc §6.4, §2.1
**Task refs:** TS-018, TS-019

## Purpose

Deterministic, bit-reproducible BOQ assurance — **zero LLM**. Normalize uploaded
BOQs into canonical items, run arithmetic/consistency checks, and cross-reference
trade checklists for scope gaps.

## Public interface

- **Capabilities published:** `boq.items` (query normalized items), `boq.run`.
- **Capabilities consumed (soft):** `rulepacks.loader` (unit canon map, check
  thresholds, trade checklists), `ingestion.doc_text` (spec text index for
  scope-gap triggers), `integrations.service_factory` (schedule activities for
  cross-check, TS-318), `outcomes.service_factory` (historical scope-gap patterns
  for missing-scope suggestions, TS-319).
- **Events emitted:** `finding.created` (kinds `boq_defect`, `scope_gap`),
  `boq.run_completed`.
- **Events consumed:** `document.classified` (kind=`boq` → start normalization).
- **API routes:** `/api/opportunities/{id}/boq/items`, `/defects`, `/scope-gaps`.

## Data owned

`boq_items` (with `src_sheet`/`src_row` provenance and per-row `checks` JSONB);
`findings` rows with `kind='boq_defect' | 'scope_gap'`.

## Behavior

- **B1 (deterministic only):** Pandas + DuckDB; arithmetic findings are never
  AI opinions. Same input → identical output, always. DuckDB queries run against an
  explicitly registered DataFrame in a fresh in-memory connection, not the caller's
  Python scope.
- **B2 (normalization):** unit canon via pack map; `amount_calc = round(qty×rate, 2)`.
- **B3 (checks):** arithmetic error (|amount−calc| > tolerance), blank/zero rate,
  duplicate (description+unit), quantity outlier (z/quantile threshold from pack),
  grand-total/carry-forward mismatch.
- **B4 (scope gaps):** checklist item fires when a spec trigger matches AND no
  BOQ line matches the item's patterns; finding carries the trigger's page.
- **B5 (money order):** defects sort by rupee impact, not row order (Doc §9).
- **B6 (provenance):** every defect points to `src_sheet`/`src_row`.
- **B7 (upload guard):** BOQ upload enforces a 10 MB size cap and the same MIME/
  extension validation as ingestion documents. The `RunBody.csv` field is capped at
  10,000,000 characters.
- **B8 (drawing schedule cross-check, TS-318):** when `integrations.service_factory`
  is available and the opportunity has imported schedule activities, the BOQ run
  compares BOQ descriptions to activity names using conservative token overlap.
  Unmatched schedule activities raise `SCOPE_GAP` findings; unmatched BOQ items raise
  `BOQ_DEFECT` findings.
- **B9 (historical scope suggestions, TS-319):** when `outcomes.service_factory` is
  available, the BOQ run fetches historical `scope_gap` categories from prior
  opportunities in the workspace and raises `SCOPE_GAP` suggestions for any that
  are not already present in the current BOQ.

## Acceptance criteria

- A1: fixture workbook with a rate×qty mismatch yields exactly that arith defect.
- A2: `Cum`, `cum`, `M³`, `CuM` normalize to `m3`.
- A3: dewatering scope-gap fires on a basement-excavation spec fixture with no
  dewatering BOQ line.
- A4: grand-total carry-forward error detected on fixture.
- A5: running twice yields byte-identical findings (determinism).
- A6: oversized BOQ upload returns 413.
- A7: `POST .../run` rejects a CSV payload > 10,000,000 characters.
- A8 (TS-318): A schedule activity with no matching BOQ line raises a `SCOPE_GAP`; a BOQ item with no matching schedule activity raises a `BOQ_DEFECT`.
- A9 (TS-319): A historical `scope_gap` category missing from the current BOQ raises a `SCOPE_GAP` `Consider: ...` suggestion.

## Out of scope

Scanned-BOQ OCR hardening (P2); >3 trade checklists (P2); rate benchmarking (never in v1).
