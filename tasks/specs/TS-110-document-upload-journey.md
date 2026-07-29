# TS-110 — Document upload journey: file picker/drag-drop, multipart client, per-file progress + failure

**Status:** todo
**Requirement:** [R-017](../../specs/requirements/R-017-document-upload-journey.md)
**Spec(s) updated:** `specs/modules/ingestion.md` (to be updated when built)
**Module(s):** frontend, `ingestion`
**Severity / Gate:** P0 · Gate 5

## What this builds

The single biggest gap `docs/PRODUCT_DISCOVERY_GAPS.md` (TS-126's audit)
found: **no customer can upload their own tender.** The backend's hardened
`/upload` endpoint (TS-095, TS-026) has no UI at all — the app only
analyses a hardcoded sample. Everything downstream (classify, deadlines,
risk, BOQ) already works; this is the missing front door.

## Implementation (reference plan — not yet built)

A drop zone on the opportunity page and the board's empty state: select or
drag N files → a row per file showing progress, detected type, and
classification result → the document checklist and deadline wall refresh
as each completes.

```ts
// frontend/lib/api.ts — multipart branch
// TRAP: must NOT set Content-Type — the browser sets the multipart
// boundary, and the existing withAuth() helper unconditionally sets
// application/json, which would corrupt the request body.
export async function upload<T>(path: string, file: File, token: string,
                                 onProgress?: (pct: number) => void): Promise<T>
// Needs XMLHttpRequest (or a streamed fetch with a ReadableStream body) —
// plain fetch reports no upload progress.
```

Per-file failure, not per-batch: a file rejected for size/type/corruption
reports its own specific reason and stays retryable without discarding the
rest of the batch. Client-side size/extension pre-checks are a courtesy
for fast feedback only — the server's magic-byte validation (TS-095) stays
the actual authority; a client that skips the check must still be
rejected. The existing "sample" button stays, relabelled "Try a sample," as
a genuine demo affordance.

## Files touched (planned)

- `frontend/lib/api.ts` (multipart upload branch)
- `frontend/app/opportunities/[id]/page.tsx` (drop zone, per-file rows)
- `backend/app/modules/ingestion/router.py` (per-file error responses if
  not already granular enough)

## Tests (planned)

- E2E: upload a real multi-page PDF → clauses and deadlines appear
  (Playwright, per TS-104's planned test stack)

## Acceptance criteria (R-017, A1–A6)

- [ ] A real multi-page PDF uploads through the UI and produces clauses and
      deadlines, with no hardcoded sample involved.
- [ ] Upload progress is visible per file, not just per batch.
- [ ] A rejected file reports its specific reason and does not abort the
      rest of the batch.
- [ ] A failure mid-transfer leaves no half-ingested document.

## Commit

Not yet implemented.
