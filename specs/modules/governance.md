# Governance — Spec

**Status:** implemented (TS-332 config API + TS-340 retention job)  
**Requirement refs:** Doc §11.2 (security baseline), FEATURE_COVERAGE.md §I  
**Task refs:** TS-332, TS-340

## Purpose
Workspace-level data governance controls: data residency region, storage encryption at rest, document retention policy, legal-hold flags, and scheduled retention execution.

## Public interface

- **API routes** (admin only under `/api/governance/workspaces/{workspace_id}/data-governance`):
  - `GET /api/governance/workspaces/{workspace_id}/data-governance` — read current settings.
  - `PUT /api/governance/workspaces/{workspace_id}/data-governance` — update settings.
  - `GET /api/governance/workspaces/{workspace_id}/data-governance/retention-candidates` — list documents older than retention that are not on legal hold.
- **Registry capabilities**:
  - `governance.settings_for_workspace(session, workspace_id)` → dict or None.
  - `governance.service_factory(session)` → `GovernanceService`.
  - `governance.retention_job()` → async callable that opens a DB session and runs `GovernanceService.run_retention_job`.
- **Events emitted**:
  - `governance.settings_changed`
  - `governance.document_archived` (audited)
  - `governance.document_soft_deleted` (audited)
  - `governance.document_hard_deleted` (audited)

## Data owned

- `workspace_data_governance` table (workspace-scoped, RLS):
  - `workspace_id` PK/FK
  - `data_region` (default from `TS_DATA_RESIDENCY_DEFAULT_REGION`)
  - `retention_days`
  - `archive_after_days`
  - `legal_hold` boolean
  - `encryption_at_rest` ("none" | "sse-s3" | "aws:kms")
- `documents` (ingestion-owned, lifecycle fields consumed by governance):
  - `archived_at`
  - `deleted_at`

## Behavior

- B1. Each workspace has at most one governance row; GET creates a default row if absent.
- B2. Only workspace admins/owners may read or write governance settings.
- B3. `encryption_at_rest` is advisory: S3 uploads use the configured SSE setting when `TS_STORAGE_TYPE=s3`; local storage does not encrypt files (dev/test only).
- B4. Retention candidates are returned from the ingestion `documents` table via the registry capability `ingestion.documents_for_retention` (soft dependency). If ingestion is not available, the list is empty.
- B5. Legal hold overrides retention: workspaces with `legal_hold=true` are skipped entirely.
- B6. Updates are audited with `audit_log.log`.
- B7. When `TS_RETENTION_JOB_ENABLED=true`, `governance/module.py` schedules `governance.retention_job` to run every `TS_RETENTION_JOB_INTERVAL_HOURS` (default 24).
- B8. Retention job lifecycle per workspace:
  1. Archive pass: documents older than `archive_after_days` (when set and < `retention_days`) are marked `archived_at = now` via `ingestion.retention_apply(..., "archive")`.
  2. Soft-delete pass: documents older than `retention_days` are marked `deleted_at = now` via `ingestion.retention_apply(..., "soft_delete")`.
  3. Hard-delete pass: on a subsequent run, documents whose `deleted_at` is older than `TS_RETENTION_GRACE_DAYS` are removed from the `documents` table and the storage blob is deleted via `StorageBackend.delete`.
- B9. Every lifecycle action appends an `audit_log` row via `review.service_factory`.

## Acceptance criteria

- A1. Admin can read and write governance settings through the settings UI.
- A2. `S3Storage.write` passes `ServerSideEncryption` and `SSEKMSKeyId` when configured.
- A3. Retention candidates endpoint returns documents older than `retention_days` and omits legal-held workspaces.
- A4. With `TS_RETENTION_JOB_ENABLED=true`, a document older than `retention_days` is soft-deleted and, after the grace period, hard-deleted along with its storage object.
- A5. Legal hold prevents both archival and deletion.
- A6. Migrations and RLS are present.

## Out of scope

- Actual KMS key lifecycle management.

## Assumptions

- `ingestion.documents_for_retention` and `ingestion.retention_apply` capabilities are provided by the ingestion module.
- `review.service_factory` provides `ReviewService.audit` for retention audit events.
