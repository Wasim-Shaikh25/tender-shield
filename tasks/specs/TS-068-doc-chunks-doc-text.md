# TS-068 — Implement `ingestion.doc_chunks` table and `ingestion.doc_text` capability

**Status:** done
**Requirement:** spec audit; Doc §3.3
**Spec(s) updated:** `specs/modules/ingestion.md`
**Module(s):** `ingestion`
**Severity / Gate:** P2 · Spec audit

## What this builds

Page-level text storage (`doc_chunks`) and a `DocTextService` capability for
fetching a document's or a single page's text — needed so `assistant`
(TS-069) and other consumers can pull page-level text without re-running
extraction.

## Implementation

```python
# backend/app/modules/ingestion/models.py
class DocChunk(Base, WorkspaceScopedMixin):
    __tablename__ = "doc_chunks"
```

```python
# backend/app/modules/ingestion/doc_text.py
"""Page-level text chunks and the `ingestion.doc_text` capability (TS-068)."""

def persist_chunks(...) -> None:
    """Replace existing doc_chunks for a document with the current extraction."""

class DocTextService:
    def text_for_document(self, document_id) -> str: ...
    def text_for_page(self, document_id, page: int) -> str: ...
```

```python
# backend/app/modules/ingestion/module.py
reg.provide("ingestion.doc_text", lambda session: DocTextService(session))
```

## Files touched

- `backend/app/modules/ingestion/{models,doc_text,service,module,router}.py`
- `backend/migrations/versions/` (new `doc_chunks` migration)

## Tests

- `backend/tests/modules/ingestion/test_doc_text.py`

## Acceptance criteria

- [x] `ingestion.doc_text` resolves to a working `DocTextService` via the
      registry.
- [x] `text_for_page` returns only that page's text, not the whole document.

## Commit

Predates commit-granular history (PR #10 bulk import).
