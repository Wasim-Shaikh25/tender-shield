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
| `findings` | `findings`** (shared table; owns model + migration + store) |
| `boq` | `boq_items` |
| `drafting` | `artifacts` |
| `review` | `audit_log`, `outcomes` (updates review columns on `findings`) |
| `billing` | `usage_events`, `payment_log`, payment intents/webhook dedup |

*`opportunities` is the shared aggregate root; owned by `ingestion`, referenced by
ID from every other module.

**`findings` is a shared table with one owner: the `findings` module owns the
SQLAlchemy model, migration, and `FindingStore`. Producers (`risk`, `boq`) write
via the `findings.store_factory` capability, scoped by a `producer` column so a
re-run of one producer never disturbs another's rows. The row shape mirrors the
core `Finding` contract (`app.core.contracts.findings`). This keeps the table
pluggable — no module imports another's models.

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

## Foundation vs. per-module models (TS-013)

The DB **foundation** is core infrastructure (`app/core/db.py`): the declarative
`Base`, `OrgScopedMixin` (adds `org_id` and self-registers the table in
`ORG_SCOPED_TABLES` for RLS generation), `TimestampMixin`, `rls_statements()`,
`bind_org_context()`, and the engine/session-factory builders. `create_app`
publishes `db.engine` and `db.sessionmaker` as registry capabilities so modules
consume the session factory without importing a DB module.

The **table models themselves are owned by their modules** (table above) and
land with each module's task — a module defines them in
`app/modules/<name>/models.py`, which `migrations/env.py` auto-discovers so
`Base.metadata` fills in as modules are enabled. This keeps the schema
pluggable: no orphan models for modules that don't exist yet.

## Acceptance criteria

- A1 (foundation): `OrgScopedMixin` registers tables for RLS; `rls_statements`
  emits the Doc §3.2 policy; SQLite session roundtrip works; `bind_org_context`
  is a safe no-op off PostgreSQL. `alembic upgrade head`/`downgrade base` clean.
- A2 (per module): each module's migration creates its Doc §3.2 tables; up/down
  clean; RLS denies cross-org reads in a two-org PostgreSQL integration test.

## Out of scope

Phase-3 tables (variations/notices), admin-console tables beyond `payment_log`.
