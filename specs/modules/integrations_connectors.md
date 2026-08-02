# Live CDE/ERP Connector Sync — Spec

**Status:** draft
**Requirement refs:** Doc §4.I, FEATURE_COVERAGE.md §I
**Task refs:** TS-333

## Purpose
Enable OAuth-based, polling or webhook-driven synchronization of project data from external construction and ERP systems (Procore, Autodesk Construction Cloud, Aconex, SharePoint/OneDrive, generic ERP) into TenderShield's integration source model.

## Public interface

- **API routes** under `/api/integrations`:
  - `GET /connectors` — list supported connector kinds and status.
  - `POST /sources/{source_id}/oauth` — start OAuth flow (returns `authorization_url` and `state`).
  - `POST /connectors/{connector_kind}/callback` — OAuth callback (exchanges code, stores token in `source.config`).
  - `POST /sources/{source_id}/poll` — trigger a poll for new/updated records.
  - `POST /sources/{source_id}/webhook` — public webhook receiver for push events.
- **Registry capabilities**:
  - `integrations.connector_for_kind(session, kind)` → connector instance or None.
  - `integrations.poll_source(session, source_id, user_id)` → sync result dict.
- **Events emitted**:
  - `integrations.oauth_completed`
  - `integrations.poll_completed`
  - `integrations.webhook_received`

## Data owned

- `integration_sources` table (extended to store OAuth tokens/cursors in `config` JSON).
- `integration_sync_jobs` table records each poll/webhook run.
- Connector payloads are normalized to existing `documents`, `events`, `cost_lines`, `activities` shapes before persistence.

## Behavior

- B1. Each `IntegrationSource.adapter_kind` may be a static adapter (e.g. `json_payload`) or a live connector kind (e.g. `procore`, `autodesk`, `aconex`, `sharepoint`, `erp`).
- B2. Live connectors implement `BaseConnector`: `authorization_url(state)`, `exchange_code(code, state)`, `fetch(source)` and `normalize(records)`.
- B3. Poll and webhook flows are gated by `TS_LIVE_CONNECTOR_POLLING_ENABLED`; without the flag, endpoints return `503` or mock-empty results in non-production.
- B4. OAuth secrets are stored only inside `source.config`; the backend never logs tokens.
- B5. Records from live connectors are persisted through the same `_persist` path as static payloads.
- B6. Unsupported connector kinds return `unknown_adapter`.

## Acceptance criteria

- A1. `GET /connectors` returns the supported list with `auth_required` flag.
- A2. OAuth start/callback endpoints exist and update `source.config` with token placeholder.
- A3. Poll endpoint creates a sync job and returns record counts.
- A4. Webhook endpoint accepts arbitrary JSON and triggers normalization.
- A5. Connector scaffolding is present for Procore, Autodesk, Aconex, SharePoint, and ERP.

## Out of scope

- Real HTTP calls to third-party APIs (credential-less stubs; full integrations require staging keys).
- OAuth app registration UI.

## Assumptions

- Third-party credentials and redirect URLs are provided as environment variables per connector.
- Live connector polling is disabled by default.
