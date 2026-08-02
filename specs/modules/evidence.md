# Evidence — Spec

**Status:** implemented — chain of custody, event attachment, completeness scoring
**Requirement refs:** Research Doc §2.1, §4.G, §6.3; Build Doc §6.5
**Task refs:** TS-254, TS-255, TS-270

## Purpose

Preserve contemporaneous records for change events with an auditable chain of custody.
Evidence-completeness scoring surfaces missing record types before notice issue or claim
preparation (Phase 19 builds on this foundation).

## Public interface

### Capabilities published

- `evidence.service_factory` → `EvidenceService(session)`.
- `evidence.completeness_for_event` — deterministic completeness payload for a change event
  (read-only helper for `change` event detail).

### Capabilities consumed (soft)

| Capability | Use |
|---|---|
| `ingestion.service_factory` | Validate opportunity exists |

### Events emitted

| Event | Payload (minimum) |
|---|---|
| `evidence.record_attached` | `workspace_id`, `event_id`, `record_id`, `record_type` |

### API routes (prefix `/api/evidence`)

- `POST /events/{event_id}/records` (estimator) — attach evidence with chain-of-custody seed.
- `GET  /events/{event_id}/records` (viewer) — list records for an event.
- `GET  /events/{event_id}/completeness` (viewer) — score + missing types.
- `GET  /records/{record_id}` (viewer) — record detail with custody chain.

`change` also exposes `POST /api/change/events/{event_id}/evidence` delegating here when the
module is enabled.

## Data owned

### `evidence_records`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID | RLS |
| `opportunity_id` | UUID | indexed; logical ref |
| `change_event_id` | UUID | indexed; logical ref to change event (no FK) |
| `record_type` | string | `site_instruction` \| `photograph` \| `geotagged_photo` \| `measurement` \| `daily_report` \| `meeting_minutes` \| `correspondence` \| `drawing_revision` \| `labour` \| `plant` \| `material` \| `daywork` \| `other` |
| `title` | string | short label |
| `description` | text nullable | operator notes |
| `captured_at` | timestamptz | when the record was created in the field |
| `document_id` | UUID nullable | optional ingestion document ref |
| `custody_chain` | JSON | append-only `[{user_id, action, at, note?}]` |
| `record_metadata` | JSON | geolocation, offline-sync hints, quality prompts |
| `created_by` | UUID | |
| `created_at` | timestamptz | |

## Behavior

- **B1 — Chain of custody.** Every record starts with a `created` custody entry. Viewing appends
  `viewed` only when explicitly requested via service audit (Phase 18: create-only chain).
- **B2 — Event link.** Records attach to a single `change_event_id`; cross-module by UUID only.
- **B3 — Completeness (deterministic).** Required record types derive from event `reason` via a
  fixed map (never LLM). Score = `len(present ∩ required) / len(required)` as a 0–100 integer.
- **B4 — Missing list.** Returns human-readable missing type labels for UI checklists.
- **B5 — Site evidence (TS-270).** `geotagged_photo` carries geolocation in `record_metadata`. `labour`, `plant`, `material`, and `daywork` record types are accepted and count toward claim-checklist items.
- **B6 — Org isolation.** All queries filter by `workspace_id`.

## Acceptance criteria

- A1 (TS-254): Attached record persists with `created` custody entry and creator id.
- A2 (TS-254): `GET /records/{id}` returns full custody chain.
- A3 (TS-255): Completeness for `drawing_revision` lists missing types when only photograph present.
- A4 (TS-255): Score is 100 when all required types are present.
- A5 (TS-270): `geotagged_photo`, `labour`, `plant`, `material`, and `daywork` records are accepted and returned with `metadata`.

## Out of scope

- Native mobile apps and offline-first sync client (Phase 21).
- Claims valuation workspace (Phase 19).
- File blob storage beyond `document_id` reference to ingestion.

## Assumptions

- `assumption:` Required-type map is a static Phase 18 table until org-custom checklists land in
  Phase 19 (TS-260).
