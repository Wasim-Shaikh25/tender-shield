# Governance — Spec

**Status:** draft
**Requirement refs:** Doc §11.2 (security baseline), FEATURE_COVERAGE.md §I
**Task refs:** TS-332

## Purpose
Workspace-level data governance controls: data residency region, storage encryption at rest, document retention policy, and legal-hold flags.

## Public interface

- **API routes** (admin only under `/api/auth/workspaces/{workspace_id}/data-governance`):
  - `GET /api/auth/workspaces/{workspace_id}/data-governance` — read current settings.
  - `PUT /api/auth/workspaces/{workspace_id}/data-governance` — update settings.
  - `GET /api/auth/workspaces/{workspace_id}/data-governance/retention-candidates` — list documents older than retention that are not on legal hold.
- **Registry capabilities**:
  - `governance.settings_for_workspace(session, workspace_id)` → dict or None.
  - `governance.retention_candidates(session, workspace_id)` → list[dict].
- **Events emitted**:
  - `governance.settings_changed`
  - `governance.retention_run`

## Data owned

- `workspace_data_governance` table (workspace-scoped, RLS):
  - `workspace_id` PK/FK
  - `data_region` (default from `TS_DATA_RESIDENCY_DEFAULT_REGION`)
  - `retention_days`
  - `archive_after_days`
  - `legal_hold` boolean
  - `encryption_at_rest` ("none" | "sse-s3" | "aws:kms")

## Behavior

- B1. Each workspace has at most one governance row; GET creates a default row if absent.
- B2. Only workspace admins/owners may read or write governance settings.
- B3. `encryption_at_rest` is advisory: S3 uploads use the configured SSE setting when `TS_STORAGE_TYPE=s3`; local storage does not encrypt files (dev/test only).
- B4. Retention candidates are returned from the ingestion `documents` table via the registry capability `ingestion.documents_for_retention` (soft dependency). If ingestion is not available, the list is empty.
- B5. Legal hold overrides retention: documents whose opportunity or workspace is on legal hold are excluded from candidate reports.
- B6. Updates are audited with `audit_log.log`.

## Acceptance criteria

- A1. Admin can read and write governance settings through the settings UI.
- A2. `S3Storage.write` passes `ServerSideEncryption` and `SSEKMSKeyId` when configured.
- A3. Retention candidates endpoint returns documents older than `retention_days` and omits legal-held workspaces.
- A4. Migrations and RLS are present.

## Out of scope

- Actual KMS key lifecycle management.
- Automatic deletion/archival job (report is manual).

## Assumptions

- `ingestion.documents_for_retention` capability is provided by the ingestion module.
