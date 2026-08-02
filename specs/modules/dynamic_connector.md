# Generic dynamic REST connector — Spec

**Status:** draft
**Requirement refs:** User request (post-Phase 22); `docs/REMAINING_GAPS_ROADMAP.md` TS-305/TS-333
**Task refs:** TS-334

## Purpose
Allow non-technical users to configure a live REST integration (ERP, Oracle, custom sandbox, etc.) from the UI without writing code. The connector spec is stored in the DB and interpreted by a generic `DynamicRestConnector`.

## Public interface

- **API routes** under `/api/integrations/dynamic` (admin/estimator):
  - `GET /dynamic-connectors` — list workspace connector specs (secrets masked).
  - `GET /dynamic-connectors/{id}` — get one spec.
  - `POST /dynamic-connectors` — create a spec.
  - `PUT /dynamic-connectors/{id}` — update a spec.
  - `DELETE /dynamic-connectors/{id}` — delete a spec.
  - `POST /dynamic-connectors/{id}/test` — test connection to `base_url` with auth/headers; does not persist fetched data.
  - `POST /dynamic-connectors/{id}/poll` — run a fetch and import normalized records.
- **Registry capabilities**:
  - `integrations.dynamic_connector_for_source(session, source_id)` → spec dict.
  - `integrations.dynamic_poll(session, source_id, user_id)` → import result.

## Data owned

- `dynamic_connector_configs` table (workspace-scoped, RLS):
  - `id`, `workspace_id`, `name`, `base_url`
  - `auth_type` ("none" | "bearer" | "basic" | "api_key")
  - `auth_config` JSON (token, username/password, api_key header/name)
  - `headers` JSON
  - `pagination` JSON (`type`: "none" | "offset" | "cursor" | "link_header"; params)
  - `mappings` JSON (`document`, `event`, `cost_line`, `activity` mapping rules)
  - `enabled` boolean
  - `last_tested_at`, `last_test_status`
  - `created_at`, `updated_at`

## Behavior

- B1. Admins/estimators may CRUD dynamic connector specs in their workspace.
- B2. `auth_config` is stored as JSON; secret values are never returned by the list/get endpoints (return `***` placeholders).
- B3. Test connection performs a `GET` to `base_url` with headers and auth; returns HTTP status, latency, and a small response preview (truncated, no persistence).
- B4. Poll uses `DynamicRestConnector(spec).fetch()` and passes the result through the existing `_persist` path.
- B5. Mappings are JSONPath-like dotted paths (e.g. `data.items.*.costCode`) or simple key names; the connector converts API responses into the standard `documents/events/cost_lines/activities` shape.
- B6. If `base_url` is a sandbox/localhost URL, the test still runs; the user decides whether to trust it.
- B7. Dynamic connector specs can be referenced by an `IntegrationSource` with `adapter_kind="dynamic"` and `config.dynamic_connector_id`.

## Acceptance criteria

- A1. User can create a connector from the UI with base URL, auth, headers, pagination, and mappings.
- A2. Test Connection button returns success/failure without persisting data.
- A3. Poll endpoint imports at least cost lines from a sample Oracle/ERP JSON response using the mapping.
- A4. Secrets are masked in GET responses.
- A5. RLS and workspace isolation are enforced.

## Out of scope

- Automatic Oracle API documentation parsing by AI in this iteration.
- Two-way sync/write-back to ERP.
- OAuth-based dynamic connectors (use the connector registry for OAuth-specific providers).

## Assumptions

- The user provides the Oracle/ERP sandbox URL and sample JSON structure.
- `httpx` is available in the backend environment.
