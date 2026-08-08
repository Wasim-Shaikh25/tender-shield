# Round 13 Gap Closure — Spec

**Status:** draft  
**Requirement refs:** `docs/ROUND13_GAP_CLOSURE_REQUIREMENTS.md`; `PRODUCTION_READINESS_AUDIT.md` TS-SEC-02, TS-SEC-04, TS-UI-05, TS-UI-06; `docs/TenderShield_Full_Build_Doc.md` §9, §11.3, §14  
**Task refs:** TS-380, TS-381, TS-382, TS-383  

## Purpose

This spec captures the fourth batch of production-readiness hardening identified in the
Round 13 audit. It closes the remaining High-severity UX security gaps and the Phase 1
UI/API integration gaps that still block a public / paid production launch.

No new top-level backend modules are created. Existing interfaces are extended/hardened:

- **Frontend security** (`frontend/components/plan-dashboard.tsx`):
  - `MermaidSection` is replaced or guarded so LLM-generated diagrams cannot execute
    scripts or access the parent window.
- **Backend security** (`backend/app/modules/analytics/plan_agent.py`,
  `backend/app/modules/rulepacks/rag_service.py`):
  - `PlanDashboardAgent.generate()` and `RagSuggestionService._build_prompt()` reuse
    `app.core.prompt_guard` helpers.
- **Frontend integration** (`frontend/lib/api.ts`, `frontend/app/**/page.tsx`):
  - Phase 1 backend routes are either consumed by a UI page or explicitly deferred.
- **Frontend UX** (`frontend/app/opportunities/[id]/page.tsx`,
  `frontend/app/rulepacks/page.tsx`, `frontend/app/admin/audit-log/page.tsx`):
  - Raw-JSON `<pre>` blocks are replaced with typed summary cards/tables, with raw
    JSON available only in a collapsible debug panel.

## Public interface

### Frontend components

- `frontend/components/plan-dashboard.tsx`:
  - `MermaidSection` either renders an iframe-sandboxed Mermaid diagram or falls back
    to a plain text description when Mermaid is disabled.
  - New helper `sanitizeMermaid(input: string): string` removes script tags, event
    handlers, and dangerous directives while preserving Mermaid syntax.
- `frontend/components/json-summary.tsx`:
  - `KeyValueSummary` component for rendering arbitrary JSON objects as labelled
    key-value lists with optional expansion.

### Backend services

- `backend/app/modules/analytics/plan_agent.py`:
  - `PlanDashboardAgent.generate(query, context, identity=...)` sanitizes `query` and
    delimits both `query` and `context` before the LLM call.
  - Raises `PromptInjectionError` (mapped to `400 prompt_injection_detected`) when
    `looks_like_injection(query)` is true.
- `backend/app/modules/rulepacks/rag_service.py`:
  - `RagSuggestionService._build_prompt()` sanitizes `text_sample` and delimits both
    `text_sample` and the rulepack `summary`.
  - `suggest_from_file()` rejects `text_sample` that triggers `looks_like_injection()`
    with `400 prompt_injection_detected`.

### API client

- `frontend/lib/api.ts`:
  - New wrappers for the Phase 1 routes listed in `docs/ROUND13_GAP_CLOSURE_REQUIREMENTS.md`
    R3.1, or an explicit comment referencing the deferral document for routes that are
    intentionally not wired in this round.

## Data owned

No new database tables. Existing columns and configuration are used:

- `users.mfa_secret` and related fields already exist for TOTP enrollment.
- `documents.kind`, `documents.is_addendum`, and stored file keys support the document
  viewer text/stream/download features.
- `rulepacks`, `rulepack_files`, `rag_suggestions`, `correction_proposals` support the
  rulepack pattern and correction UI.

## Behavior

### B1 — Mermaid sandboxing (TS-380)

- **B1.1** `MermaidSection` accepts only a `diagram` string and an optional `id`.
- **B1.2** `diagram` is sanitized before rendering:
  - HTML `<script>` tags, event-handler attributes (`on*`), and `javascript:` / `data:`
    URLs are removed by a strict regex/whitelist sanitizer.
  - `%%init` and other Mermaid directives that can execute arbitrary callbacks are
    stripped.
- **B1.3** The sanitized diagram is rendered inside an `<iframe sandbox>` with
  `srcdoc` containing the Mermaid runtime and the diagram text. The iframe is styled
  to match the parent card but has no access to `window.parent`.
- **B1.4** If `NEXT_PUBLIC_ALLOW_MERMAID=false` or the feature flag is off, the
  component renders "Mermaid diagrams are disabled" and does not load the `mermaid`
  bundle.
- **B1.5** Sanitization failures result in a user-visible placeholder, not an empty
  or partially-rendered diagram.

### B2 — Prompt-injection guards (TS-381)

- **B2.1** `PlanDashboardAgent.generate()`:
  - Validates that `query` is a string and is non-empty.
  - Calls `sanitize_message(query)` and rejects if `looks_like_injection(query)`.
  - Wraps `query` in `<user_query>` delimiters.
  - JSON-encodes `context` and wraps it in `<tool_results>` delimiters.
  - The system prompt remains unchanged; it instructs the model to ignore any
    instructions inside the delimited blocks.
- **B2.2** `RagSuggestionService._build_prompt()`:
  - Sanitizes `text_sample` and rejects if `looks_like_injection(text_sample)`.
  - Wraps `text_sample` in `<source_text>` delimiters.
  - JSON-encodes `summary` and wraps it in `<rulepack_summary>` delimiters.
  - The fixed instruction text is moved outside the delimited blocks.
- **B2.3** No new guard code is written; the helpers in `app.core.prompt_guard` are
  imported and reused.

### B3 — Phase 1 route wiring (TS-382)

- **B3.1** For each Phase 1 route listed in `docs/ROUND13_GAP_CLOSURE_REQUIREMENTS.md`
  R3.1, a typed wrapper is added to `frontend/lib/api.ts`.
- **B3.2** Each new wrapper is called from at least one `frontend/app/**/page.tsx` or
  is explicitly commented as deferred with a reference to `docs/PHASE2_UI_ROADMAP.md`.
- **B3.3** A new script `scripts/validate_ui_api_coverage.py` is added. It parses
  `frontend/lib/api.ts` and the FastAPI router tree, reports unconsumed routes, and
  exits non-zero when Phase 1 routes are missing consumers.
- **B3.4** Phase 2+ unconsumed routes are documented in `docs/PHASE2_UI_ROADMAP.md`.

### B4 — Raw-JSON `<pre>` replacement (TS-383)

- **B4.1** A `KeyValueSummary` component in `frontend/components/json-summary.tsx`
  renders arbitrary JSON as labelled key-value pairs up to a configurable depth.
- **B4.2** The opportunity audit tab (`frontend/app/opportunities/[id]/page.tsx`)
  renders `a.meta` with `KeyValueSummary`; unknown extra fields are hidden behind a
  "Raw metadata" collapsible panel.
- **B4.3** The rulepack suggestions page (`frontend/app/rulepacks/page.tsx`) renders
  `s.proposed_yaml` with `KeyValueSummary`; deep nesting is collapsible.
- **B4.4** The admin audit-log page (`frontend/app/admin/audit-log/page.tsx`) renders
  `l.detail` with `KeyValueSummary`; the full JSON remains available in a "Raw detail"
  collapsible panel.
- **B4.5** No `dangerouslySetInnerHTML` is used; all values are React-rendered strings.

## Acceptance criteria

- A1. `npm run lint`, `npm run typecheck`, and `npm run build` are clean; the build
  produces at least 33 routes.
- A2. `cd backend && .venv/bin/ruff check .` and `.venv/bin/mypy app` are clean.
- A3. `cd backend && .venv/bin/pytest -q` returns 663 passed / 5 skipped.
- A4. Frontend unit/component tests assert that a malicious Mermaid string does not
  produce an active `<script>` or `javascript:` link.
- A5. Backend tests assert that `PlanDashboardAgent` and `RagSuggestionService` reject
  or sanitize a prompt containing `ignore previous instructions` and `</user_query>`.
- A6. `grep -n "JSON.stringify" frontend/app/**/page.tsx` shows only legitimate
  download-blob/connector-prefill uses and the three explicitly named "Raw" debug
  panels.
- A7. `docs/PHASE2_UI_ROADMAP.md` exists and lists all Phase 2+ unconsumed routes
  with module, route, method, and deferral justification.
- A8. `PRODUCTION_READINESS_AUDIT.md` is updated in the next audit round to mark
  TS-380 through TS-383 as closed with evidence commands and commit hashes.

## Out of scope

- `TS-R03` — severity fallback to `medium` remains a low-priority accuracy refinement.
- `TS-UI-03` — baseline/opportunity detail console noise is re-verified separately.
- `TS-E2E-01` — Playwright golden-path update is a QA task, tracked independently.
- Phase 2+ feature modules (advisor, analytics, control tower, full claims/evidence/
  marketdata/outcomes UIs) are not built in this batch; they are deferred in
  `docs/PHASE2_UI_ROADMAP.md`.
