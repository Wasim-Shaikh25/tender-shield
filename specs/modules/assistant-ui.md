# AI Assistant UI — Spec

**Status:** implemented
**Requirement refs:** Doc §8, §9; `specs/modules/assistant.md`; user request
**Task refs:** TS-352

## Purpose

Improve the in-app assistant's front-end so it feels like a modern chat product:
- persistent threaded history,
- rich markdown rendering (lists, tables, code, citations),
- follow-up context so the assistant remembers what the user said earlier in the
  same thread.

The backend already exposes `POST /api/assistant/sessions/{id}/chat` and a
streaming endpoint (`/stream`); this spec focuses on the UI and the small backend
changes needed to support markdown/structured responses and thread memory.

## Public interface

### Backend routes to extend/reuse

- `POST /api/assistant/sessions` — create a session.
- `GET /api/assistant/sessions` — list sessions for the workspace.
- `GET /api/assistant/sessions/{id}/messages` — fetch history.
- `POST /api/assistant/sessions/{id}/chat` — non-streaming single answer.
- `POST /api/assistant/sessions/{id}/stream` — SSE streaming answer.

### New response envelope fields

Assistant messages may now include:

```json
{
  "type": "message",
  "role": "assistant",
  "content": "markdown text with [doc:<id> p<page>] citations",
  "citations": [
    {"kind": "doc", "doc_id": "...", "page": 3, "quote": "..."}
  ],
  "suggested_followups": ["What are the top 3 risks?", "Show me the BOQ gaps."],
  "dashboard": null | PlanDashboard
}
```

`content` is CommonMark with a small TenderShield citation extension.

## Data owned

No new backend tables; reuses `chat_sessions` / `chat_messages` from
`specs/modules/assistant.md`. Adds an optional `render_format` enum
(`plain`, `markdown`, `dashboard`) to `chat_messages`.

## Behavior

- **B1 (threaded history):** the assistant UI keeps a session ID. Each user
  message and assistant reply is appended to the session; the backend sends the
  last N messages (default 20, max 100) as conversation context to the LLM.
- **B2 (follow-up memory):** when a user asks "how did I greet you?", the model
  sees the full recent history and can answer accurately. History is pruned to
  fit token budget by dropping oldest pairs first, never the current user message.
- **B3 (markdown rendering):** the UI renders assistant `content` as sanitized
  markdown using `react-markdown` (or equivalent) with Tailwind typography. Code
  blocks are syntax-highlighted; tables scroll horizontally on mobile.
- **B4 (citation chips):** `[doc:<id> p<page>]` links are parsed and rendered as
  clickable chips that open the document viewer at the quoted page. Citations
  from `citations[]` are displayed as a collapsible "Sources" panel below the
  assistant answer.
- **B5 (suggested follow-ups):** after each assistant reply, up to 3 chips are
  shown; clicking one appends the question to the chat and submits it.
- **B6 (dashboard cards):** when `type == "dashboard"`, the message body is
  hidden and a Tailwind dashboard card is rendered from `dashboard` payload
  (title, chart type, metrics, action items).
- **B7 (streaming):** the SSE endpoint emits `chunk` deltas. The UI buffers
  chunks and runs markdown parsing at the end (or incrementally for plain text).
- **B8 (new conversation):** a "+" button creates a fresh session; previous
  sessions remain in a sidebar.
- **B9 (opportunity/workspace scope):** the chat is scoped to the current
  workspace or the selected opportunity. The scope is shown in the header and
  can be switched from the sidebar.
- **B10 (copy/export):** each assistant message has a copy-to-clipboard button
  and an option to export the whole thread as `.md`.
- **B11 (safety):** user markdown input is plain text only; XSS is prevented by
  rendering assistant output through a sanitizer that strips raw HTML and only
  allows CommonMark + citation spans.

## Acceptance criteria

- A1: a new session starts empty and the assistant greets with scope info.
- A2: asking "hi" then "what did I just say?" returns "You said hi."
- A3: assistant replies render bullets, numbered lists, tables, and code blocks.
- A4: citation chips are clickable and navigate to the referenced document page.
- A5: suggested follow-ups send a new message when clicked.
- A6: dashboard-type responses render the chart/metric card, not raw JSON.
- A7: switching opportunity/workspace updates the assistant context without
  losing the session list.
- A8: long threads load with pagination ("Load earlier messages").
- A9: export thread produces a `.md` file with timestamps and citations.
- A10: raw HTML in assistant output is stripped/escaped before rendering.

## Out of scope

- Real-time collaboration on a single thread.
- Voice/image input.
- Cross-workspace chat for non-super-admins.
- Inline artifact editing inside the chat (keep existing draft-review flow).

## Assumptions

- `react-markdown` and `remark-gfm` can be added to `frontend/package.json`.
- The backend `chat_messages` table stores markdown as plain text; rendering is
  purely a UI concern.
- Token budget for history is controlled by the backend via `app.core.config`.
