# Public API + E-signature — Spec

**Status:** implemented (TS-339 validation added)
**Requirement refs:** Research Doc §4.I
**Task refs:** TS-292

## Purpose

Provide a scoped public API for external systems (e-signature providers, ERPs,
client portals) to read issue status and request signatures on notices without
using the interactive auth flow.

## Public interface

- **Capability published:** `public_api.service_factory`.
- **Capabilities consumed (soft):**
  - `change.service_factory` — read notice/change events.
  - `ingestion.service_factory` — read opportunity metadata.

### Auth

- `public_api_keys` table holds workspace-scoped keys: `key_hash`, `scopes`,
  `name`, `revoked_at`.
- Middleware looks for `Authorization: ApiKey <key>` header and sets
  `request.state.public_api_workspace_id` / scopes.

### API routes (prefix `/api/public`)

- `POST /keys` — create an API key (admin only; returns plaintext once).
- `GET /keys` — list keys (hashes hidden).
- `GET /notices/{notice_id}/status` — get signature/notice status.
- `POST /notices/{notice_id}/request-signature` — queue a signature request.
- `POST /signatures/callback` — provider webhook callback.

## Data owned

- `public_api_keys` — workspace-scoped keys.
- `public_signature_requests` — signature request records and status.

## Behavior

- Keys are 32-byte random tokens hashed with SHA-256; only the plaintext is shown
  on creation.
- `POST /notices/{notice_id}/request-signature` body carries `opportunity_id`,
  `recipient_email`, optional `change_event_id`, and `provider` (e.g., `docusign_stub`).
- `notice_id` and `change_event_id` are validated as workspace/opportunity-scoped
  `ChangeEvent` rows (a `notice_id` additionally requires a non-null `notice_type`).
- Webhook callback updates `status` to `signed` / `declined` / `viewed`.

## Acceptance criteria

- A1: API key create/list with `read` / `write` scopes.
- A2: Signature request creates a `public_signature_requests` row.
- A3: Webhook callback updates the request status.
- A4: Migration and RLS present.
- A5: Invalid `notice_id` or `change_event_id` (including cross-workspace IDs or
  non-notice events for `notice_id`) returns `404 no_such_notice` /
  `404 no_such_change_event`.

## Out of scope

- Real DocuSign/Adobe OAuth integration (provider abstraction stubbed).
- Email sending from this module.
