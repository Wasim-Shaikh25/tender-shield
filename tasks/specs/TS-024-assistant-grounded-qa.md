# TS-024 — `assistant` module: grounded Q&A over org corpus, citations mandatory

**Status:** done
**Requirement:** Doc §8
**Spec(s) updated:** `specs/modules/assistant.md`
**Module(s):** `assistant`
**Severity / Gate:** P1 · Phase 1 MVP

## What this builds

Chat over the org's own tender corpus (deadlines, findings, clauses) with
tool-use grounding — the assistant answers only from tool results, never
free-form knowledge, and every answer must cite what it drew from.

## Implementation

```python
# backend/app/modules/assistant/agent.py
class AnthropicAgent:
    """Tool-use loop: the model may only answer using data returned by
    tools.py's functions — no un-cited general knowledge answers."""
```

```python
# backend/app/modules/assistant/tools.py
def list_deadlines(ingestion_factory, session, workspace_id, opportunity_id) -> list[dict]: ...
def filter_findings(...) -> list[dict]: ...
```

```python
# backend/app/modules/assistant/models.py
class ChatSession(Base, WorkspaceScopedMixin): ...
class ChatMessage(Base, WorkspaceScopedMixin): ...
```

Because tender text is untrusted input reaching an LLM, this is one of the
surfaces CLAUDE.md §4's prompt-injection defense applies to — tool outputs
are treated as data, not as instructions to the agent.

## Files touched

- `backend/app/modules/assistant/{agent,tools,models,service,router,module}.py`

## Tests

- `backend/tests/modules/assistant/test_tools.py`

## Acceptance criteria

- [x] Every assistant answer is grounded in tool-call results, not free
      knowledge.
- [x] Chat history persists per workspace (`ChatSession`/`ChatMessage`),
      RLS-scoped like every other org table.

## Commit

Predates commit-granular history (PR #10 bulk import).
