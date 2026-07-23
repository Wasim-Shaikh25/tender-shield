# Ingestion — Spec

**Status:** implemented (Phase-1 core) — opportunities/documents + rules-first
classification + missing-doc checklist (TS-014), clause segmentation (TS-016),
and deterministic deadline extraction + deadline wall + confirm chips (TS-015).
Relative-date formula resolution and LLM-assisted extraction for messy scans are
follow-ups. API mounted under `/api/ingestion/opportunities`.
**Requirement refs:** Doc §3.3, §6.1, §6.2
**Task refs:** TS-014, TS-015, TS-016

## Purpose

Owns the opportunity aggregate and the document path: resumable upload → classify
→ OCR → deadline extraction (the <3-minute promise) → clause segmentation.
Everything downstream (risk, BOQ, drafting) consumes its outputs.

## Public interface

- **Capabilities published:** `ingestion.opportunities` (CRUD/query),
  `ingestion.clauses` (clause retrieval for risk engine),
  `ingestion.doc_text` (page text access).
- **Capabilities consumed (soft):** `rulepacks.loader` (doc types, expected-doc
  set, deadline calculators), `billing.metering` (review authorization gate).
- **Events emitted:** `document.uploaded`, `document.classified`,
  `document.ocr_completed`, `deadlines.extracted`, `clauses.segmented`,
  `opportunity.processing_completed`.
- **API routes:** `/api/opportunities` CRUD, document upload/list,
  `/api/opportunities/{id}/deadlines`, missing-doc checklist endpoint.

## Data owned

`opportunities`, `documents`, `clauses`, `deadlines`, `doc_chunks`.

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
- **B7 (uploads):** tus resumable, ZIP-aware, virus-scanned, magic-byte MIME
  sniffing, 2GB cap; S3 per-org prefixes, SSE-KMS.

## Acceptance criteria

- A1: anchor classifier labels fixture NIT/GCC/SCC/BOQ correctly, no LLM call.
- A2: deadline rows without a verifiable quote are flagged low-confidence.
- A3: missing-doc checklist flags an absent SCC referenced by the NIT fixture.

## Out of scope

Scanned-BOQ OCR hardening (P2), addendum diff view (P2), drawing intelligence (gated).
