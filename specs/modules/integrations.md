# Integrations — Spec

**Status:** draft
**Requirement refs:** Research Doc §4.I, §10.2, §12.3, §13
**Task refs:** TS-281–TS-287

## Purpose

A pluggable integration layer for construction data sources. The first slice is
upload/ingest-based adapters: each adapter accepts files or structured payloads from a
named source and normalises them into TenderShield primitives (`documents`,
`change_events`, `cost_codes`, `schedule_activities`) without requiring live OAuth
credentials. Live API pulls are gated behind source configuration and degrade
clearly when credentials or rate limits are missing.

## Public interface

### Capabilities published

- `integrations.service_factory` → `IntegrationsService(session)`.
- `integrations.adapters_for_workspace` — list configured sources for a workspace.
- `integrations.import_from_source` — run an import job for a source.

### Capabilities consumed (soft)

| Capability | Use |
|---|---|
| `ingestion.service_factory` | Create `documents` and opportunities from imported files. |
| `change.service_factory` | Create imported change events / RFIs. |
| `outcomes.service_factory` | Push imported cost lines to project economics. |

### Events emitted

- `integrations.import_started`
- `integrations.import_completed`
- `integrations.import_failed`

### API routes (prefix `/api/integrations`)

- `POST /sources` (admin) — create/configure a source.
- `GET /sources` (viewer) — list workspace sources.
- `POST /sources/{id}/import` (estimator) — run an import job for a source.
- `GET /sources/{id}/jobs` (viewer) — list import jobs.
- `GET /sources/{id}/documents` (viewer) — documents created by the source.
- `GET /sources/{id}/events` (viewer) — change events created by the source.
- `POST /schedule/import` (estimator) — import P6 XER / MS Project XML / CSV schedule.
- `GET /schedule/activities` (viewer) — imported schedule activities.

## Data owned

- `integration_sources` — configured source + adapter kind + credentials blob.
- `integration_sync_jobs` — per-import job status, counts, errors.
- `integration_documents` — mapping from source file to `documents` row.
- `integration_events` — mapping from source event to `change_events` row.
- `integration_schedule_activities` — imported schedule activities.
- `integration_cost_lines` — imported ERP cost code / committed cost lines.

All tables are workspace-scoped with RLS.

## Behavior

### Adapter framework (B1–B4, TS-281)

- **B1 — Adapter registry.** `BaseAdapter` declares `name`, `supported_mimetypes`,
  `normalize(payload, workspace_id, opportunity_id, context)`. Concrete adapters
  register in `ADAPTER_REGISTRY`.
- **B2 — Source configuration.** `POST /sources` stores `adapter_kind`, optional
  `opportunity_id`, `config` JSON (credentials are encrypted at rest when a crypto
  capability is available; otherwise stored as a `secrets` object reference).
- **B3 — Conflict handling.** Imports are idempotent by a source-native id
  (`source_native_id`). Duplicate rows update `updated_at` and append a new
  `integration_sync_jobs` record rather than creating duplicates.
- **B4 — Rate limits.** Live API adapters (not implemented in first slice) read
  `rate_limit_calls_per_minute` from `config` and throttle via a simple bucket.

### Document-source adapters (B5–B7, TS-282)

- **B5 — SharePoint / OneDrive.** Accepts a JSON payload of `files` with `filename`,
  `mime_type`, `content_base64`, `folder_path`. Creates `documents` via the
  ingestion module and `integration_documents` mapping rows.
- **B6 — Metadata.** Each file stores `source_path`, `last_modified_at` and a
  `source_native_id` hash (`folder_path/filename`).
- **B7 — Degradation.** If `ingestion` is disabled, the adapter returns a
  `skipped` count and does not crash.

### Construction-platform adapters (B8–B13, TS-283–TS-286)

- **B8 — Procore.** Accepts a payload of `rfis` and `change_events` from a Procore
  export. Each item creates a `change_events` row with `source_adapter=procore` and
  `source_native_id`.
- **B9 — Autodesk Construction Cloud.** Accepts `issues` and `submittals` export.
  Issues with `type=change` become `change_events`.
- **B10 — Oracle Aconex.** Accepts Aconex mail / transmittal export; creates
  `documents` and `change_events` where the subject matches change keywords.
- **B11 — ERP adapter.** Accepts a CSV/JSON cost report with columns
  `cost_code`, `description`, `committed_cost_minor`, `certified_value_minor`,
  `currency`. Creates `integration_cost_lines` linked to an opportunity.
- **B12 — Tally / SAP / Dynamics shortlist.** The ERP adapter is provider-agnostic;
  `adapter_kind` may be `tally`, `sap`, or `dynamics` but the same normalisation
  logic applies.
- **B13 — No live API in first slice.** All adapters ingest exported payloads; live
  OAuth pulls are out of scope until their exit gates are met.

### Schedule import (B14–B16, TS-287)

- **B14 — Supported formats.** `p6_xer` (limited: parse the `TASK` table from a
  XER text file), `ms_project_xml` (parse `Task` nodes), `csv` (columns
  `activity_id`, `name`, `start`, `finish`, `duration_days`).
- **B15 — Activity links.** Imported activities store `opportunity_id`,
  `source_native_id`, `name`, `start_date`, `finish_date`, `duration_days`,
  `predecessors` JSON, and `linked_change_event_ids` (set manually after import).
- **B16 — Contemporaneous programme snapshots.** `POST /schedule/snapshot`
  records a point-in-time copy of activities for a source.

## Acceptance criteria

- A1 (TS-281): Adapter registry exists and boots with the `integrations` module.
- A2 (TS-282): SharePoint/OneDrive upload creates `documents` and mapping rows.
- A3 (TS-283): Procore import creates change events from RFI/change payloads.
- A4 (TS-284): Autodesk import creates issues/submittals as documents or events.
- A5 (TS-285): Aconex import creates documents and change events.
- A6 (TS-286): ERP import creates cost lines from CSV/JSON.
- A7 (TS-287): Schedule import creates activities from XER/XML/CSV.
- A8: All tables are workspace-scoped and have RLS migrations.
- A9: Missing soft dependencies (`ingestion`, `change`) degrade with explicit
  `unavailable` flags.

## Out of scope

- Live OAuth/API polling for any provider.
- Two-way sync and write-back to external systems.
- Real-time webhooks from Procore/Aconex/etc.

## Assumptions

- `assumption:` First-slice integrations are upload/export based because live APIs
  require provider credentials and rate-limit negotiation that are not yet proven.
- `assumption:` The `ingestion` module owns the `documents` and `opportunities`
  tables; `integrations` never imports `ingestion` directly and uses registry
  capabilities.
