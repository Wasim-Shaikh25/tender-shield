# Cross-Reference & Clause Diff — Spec

**Status:** implemented (TS-053 + TS-051)
**Requirement refs:** Phase 1.5 doc §5
**Task refs:** TS-053, TS-051

## Purpose

Two related trust features that sit on top of the ingestion clause store:

1. **Clause Cross-Reference (TS-053):** search a topic/term across every document
   in an opportunity and get back ranked clause snippets with provenance.
2. **Clause Change Detection (TS-051):** compare two versions of a document
   (explicit `supersedes` chain or the two most recent uploads of the same kind)
   and report added, removed, and changed clauses.

## Public interface

- **Capability published:** `crossref.service_factory`.
- **Capabilities consumed (soft):** `ingestion.service_factory`.
- **Events:** none.
- **API routes** (prefix `/api/crossref`):
  - `GET /opportunities/{id}?q=<query>&limit=<n>` — ranked clause search.
  - `POST /opportunities/{id}/diff?document_id=<id>` — diff vs the superseded
    document; if omitted, compares the two latest documents of the same kind.

## Data owned

None. Reads documents and clauses through `ingestion`.

## Behavior

- **B1 — Keyword search.** Query is tokenised into lowercase words. Each clause
  is scored by token overlap against the query, normalised by the larger token set.
  Results include document filename/kind, clause ref, heading, page, and a
  300-char text preview.
- **B2 — Diff resolution.** If `document_id` is supplied, its `supersedes` column
  identifies the old version. Otherwise the service groups documents by `kind`
  and uses the two most recent uploads. If neither exists, it walks the
  opportunity's `supersedes` links.
- **B3 — Clause matching.** Clauses are keyed by `clause_ref` when present;
  unsegmented clauses use a synthetic positional key. A clause is `changed` when
  its normalised text differs from the old version; otherwise it is `added` or
  `removed`.
- **B4 — Org isolation.** All reads are scoped to the opportunity (and therefore
  to the org) by delegating to the ingestion service, which enforces its own
  org filter.

## Acceptance criteria

- A1: `GET /opportunities/{id}?q=payment` returns clauses containing "payment"
  ranked above unrelated clauses.
- A2: Uploading a second version of a document and calling `POST /diff` reports
  the added/removed/changed clauses.
- A3: Passing `document_id` of a document with `supersedes` set compares that
  specific pair.

## Out of scope

- Semantic similarity / embeddings (P2); paragraph-level diff (P2); automatic
  corrigendum ingestion (P2).
