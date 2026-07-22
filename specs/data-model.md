# Canonical Data Model — Spec

**Status:** agreed
**Requirement refs:** Doc §3.2
**Task refs:** TS-013

## Purpose

Single PostgreSQL 16 (+pgvector) schema — the "baseline graph". The authoritative
DDL is in Doc §3.2; this spec records ownership and the rules around it.

## Table ownership (module → tables)

| Module | Tables |
|---|---|
| `auth` | `users`, `orgs`, `org_members`, refresh-token tables |
| `ingestion` | `opportunities`*, `documents`, `clauses`, `deadlines`, `doc_chunks` |
| `risk` | `findings` (kind=`risk_clause`, `missing_doc`) |
| `boq` | `boq_items`, `findings` (kind=`boq_defect`, `scope_gap`) |
| `drafting` | `artifacts` |
| `review` | `audit_log`, review fields on `findings`/`artifacts`, `outcomes` |
| `billing` | `usage_events`, `payment_log`, payment intents/webhook dedup |

*`opportunities` is the shared aggregate root; owned by `ingestion`, referenced by
ID from every other module. `findings` is a shared-shape table defined in core
contracts; writer modules own their `kind` values.

## Behavior

- **B1 (RLS non-negotiable):** every org-scoped table has
  `POLICY org_isolation USING (org_id = current_setting('app.org_id')::uuid)`;
  the request layer executes `SET LOCAL app.org_id` per transaction (Doc §3.2, §5).
- **B2 (provenance columns):** extraction-derived rows carry `source_page` and
  verbatim `source_quote` (≤200 chars).
- **B3 (append-only):** `audit_log` and `payment_log` have no UPDATE/DELETE grants.
- **B4 (money):** amounts in minor units (`BIGINT`) for payments; `NUMERIC` for BOQ.
- **B5 (migrations):** Alembic; every migration reversible; CI runs up/down on a
  scratch DB (Doc §11.1).

## Acceptance criteria

- A1: migration suite creates all Doc §3.2 tables; up/down clean.
- A2: RLS denies cross-org reads in an integration test with two orgs.

## Out of scope

Phase-3 tables (variations/notices), admin-console tables beyond `payment_log`.
