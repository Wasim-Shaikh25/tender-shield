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
  scope-gap triggers).
- **Events emitted:** `finding.created` (kinds `boq_defect`, `scope_gap`),
  `boq.run_completed`.
- **Events consumed:** `document.classified` (kind=`boq` → start normalization).
- **API routes:** `/api/opportunities/{id}/boq/items`, `/defects`, `/scope-gaps`.

## Data owned

`boq_items` (with `src_sheet`/`src_row` provenance and per-row `checks` JSONB);
`findings` rows with `kind='boq_defect' | 'scope_gap'`.

## Behavior

- **B1 (deterministic only):** Pandas + DuckDB; arithmetic findings are never
  AI opinions. Same input → identical output, always.
- **B2 (normalization):** unit canon via pack map; `amount_calc = round(qty×rate, 2)`.
- **B3 (checks):** arithmetic error (|amount−calc| > tolerance), blank/zero rate,
  duplicate (description+unit), quantity outlier (z/quantile threshold from pack),
  grand-total/carry-forward mismatch.
- **B4 (scope gaps):** checklist item fires when a spec trigger matches AND no
  BOQ line matches the item's patterns; finding carries the trigger's page.
- **B5 (money order):** defects sort by rupee impact, not row order (Doc §9).
- **B6 (provenance):** every defect points to `src_sheet`/`src_row`.
- **B7 (upload guard):** BOQ upload enforces a 100 MB size cap and the same MIME/
  extension validation as ingestion documents.

## Acceptance criteria

- A1: fixture workbook with a rate×qty mismatch yields exactly that arith defect.
- A2: `Cum`, `cum`, `M³`, `CuM` normalize to `m3`.
- A3: dewatering scope-gap fires on a basement-excavation spec fixture with no
  dewatering BOQ line.
- A4: grand-total carry-forward error detected on fixture.
- A5: running twice yields byte-identical findings (determinism).
- A6: oversized BOQ upload returns 413.

## Out of scope

Scanned-BOQ OCR hardening (P2); >3 trade checklists (P2); rate benchmarking (never in v1).
