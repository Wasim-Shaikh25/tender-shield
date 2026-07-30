# Assistant ("Ask TenderShield") — Spec

**Status:** implemented — grounded, tool-first Q&A: deterministic intents (deadlines, findings by severity, missing docs, rule-pack lookup) with citations work with no key; off-topic questions refused; free-form questions use an injected LLM agent only when ANTHROPIC_API_KEY is set (grounded-only). Versioned artifact-edit tool is a follow-up.
**Requirement refs:** Doc §8
**Task refs:** TS-024

## Purpose

In-app assistant grounded ONLY in the org's documents, the rule-pack, and
generated work products. Tools, not vibes; citations mandatory; refuses general
questions.

## Public interface

- **Capabilities consumed (soft):** `ingestion.service_factory` (deadlines,
  missing docs), `findings.store_factory` (filtered findings),
  `rulepacks.loader` (rule-pack lookup).
- **API routes** (prefix `/api/assistant`):
  - `POST /chat` (viewer) — transient single-turn Q&A.
  - `POST /sessions` (viewer) — create a chat session for an opportunity.
  - `GET /sessions` (viewer) — list org sessions, optionally filtered by opportunity.
  - `GET /sessions/{id}/messages` (viewer) — retrieve conversation history.
  - `POST /sessions/{id}/chat` (viewer) — persist user + assistant messages and answer.
  - `POST /sessions/{id}/stream` (viewer) — SSE stream of the assistant answer.

## Data owned

`chat_sessions` and `chat_messages` (org-scoped, RLS); retrieval of opportunity
facts uses `ingestion.service_factory` and `findings.store_factory` via
capability, not direct table access.

## Behavior

- **B1 (grounded-only):** answers only from tool results; nothing relevant →
  says so; general questions → polite refusal. User input is wrapped in data-only
  delimiters and run through a lightweight prompt-injection classifier; the response
  is rejected if it cites pages not present in the tool context.
- **B2 (tools):** `search_docs`, `list_deadlines`, `filter_findings`,
  `boq_query` (safe filter), `rulepack_lookup`, `regenerate_artifact_section`
  (versioned edit — never mutates approved artifacts, requires UI confirmation).
- **B3 (citations mandatory):** every factual sentence carries `[doc:<id> p<page>]`
  or `[pack:<ref>]`; uncited output blocked by the §6.5 validator family.
- **B4 (escalation honesty):** "should we bid?" returns the factor table + org
  weights + mandatory "commercial judgment call" banner; logged distinctly.
- **B5 (metering):** free 20 messages total; paid 300/mo soft cap; per-turn token
  budget alarms.
- **B6 (RLS-scoped):** all retrieval under the caller's org context.

## Acceptance criteria

- A1: off-topic question is refused.
- A2: a response with an uncited factual sentence is blocked/regenerated.
- A3: `AnthropicAgent` uses a valid, current Anthropic model identifier.
- A4: a prompt-injection attempt returns the grounded-only refusal.
- A5: a response citing a page not in tool context is rejected.

## Out of scope

Cross-tender queries (P3), Ops Copilot (Doc §17, P2–3 — separate admin app).
