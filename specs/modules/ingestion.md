# Ingestion — Spec

**Status:** implemented (Phase-1 core) — opportunities/documents + rules-first
classification + missing-doc checklist (TS-014), clause segmentation (TS-016),
and deterministic deadline extraction + deadline wall + confirm chips (TS-015).
Real multipart upload + text extraction (PDF via pypdf, XLSX via openpyxl, CSV) feeds the pipeline (TS-026); LocalStorage dev backend, S3 in prod. OCR (TS-038): pluggable OcrProvider — RapidOCR (offline, ONNX) reads scanned PDFs when TS_OCR_ENABLED, else docs are flagged needs_ocr (honest degradation, Doc §12.4); pdfplumber extracts BOQ tables from digital PDFs (no cloud). **tus resumable upload (TS-033)** and **Celery async page-streamed processing with SSE (TS-034)** are implemented. Relative-date formula resolution and LLM-assisted extraction for messy scans are follow-ups.
**Requirement refs:** Doc §3.3, §6.1, §6.2
**Task refs:** TS-014, TS-015, TS-016, TS-026, TS-033, TS-034

## Purpose

Owns the opportunity aggregate and the document path: resumable upload → classify
→ OCR → deadline extraction (the <3-minute promise) → clause segmentation.
Everything downstream (risk, BOQ, drafting) consumes its outputs.

## Public interface

- **Capabilities published:**
  - `ingestion.service_factory` → `IngestionService(session)` exposing opportunity
    CRUD, document registration, deadline/clause listing, and missing-doc reports.
  - `ingestion.ocr` → `OcrProvider` (RapidOCR when `TS_OCR_ENABLED`, else
    `NullOcrProvider` for honest degradation).
  - `ingestion.file_to_boq_csv` → pure helper converting PDF/XLSX tables to a
    CSV string for the BOQ module.
  - `ingestion.scanned_boq_csv` → scanned-table fallback (rapid-table) when OCR is
    enabled.
  - `ingestion.doc_text` → `DocTextService(session)` for page-level text retrieval
    (`text_for_document`, `text_for_page`).
- **Capabilities consumed (soft):** `rulepacks.loader` (doc types, expected-doc
  set, deadline calculators).
- **Events emitted:** `opportunity.created`, `document.classified`,
  `deadlines.extracted`, `clauses.segmented`.
- **API routes** (prefix `/api/ingestion`):
  - `GET /opportunities` (viewer)
  - `GET /opportunities/{id}` (viewer)
  - `POST /opportunities` (viewer)
  - `GET /opportunities/{id}/documents` (viewer)
  - `POST /opportunities/{id}/documents` (viewer) — register a classified document
  - `POST /opportunities/{id}/upload` (viewer) — multipart upload + text extraction
  - `GET /opportunities/{id}/deadlines` (viewer)
  - `POST /opportunities/{id}/deadlines/{deadline_id}/confirm` (viewer)
  - `GET /opportunities/{id}/clauses` (viewer)
  - `GET /opportunities/{id}/missing-docs` (viewer)
  - `GET /documents/{id}/text` (viewer) — page-level document text
    (`?page=N` returns a single page; no query returns all pages)
  - `POST /opportunities/{id}/upload?async=1` (estimator) — enqueue async extraction; returns `task_id`
  - `GET /opportunities/{id}/documents/{doc_id}/stream?task_id=...` (viewer) — SSE stream of async progress/done/error
  - `POST /tus` (estimator) — tus creation (`Upload-Length`, `Upload-Metadata` headers)
  - `PATCH /tus/{id}` (estimator) — tus chunk upload (`Upload-Offset` header)
  - `HEAD /tus/{id}` (estimator) — tus offset query

## Data owned

`opportunities`, `documents`, `clauses`, `deadlines`, `doc_chunks`.

`doc_chunks` stores page-level text chunks per document; rows are replaced when a
document is re-registered or re-uploaded.

## Behavior

- **B1 (classification rules-first):** anchor-regex classification (NIT/GCC/SCC/
  BOQ/addendum…) on first pages; LLM (Haiku-class) fallback only when rules miss
  (Doc §6.1). Excel BOQs skip OCR entirely.
- **B2 (missing-doc checklist):** compare classified set vs pack's expected set;
  flag absences (e.g. SCC referenced but absent) and addendum supersessions.
- **B3 (deadline extraction):** schema-constrained LLM extraction; every deadline
  MUST carry `source_page` + verbatim `source_quote`; **never infer unprinted
  dates**; relative formulas resolved by deterministic pack calculators only
  (Doc §6.2).
- **B4 (quote verification):** fuzzy ≥0.85 match on the cited page gates every
  extraction; failures render as low-confidence confirm chips, never silent facts.
- **B5 (streaming):** results stream to the UI as produced (Redis pub/sub → SSE);
  deadline wall lands < 3 min p95.
- **B6 (untrusted input):** all document text is wrapped in data-only delimiters
  in every prompt (prompt-injection defense, Doc §11.3).
- **B7 (uploads):** multipart upload with size cap, magic-byte/MIME validation,
  allowed-extension set, virus-scan stub, and S3 per-workspace prefixes. LocalStorage
  in dev/tests. The size cap is enforced before the full file is buffered into memory.
  File text extraction in the async upload path runs in `asyncio.to_thread` so it
  does not block the event loop.
- **B8 (upload limits):** ingestion cap 2 GB, BOQ cap 100 MB.
- **B9 (no blind decoding):** unknown extensions are not decoded as text; they are
  rejected as unsupported.
- **B10 (resumable upload):** tus endpoints support creation, PATCH chunking, and HEAD offset queries; completed uploads are validated, stored, and processed identically to multipart uploads.
- **B11 (async extraction):** `?async=1` creates a pending document and enqueues a Celery task; the SSE endpoint streams `PROGRESS`/`done`/`error` events, sleeps between polls, stops on client disconnect, and has a hard timeout. Celery falls back to eager execution when Redis is not configured. The Celery task classifies the document, segments clauses, extracts deadlines, updates `submission_due`, persists chunks, and applies OCR when `TS_OCR_ENABLED=true`.
- **B12 (deadline scoping):** `POST /opportunities/{id}/deadlines/{deadline_id}/confirm`
  verifies that the deadline belongs to the opportunity in the URL path; a mismatch
  returns 404.
- **B13 (sample text limits):** `POST /opportunities/{id}/documents` rejects a
  `sample_text` longer than 1,000,000 characters.

## Acceptance criteria

- A1: anchor classifier labels fixture NIT/GCC/SCC/BOQ correctly, no LLM call.
- A2: deadline rows without a verifiable quote are flagged low-confidence.
- A3: missing-doc checklist flags an absent SCC referenced by the NIT fixture.
- A4: oversized upload returns 413 before the full file is buffered.
- A5: invalid MIME/extension returns 415/422.
- A6: S3-backed storage with `moto` stores files under the workspace prefix.
- A7: SSE stream stops on client disconnect, polls with a sleep, and times out after
  a bounded interval.
- A8: confirming a deadline for a different `opportunity_id` returns 404.
- A9: async `process_document` produces clauses, deadlines, and a `submission_due`.
- A10: `POST /opportunities/{id}/documents` rejects `sample_text` > 1,000,000 chars.

## Out of scope

Scanned-BOQ OCR hardening (P2), addendum diff view (P2), drawing intelligence (gated).
