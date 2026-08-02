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

## Data owned

- `drawings` — title block, extracted text, revision, supersedes link, status, page count.
- `drawing_comparisons` — changed pages, changed regions, summary.

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
- A6: All endpoints are workspace-scoped.

## Out of scope

- Pixel/CAD layer overlay and geometric change detection.
- Symbol recognition and automatic count assistance (TS-323).
- Drawing-to-BOQ link (TS-324).
- Confidence heatmap (TS-325).
