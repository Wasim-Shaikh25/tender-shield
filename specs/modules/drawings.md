# `drawings` — Drawing Register, Title-Block Extraction & Comparison — Spec

**Status:** implemented (TS-321, TS-322)  
**Requirement refs:** `docs/TenderShield_AI_Architecture_and_Market_Research.pdf` §4.D; `FEATURE_COVERAGE.md` §D  
**Task refs:** TS-321, TS-322

## Purpose

Maintain a drawing register for each opportunity, extract title-block metadata from
uploaded drawing PDFs/images, and compare revisions to detect page- and region-level
changes.

## Public interface

**Capabilities published**
- `drawings.service_factory` — create/list/retrieve drawings, supersede, compare.

**Capabilities consumed (soft)**
- `ingestion.ocr` — for image-based drawing text extraction when available.

**API routes** (prefix `/api/drawings`)
- `GET /opportunities/{id}/drawings` — list register.
- `GET /opportunities/{id}/drawings/{drawing_id}` — get one drawing.
- `POST /opportunities/{id}/drawings` — create a drawing record (manual or with metadata).
- `POST /opportunities/{id}/drawings/{drawing_id}/upload` — upload the drawing file to
  extract text and title-block fields.
- `POST /opportunities/{id}/drawings/{current_id}/supersedes/{previous_id}` — mark a
  drawing as superseding a previous revision.
- `POST /opportunities/{id}/drawings/{current_id}/compare/{previous_id}` — run
  page-level and region-level text comparison between two revisions.
- `POST /opportunities/{id}/drawings/{drawing_id}/symbol-assist` — text-based symbol
  count suggestions (TS-323).
- `POST /opportunities/{id}/drawings/{drawing_id}/link-boq` — persist a drawing-to-BOQ
  link (TS-324).
- `GET /opportunities/{id}/drawings/{drawing_id}/heatmap` — extraction confidence
  heatmap per page/region (TS-325).
- `POST /opportunities/{id}/drawings/{drawing_id}/ifc-quantities` — extract IFC
  element quantities and classifications as candidate BOQ lines / activities
  (TS-326).

## Data owned

- `drawings` — title block, extracted text, revision, supersedes link, status, page count,
  symbol suggestions, heatmap.
- `drawing_comparisons` — changed pages, changed regions, summary.
- `drawing_boq_links` — linked BOQ item details, source quote, drawing region/page.

## Behavior

### Title-block extraction (TS-321)

Text is extracted from PDFs with `pdfplumber` or from images via the optional
`ingestion.ocr` provider. The first 4000 characters are scanned with conservative
regex for `drawing_number`, `title`, `revision`, `revision_date`, and `discipline`.
Fields already supplied by the caller are not overwritten by extraction.

### Revision and superseded controls (TS-321)

A drawing can explicitly supersede another drawing. The superseded drawing is
marked `status: superseded`; the new drawing keeps `status: current` and stores
`supersedes_id`. The register is ordered by drawing number and revision.

### Overlay and region-level change detection (TS-322)

Comparison splits each drawing's extracted text into pages (using `[pN]` markers or
page breaks), then runs per-page text diffs. Changed pages are listed; within each
page the text is divided into `header`, `body`, and `footer` regions, and line-level
additions/removals are counted per region. No pixel-level CAD overlay is performed;
region-level change detection is text-based, which is sufficient for the title-block
and annotation changes tracked in this phase.

## Acceptance criteria

- A1: `POST /upload` extracts text and title-block fields from a PDF drawing.
- A2: Manual metadata (drawing number, revision, etc.) is preserved on upload.
- A3: `POST /.../supersedes/...` links revisions and flips statuses.
- A4: `POST /.../compare/...` returns changed page numbers and per-region line counts.
- A5: List endpoint is ordered by drawing number and revision.
- A6: `POST /.../symbol-assist` returns per-page symbol count suggestions with `confidence: low`.
- A7: `POST /.../link-boq` persists a drawing-to-BOQ link with item details and source quote.
- A8: `GET /.../heatmap` returns per-page/per-region confidence with `cannot_determine` states.
- A9: `POST /.../ifc-quantities` returns candidate BOQ lines and activities without
  creating real project lines.
- A10: All endpoints are workspace-scoped.

### 4. Symbol and count assistance (TS-323)

A lightweight, text-based symbol assist pass scans each drawing page's extracted text
for common construction symbols (electrical, plumbing, civil labels such as `WD`, `WS`,
`Fan`, `Light`, `Switch`, `MCB`, `RCC`, `PCC`, etc.). Detected tokens are counted per
page and returned as suggestions with a `low` confidence and a `verify_manually`
flag. No pixel-level symbol recognition is performed in this phase.

### 5. Drawing-to-BOQ link (TS-324)

A user can create a persisted link between a drawing region/page and a BOQ line. The
link stores the drawing region/page reference, a manually entered BOQ item code,
description, unit, quantity, and rate, plus the original source quote. The link is
workspace/opportunity scoped and surfaced in the drawing register.

### 6. Confidence heatmap (TS-325)

The heatmap is generated from text-extraction quality signals rather than pixel
overlays: each page and coarse region receives a confidence score based on the
presence of extracted text, title-block fields, and symbol-assist coverage. The API
returns a JSON/SVG overlay with per-region confidence and `cannot_determine` states
for pages with no extractable text.

### 7. IFC / model quantity import (TS-326)

`POST /opportunities/{id}/drawings/{drawing_id}/ifc-quantities` accepts an IFC-SPF
file and extracts candidate element quantities and classifications from
`IFCPROPERTYSET`, `IFCELEMENTQUANTITY`, `IFCBUILDINGELEMENT` and related entities.
Results are returned as candidate BOQ lines (`description`, `unit`, `quantity`,
`classification`) and candidate schedule activities (`name`, `start`, `finish`,
`duration`). No entitlement is auto-generated.

## Out of scope

- Pixel/CAD layer overlay and geometric change detection.
- True computer-vision symbol detection from raster images.
- Bidirectional automatic quantity take-off from drawings.
- Live CDE/ERP connector sync (TS-333).
