# Findings — Spec

**Status:** implemented
**Requirement refs:** Doc §3.2, §6.3, §6.4, §11.4
**Task refs:** TS-017, TS-018, TS-049, TS-054, TS-055, TS-056

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
- `amount_exposure` (Numeric 16,2)
- `review_status` (`proposed` | `accepted` | `edited` | `rejected` |
  `false_positive` | `needs_clarification`)
- `review_note`, `review_reason`, `reviewed_by`
- `explanation` (JSON, for `risk_clause` explainability)

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

## Acceptance criteria

- A1: `replace_for_producer` replaces only the calling producer's rows for an
  opportunity, leaving other producers intact.
- A2: A finding written by one producer and reviewed by the review module keeps
  its review state after a re-run of a different producer.
- A3: `GET /api/findings/opportunities/{id}` returns only findings for the
  caller's org.

## Out of scope

- Golden-label / accuracy scoring (owned by `analytics`, reads via `list_for_org`).
- Per-producer display filters beyond `kind`/`severity` (frontend concern).
