# TS-069 — Implement assistant SSE `/chat` and conversation/session persistence

**Status:** done
**Requirement:** spec audit; Doc §8
**Spec(s) updated:** `specs/modules/assistant.md`
**Module(s):** `assistant`
**Severity / Gate:** P2 · Spec audit

## What this builds

Streams the assistant's response token-by-token over SSE instead of one
blocking response, plus persists sessions/messages (`ChatSession`/
`ChatMessage`, TS-024) so a conversation survives across requests.

## Implementation

```python
# backend/app/modules/assistant/router.py
def stream_chat(...): ...
```

```python
# backend/app/modules/assistant/service.py
"""TS-069 adds conversation/session persistence and an SSE `/chat` stream endpoint."""

def _stream(...):
    """Generator of SSE `data:` lines for the chat response."""
```

Uses `ingestion.doc_text` (TS-068) and the existing `tools.py` grounding
functions (TS-024) unchanged — this task only changes transport
(blocking → streamed) and adds persistence, not the grounding contract.

## Files touched

- `backend/app/modules/assistant/{router,service,models}.py`

## Tests

- `backend/tests/modules/assistant/test_stream.py`

## Acceptance criteria

- [x] `/chat` streams SSE `data:` events incrementally, not one blocking
      JSON response.
- [x] A session's messages persist and are retrievable via
      `GET .../sessions/{id}/messages`.

## Commit

Predates commit-granular history (PR #10 bulk import).
