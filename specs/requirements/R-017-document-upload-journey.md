# R-017 — Document upload journey

**Status:** draft
**Severity:** P0 — a customer cannot upload their own tender; the product only
analyses its own built-in fixture
**Requirement refs:** Doc §1.3 (NFR), §6.1; product overview §NFR
**Task refs:** TS-110
**Gap refs:** `docs/PRODUCT_DISCOVERY_GAPS.md` §G-01
**Specs to update:** `specs/frontend.md`, `specs/modules/ingestion.md`

## Purpose

`POST /api/ingestion/opportunities/{id}/upload` is fully implemented and was
hardened in TS-095 (streaming to a size-capped temp file, magic-byte validation
before anything is persisted). It has **no user interface**.

There is no `<input type="file">`, no `FormData`, and no call to `/upload`
anywhere in `frontend/`. The only path a document takes into the system through
the UI is the "Upload sample tender" button, which posts a hardcoded 12-line
demo string:

```tsx
// frontend/app/opportunities/[id]/page.tsx:25, :111
const SAMPLE = `[p1]
NOTICE INVITING TENDER (NIT No. TS/DEMO/2026/001) …`;
await api.registerDocument(session!.token, id, "nit-and-conditions.md", SAMPLE);
```

```ts
// frontend/lib/api.ts:122 — JSON, not multipart
registerDocument: (token, id, filename, sample_text) =>
  req(`/ingestion/opportunities/${id}/documents`,
      { method: "POST", body: JSON.stringify({ filename, sample_text }) }, token),
```

Everything downstream — risk review, BOQ checks, deadline extraction, artifacts,
export, and the paywall that charges ₹7,500 per review — currently operates
exclusively on that fixture.

## Target

### B.1 Upload component

A drop zone on the opportunity page and in the board's empty state: select or
drag N files → a row per file showing progress, detected type and classification
result → the document checklist and deadline wall refresh as each completes.

### B.2 Multipart in the API client

`lib/api.ts` gains a multipart branch. Note the trap: it must **not** set
`Content-Type` — the browser sets the multipart boundary, and the existing
`withAuth()` helper unconditionally sets `application/json`, which would corrupt
the request body.

```ts
export async function upload<T>(path: string, file: File, token: string,
                                onProgress?: (pct: number) => void): Promise<T>
```

Progress needs `XMLHttpRequest` (or a streamed `fetch` with a
`ReadableStream` body); `fetch` alone reports no upload progress.

### B.3 Per-file failure, not per-batch

A file rejected for size, type or corruption reports its own specific reason and
stays retryable without discarding the rest of the batch. Server-side rejection
messages (`file_too_large`, `unsupported_type`) map to human copy.

### B.4 Client-side pre-checks are a courtesy, never the control

Size and extension are checked client-side for fast feedback only. The server's
magic-byte validation (R-003 §B.2) remains the authority — a client that skips
the check must still be rejected.

### B.5 The sample stays

The existing sample button is relabelled "Try a sample" and kept as a genuine
demo affordance for evaluation without a real pack.

## Behavior

- **B1** A real multi-page PDF uploads and produces clauses and deadlines.
- **B2** Upload progress is visible per file.
- **B3** A rejected file reports its specific reason and does not abort the batch.
- **B4** A failure mid-transfer leaves no half-ingested document.
- **B5** The document list shows what was ingested and how it was classified.
- **B6** `estimator` or above may upload; `viewer` sees results only.

## Acceptance criteria

- **A1** A real tender PDF (≥ 50 pages) uploads end to end and yields clauses +
  extracted deadlines.
- **A2** A file over the cap is rejected client-side *and*, when the client check
  is bypassed, server-side — verified by posting directly to the endpoint.
- **A3** A file whose extension lies about its content (e.g. `.pdf` containing a
  ZIP) is rejected by magic bytes.
- **A4** Killing an upload mid-transfer leaves no `documents` row and no stored blob.
- **A5** Uploading three files reports three independent statuses.
- **A6** The sample button still works unchanged.

## Out of scope

- **Resumable/chunked upload.** The product overview §1.3 requires it; this task
  delivers single-shot upload up to the cap only. Resumability is a separate task
  and should be sequenced with R-016/TS-106 (S3 multipart).
- **ZIP ingestion** (§1.3) — no ZIP path exists anywhere yet, and R-003 §B.4
  deferred ZIP-bomb guards for exactly that reason. Building ZIP ingestion means
  building those guards first.
- OCR tuning; the existing `ingestion.ocr` capability is consumed as-is.

## Assumptions

- `assumption:` single-shot upload within the existing cap is acceptable for a
  design-partner launch. This is a **product decision** — the 800-page NFR
  implies packs well above a typical default cap, so the real maximum pack size
  needs confirmation before the cap is treated as adequate.
- `assumption:` local disk storage is acceptable until R-016/TS-106 lands S3.
  Real uploads make `TS_STORAGE_DIR` a genuine operational dependency —
  ephemeral container disk will lose customer files on restart.
