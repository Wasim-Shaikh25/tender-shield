# Assistant ("Ask TenderShield") — Spec

**Status:** implemented — grounded, tool-first Q&A: deterministic intents (deadlines, findings by severity, missing docs, rule-pack lookup) with citations work with no key; off-topic questions refused; free-form questions use an injected LLM agent only when `TS_OPENROUTER_API_KEY` or `OPENROUTER_API_KEY` is set (grounded-only). User input is sanitized, delimited, and scanned for prompt-injection patterns before reaching the LLM. Versioned artifact-edit tool is a follow-up.
**Requirement refs:** Doc §8, §11.3
**Task refs:** TS-024, TS-112, TS-145, TS-164, TS-193, TS-195

## Purpose

In-app assistant grounded ONLY in the org's documents, the rule-pack, and
generated work products. Tools, not vibes; citations mandatory; refuses general
questions.

## Public interface

- **Capabilities consumed (soft):** `ingestion.service_factory` (deadlines,
  missing docs), `findings.store_factory` (filtered findings),
  `rulepacks.loader` (rule-pack lookup), `auth.workspace_factory` (owner/membership checks).
- **API routes** (prefix `/api/assistant`):
  - `POST /chat` (viewer) — transient single-turn Q&A. `opportunity_id` is optional; when omitted the assistant reasons across the whole workspace.
  - `POST /sessions` (viewer) — create a chat session for a workspace (optional `opportunity_id`).
  - `GET /sessions` (viewer) — list sessions the caller can access, optionally filtered by opportunity.
  - `GET /sessions/{id}/messages` (viewer) — retrieve conversation history.
  - `POST /sessions/{id}/chat` (viewer) — persist user + assistant messages and answer. `opportunity_id` is optional.
  - `POST /sessions/{id}/stream` (viewer) — SSE stream of the assistant answer. `opportunity_id` is optional.
  - `POST /chat` and `POST /sessions/{id}/chat` may return `type: "dashboard"` with a `dashboard` field containing a `PlanDashboard` (KPI/table/chart/mermaid/text) when the query asks for a visual summary.
  - `POST /admin/chat` (super-admin) — transient cross-tenant research chat. `opportunity_id` is optional; queries are logged to the audit log.

## Data owned

`chat_sessions` and `chat_messages` (workspace-scoped, RLS); retrieval of
opportunity facts uses `ingestion.service_factory` and `findings.store_factory` via
capability, not direct table access. Super-admin chat mode is audit-logged but does
not persist sessions.

## Behavior

- **B1 (grounded-only):** answers only from tool results; nothing relevant →
  says so; general questions → polite refusal. User input is sanitized and
  wrapped in data-only `<user_query>` / `<tool_results>` delimiters by
  `app.core.prompt_guard`; a lightweight prompt-injection classifier rejects
  the request if it matches common override/jailbreak patterns. The response is
  rejected if it cites pages not present in the tool context.
- **B2 (tools):** `search_docs`, `list_deadlines`, `filter_findings`,
  `boq_query` (safe filter), `rulepack_lookup`, `regenerate_artifact_section`
  (versioned edit — never mutates approved artifacts, requires UI confirmation).
- **B3 (citations mandatory):** every factual sentence carries `[doc:<id> p<page>]`
  or `[pack:<ref>]`; uncited output blocked by the §6.5 validator family.
- **B4 (escalation honesty):** "should we bid?" returns the factor table + org
  weights + mandatory "commercial judgment call" banner; logged distinctly.
- **B5 (metering):** free 20 messages total; paid 300/mo soft cap; per-turn token
  budget alarms.
- **B6 (workspace-scoped):** the assistant answers at workspace scope by default.
  When `opportunity_id` is supplied it narrows to one tender; when it is omitted
  deadlines, findings, and documents are aggregated across the workspace's
  opportunities. The assistant never retrieves rows outside the principal's workspace.
- **B7 (user-bound sessions):** `chat_sessions` and `chat_messages` are filtered
  by `workspace_id` so a user can only see sessions created in workspaces they
  belong to. Super-admin chat does not create sessions; it is a transient,
  audit-logged query endpoint.
- **B8 (identity in prompt):** the assistant system prompt includes the caller's
  `user_id`, `workspace_id`, and `role` so the model is aware of the tenancy
  boundary and refuses to switch context to another account/workspace.
- **B9 (admin mode gate):** `POST /admin/chat` requires `is_superadmin == true`
  and a verified `superadmin` role. The response is still grounded in the explicit
  `workspace_id` and `opportunity_id` supplied by the admin; it does not allow
  broad cross-tenant search by default.
- **B10 (dashboard intent):** user messages containing dashboard/visual keywords trigger `PlanDashboardAgent` to generate a structured `PlanDashboard`. The response is returned as `type: "dashboard"` so the UI can render it in a collapsible panel without switching pages. If no `opportunity_id` is supplied, the agent targets the first opportunity in the workspace or aggregates workspace facts. If the LLM is unavailable, the agent's fallback is returned with a clear message.

## Acceptance criteria

- A1: off-topic question is refused.
- A2: a response with an uncited factual sentence is blocked/regenerated.
- A3: `OpenRouterAgent` uses a valid OpenRouter model identifier.
- A4: a prompt-injection attempt returns the grounded-only refusal.
- A5: a response citing a page not in tool context is rejected.
- A6: `app.core.prompt_guard.sanitize_message` caps length and strips attempts to
  close `<user_query>` / `<tool_results>` tags from user content.
- A7: a non-member cannot access another workspace's chat sessions or tool results.
- A8: the LLM system prompt contains the caller's `user_id` and `workspace_id`
  and refuses queries about other tenants.
- A9: `POST /api/assistant/admin/chat` rejects non-super-admin callers and logs
  every admin query to the audit log.
- A10: a query with dashboard/visual keywords returns `type: "dashboard"` with a valid
  `PlanDashboard` payload and the UI renders it in a collapsible panel.
- A11: a query without an explicit `opportunity_id` aggregates workspace data and does not fail due to a missing opportunity dropdown.

## Out of scope

Cross-tender queries (P3), Ops Copilot (Doc §17, P2–3 — separate admin app),
broad cross-tenant semantic search without explicit `workspace_id/opportunity_id`.
