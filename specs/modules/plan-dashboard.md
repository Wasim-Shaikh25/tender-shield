# Tender Plan Dashboard — Spec

**Status:** in-progress — AI-generated, dynamic dashboard page that turns a natural-language question into structured cards, tables, charts, and Mermaid diagrams.
**Requirement refs:** Doc §9, §11.3
**Task refs:** TS-188

## Purpose

QS engineers and bid managers often need a single view that combines risk,
BOQ, deadlines, documents, and commercial factors. Instead of building a
static dashboard for every question, the assistant generates a structured
response and the frontend renders it dynamically with the right visual
component.

## Public interface

- **API routes** (prefix `/api/analytics/plan`):
  - `POST /api/analytics/plan` (viewer) — accepts `workspace_id`, `opportunity_id`,
    and `query`; returns a `PlanDashboard` JSON payload.
- **Frontend route:** `/plan` — a query box and a dynamic renderer.
- **Capability consumed (soft):** `assistant.agent` (LLM agent must accept a
  structured-output prompt and return JSON), `ingestion.service_factory`,
  `findings.store_factory`, `rulepacks.loader`.

## Data owned

None. The dashboard is a read-only projection over existing workspace data
(deadlines, findings, BOQ defects, documents, baselines). The generated
structure is transient and not persisted by default; a future follow-up may
allow saving snapshots.

## Behavior

- **B1 (natural-language first):** the user types a question or picks a
  template. The backend builds a prompt that includes the caller's identity,
  relevant tool results, and a JSON schema.
- **B2 (structured output only):** the model must return valid JSON matching
  `PlanDashboard`; malformed JSON or hallucinated fields are rejected and a
  fallback response is returned.
- **B3 (grounded in workspace data):** numbers, dates, severity counts, and
  citations come from deterministic tool results, not the model. The model's
  job is to select visualizations and summarize, not to invent data.
- **B4 (renderers):** the frontend supports at least:
  - `kpi` — metric card with label/value/trend.
  - `table` — columns and rows.
  - `chart` — `recharts` bar/line/pie chart with `labels` and `datasets`.
  - `mermaid` — a Mermaid diagram string rendered with `mermaid`.
  - `text` — markdown summary block.
- **B5 (tenant isolation):** the endpoint uses the principal's workspace and
  the injected `identity` block; super-admin queries must provide explicit
  `workspace_id` and are audit-logged.
- **B6 (prompt injection):** user query is sanitized and scanned by
  `app.core.prompt_guard` before being sent to the LLM.
- **B7 (fallback):** if the model is unavailable or returns invalid JSON, the
  endpoint returns a deterministic `text` block with a polite error and a
  link to the static analytics page.

## PlanDashboard schema (Pydantic)

```python
class DashboardSection(BaseModel):
    type: Literal["kpi", "table", "chart", "mermaid", "text"]
    title: str
    data: dict

class PlanDashboard(BaseModel):
    title: str
    summary: str
    sections: list[DashboardSection]
    citations: list[str] = []
```

- `kpi.data` keys: `label`, `value`, `trend` (optional `up|down|flat`), `unit`.
- `table.data` keys: `columns` (list of `{"key","label"}`), `rows` (list of dict).
- `chart.data` keys: `chart_type` (`bar|line|pie`), `labels`, `datasets`.
- `mermaid.data` key: `diagram` (string).
- `text.data` key: `content` (markdown string).

## Acceptance criteria

- A1: a query like "show risk severity distribution and deadline timeline"
  returns a payload with at least one chart/table/mermaid section.
- A2: the response JSON is validated; invalid model output returns a safe
  fallback `text` section.
- A3: the `/plan` page renders KPI cards, tables, charts, and Mermaid diagrams
  without raw JSON visible.
- A4: a non-member of the workspace receives the standard refusal.
- A5: a prompt-injection attempt in the query is sanitized/refused.

## Out of scope

Export to PDF/PowerPoint (P2), real-time collaborative editing, saved dashboard
snapshots (P2), 3D visualizations.
