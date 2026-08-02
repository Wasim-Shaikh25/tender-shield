# Findings — Spec

**Status:** implemented
**Requirement refs:** Doc §3.2, §6.3, §6.4, §11.4; Strategy §C.7
**Task refs:** TS-017, TS-018, TS-049, TS-054, TS-055, TS-056, TS-114, TS-219, TS-294, TS-295

## Purpose

The shared `findings` table is the single source of truth for anything the
system discovers about a tender: risk clauses, BOQ defects, scope gaps,
missing documents, qualification gaps, deadline warnings, and standard
violations. One module owns the row storage and review-state columns; every
producer writes through the `findings.store_factory` capability and every
consumer reads/updates through the same capability. No other module imports
`findings` models directly.

## Public interface

- **Capabilities published:**
  - `findings.store_factory` → `FindingStore(session)` with `replace_for_producer`,
    `list`, `list_for_org`, `get`, `set_review`.
- **Capabilities consumed (soft):** none.
- **Events emitted:** none.
- **Events consumed:** none.
- **API routes** (prefix `/api/findings`):
  - `GET /opportunities/{opportunity_id}` (viewer) — list findings for an
    opportunity, sorted by severity.

## Data owned

`findings` (org-scoped, RLS): one row per generated finding.

Columns:
- `id`, `org_id`, `opportunity_id`
- `producer` (e.g. `risk`, `boq`, `qualification`, `standards`)
- `kind` (`risk_clause`, `boq_defect`, `scope_gap`, `missing_doc`,
  `qualification_gap`, `standard_violation`, `deadline`)
- `category`, `severity`, `title`, `detail`, `source`
- `source_page`, `source_quote` (verbatim, ≤200 chars)
- `affected_trades` (JSON list), `suggested_action`
- `pattern_id`, `pattern_version`
- `amount_exposure` (BigInteger) — monetary exposure in minor units (paise)
- `currency` (String, ISO 4217) — explicit currency for `amount_exposure` (TS-295)
- `document_id` (Uuid, nullable) — source document for quote/citation resolution (TS-294)
- `facts` (JSON, nullable) — structured extraction facts (e.g. `payment_days`,
  `project_duration_months`) for pricing loading (TS-296)
- `review_status` (`proposed` | `accepted` | `edited` | `rejected` |
  `false_positive` | `needs_clarification`)
- `review_note`, `review_reason`, `reviewed_by`
- `explanation` (JSON, for `risk_clause` explainability)
- `disclaimer` (nullable string; e.g. beta/unvalidated pattern warning)
- `rulepack_version`, `model_id`, `prompt_hash`, `document_hash`, `engine_version`
  (reproducibility chain, Strategy §C.7 / TS-219)

## Behavior

- **B1 — Shared contract:** Producers hand `Finding` Pydantic objects from
  `app.core.contracts.findings`; the store maps them to `FindingRow`.
- **B2 — Idempotent re-run:** `replace_for_producer(org, opp, producer, findings)`
  deletes only the rows for that `(org, opp, producer)` triple and inserts the
  new set. A risk re-run never deletes BOQ rows.
- **B3 — Org isolation:** Every query is filtered by `org_id`. RLS is enabled on
  the PostgreSQL table.
- **B4 — Review state:** The `review` module calls `set_review` to update
  `review_status`, `review_note`, `review_reason`, and `reviewed_by`. No other
  module mutates these columns.
- **B5 — Severity sort:** Listing defaults to severity descending
  (`critical` → `info`).
- **B6 — Beta disclaimer:** `risk` producers set `disclaimer` on findings generated
  from `unvalidated` rule-patterns when the workspace is allowed to see them
  (free workspace, or paying workspace with `TS_BETA_UNVALIDATED=true`).
- **B7 — No cross-module FKs:** `findings.opportunity_id` is a plain `Uuid` column;
  it is not declared as a `ForeignKey` to `opportunities` (or any other module-owned
  table). The store enforces opportunity scoping in code and via RLS.
- **B8 — Reproducibility chain (TS-219):** Every producer stamps
  `rulepack_version`, `model_id` (`"none"` for deterministic paths),
  `prompt_hash` (LLM calls only), `document_hash` (stable hash of the input
  document set), and `engine_version` on each finding at run time. Deterministic
  findings must be byte-identical on re-run with the same inputs; enforced by
  tests.

## Acceptance criteria

- A1: `replace_for_producer` replaces only the calling producer's rows for an
  opportunity, leaving other producers intact.
- A2: A finding written by one producer and reviewed by the review module keeps
  its review state after a re-run of a different producer.
- A3: `GET /api/findings/opportunities/{id}` returns only findings for the
  caller's org.
- A4: `FindingRow.opportunity_id` has no `ForeignKey` to `opportunities` and the
  metadata architecture test asserts this.
- A5: Provenance columns are persisted and populated by every findings producer.
- A6: BOQ deterministic re-runs produce byte-identical finding signatures with
  matching provenance when inputs are unchanged.

## Out of scope

- Golden-label / accuracy scoring (owned by `analytics`, reads via `list_for_org`).
- Per-producer display filters beyond `kind`/`severity` (frontend concern).
