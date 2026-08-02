# Change & notice control — Spec

**Status:** agreed — TS-243 **done**; TS-244 scaffold **implemented**
**Requirement refs:** Research Doc §4.F, §5.3(15–18); Build Doc §6.2–6.5, §11.3–11.4;
`docs/TenderShield_Roadmap_Stage1_to_5.md` §4 (Stage 3)
**Task refs:** TS-243, TS-244, TS-245, TS-246, TS-247, TS-248, TS-249, TS-250, TS-251,
TS-252, TS-253, TS-254, TS-255, TS-256

## Purpose

Phase 18 converts TenderShield from transactional tender review into **per-project recurring
revenue** (Research Doc §10.1). The `change` module is the Stage 3 engine: it detects candidate
variations by diffing new project signals against the **locked baseline** (Phase 17), triages them
in a potential-variation inbox, records **site confirmation**, computes **deterministic notice
deadlines** from the Phase-17 notice-rule register, and hands verified facts to notice drafting
(Phase 18) and claims (Phase 19).

The evidence chain must stay unbroken:

```
tender clause → baseline obligation → change event → notice → evidence → claim → outcome
```

Without Phase 17 controls there is nothing to diff against; without Phase 18 there is no recurring
subscription or switching cost.

## Public interface

### Capabilities published

- `change.service_factory` → `ChangeService(session)`.
- `change.events_for_opportunity` — list change events for an opportunity (read-only helper).
- `change.notice_deadline_for_event` — deterministic deadline payload for a confirmed event
  (TS-251; consumes baseline notice register via registry, never imports `baseline`).

### Capabilities consumed (soft — registry only)

| Capability | Use |
|---|---|
| `baseline.service_factory` | Require sealed baseline before event creation; read notice register |
| `baseline.sealed_opportunity_count` | Adoption / gate checks (analytics) |
| `ingestion.service_factory` | Opportunity metadata, documents, confirmed deadlines |
| `findings.store_factory` | BOQ rows for impact linking (TS-249) |
| `review.service_factory` | Audit log for human actions |
| `auth.approval_matrix` | Gate notice issue and high-value confirmations (TS-239) |
| `notifications.sender` | Deadline countdown alerts (TS-252) |
| `drafting.service_factory` | Notice draft generation (TS-253) |
| `export.service_factory` | Pack exports where needed |

### Events emitted

| Event | Payload (minimum) |
|---|---|
| `change.event_created` | `workspace_id`, `opportunity_id`, `event_id`, `status`, `source_kind` |
| `change.event_triaged` | `workspace_id`, `event_id`, `prior_status`, `new_status` |
| `change.event_confirmed` | `workspace_id`, `event_id`, `outcome`, `confirmed_by` |
| `change.notice_deadline_computed` | `workspace_id`, `event_id`, `notice_deadline`, `notice_type` |
| `change.notice_draft_requested` | `workspace_id`, `event_id` — consumed by `drafting` (TS-253) |
| `change.email_received` | `workspace_id`, `opportunity_id`, `message_id`, `inbound_email_id` |

### Events consumed

| Event | Action |
|---|---|
| `baseline.sealed` | Cache latest `baseline_id` for the opportunity (in-memory / service state only;
  persisted on events as `baseline_id` UUID, no FK) |
| `ingestion.document_uploaded` | Queue baseline diff when document kind is revisable text
  (`spec`, `drawing_log`, `instruction`) — TS-245 |

### API routes (prefix `/api/change`)

#### Implemented (TS-244 scaffold)

- `GET  /opportunities/{id}/events` (viewer) — list change events for an opportunity.
- `POST /opportunities/{id}/events` (estimator) — create a **manual** candidate event with at
  least one source citation.
- `GET  /events/{event_id}` (viewer) — event detail with sources and latest confirmation.
- `POST /events/{event_id}/confirmations` (estimator) — record site confirmation outcome.

#### Implemented (TS-245, TS-246)

- `POST /opportunities/{id}/diff` (estimator) — run baseline clause diff on document text or
  `document_id`; emits cited candidate events with 24h dedup.
- `POST /opportunities/{id}/signals` (estimator) — ingest RFI / site instruction / minutes /
  daily-report / email text with deterministic classification and provenance quote.

#### Implemented (TS-248, TS-249, TS-250)

- `GET  /opportunities/{id}/inbox` (viewer) — potential-variation triage queue (`candidate` +
  `triaged`), sorted by confidence then recency.
- `PUT  /events/{event_id}/triage` (estimator) — `triaged` or `rejected` transitions.
- `PUT  /events/{event_id}/impacts` (estimator) — link BOQ rows, cost codes, findings,
  subcontract refs; returns exposure summary in minor units.
- `GET  /events/{event_id}/confirmations` (viewer) — confirmation history.
- Site confirmation outcomes map to event status (`changed`→`confirmed`, `clarification_only`→
  `triaged`, `client_risk`→`closed`, etc.).

#### Implemented (TS-251, TS-252, TS-253)

- `GET  /events/{event_id}/notice-deadline` (viewer) — deterministic deadline + required content
  from baseline notice register; persists on event (**TS-251**).
- `POST /events/{event_id}/notice-draft` (estimator) — variation notice draft via `drafting`
  with verified facts only and validators; `status=draft` until human approval (**TS-253**).
- Registry: `change.notice_deadline_for_event`, `change.process_notice_alerts` (consumed by
  `notifications` scheduler for 7/3/1/0 deduped alerts — **TS-252**).

#### Implemented (TS-254, TS-255)

- `POST /events/{event_id}/evidence` (estimator) — attach evidence via `evidence` module.
- Event detail includes `evidence_completeness` when `evidence` is enabled.

#### Implemented (TS-247, TS-327)

- `POST /opportunities/{id}/inbox/email` (admin) — register per-project forward address.
- `GET  /opportunities/{id}/inbox/email` (admin) — retrieve active forward address.
- `POST /webhooks/inbound-email` — HMAC-verified inbound provider callback; stores raw
  message append-only and emits email signal candidate via B10–B11.
- `POST /opportunities/{id}/signals/poll` (estimator) — poll configured IMAP/email inbox for new
  signal messages and ingest them behind `TS_CHANGE_SIGNAL_POLLING_ENABLED`.

#### Implemented (TS-328)

- `POST /opportunities/{id}/delay-analysis` (estimator) — for a `delay_event_id` and `delay_days`,
  return impacted schedule activities and successor path using imported `integrations.schedule`
  data. No auto entitlement is computed.

## Data owned

All tables are workspace-scoped (RLS). Other modules reference change data by UUID + events only —
**no foreign keys into `baseline`, `findings`, or `ingestion` tables**.

### `change_events`

Core variation / change record.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID | RLS |
| `opportunity_id` | UUID | indexed; logical ref to ingestion opportunity |
| `baseline_id` | UUID nullable | sealed baseline this event is measured against |
| `status` | string | `candidate` \| `triaged` \| `confirmed` \| `rejected` \| `closed` |
| `title` | string | human-readable summary |
| `reason` | string | `scope_change` \| `instruction` \| `drawing_revision` \| `spec_revision` \| `correspondence` \| `other` |
| `affected_scope` | text nullable | free-text scope description |
| `confidence_band` | string | `high` \| `medium` \| `low` |
| `notice_type` | string nullable | matches baseline notice register `category` |
| `trigger_date` | date nullable | user-supplied or extracted event date for deadline engine |
| `notice_deadline` | date nullable | **computed** by deterministic engine (TS-251); never LLM |
| `notice_deadline_detail` | JSON | engine output: `deadline_unknown`, `trigger_milestone_kind`, etc. |
| `impact_links` | JSON | TS-249: `{boq_src_rows, cost_code_ids, subcontract_refs}` |
| `created_by` | UUID nullable | |
| `created_at`, `updated_at` | timestamptz | |

### `change_sources`

Provenance for every fact shown to users — **no uncited claims** (Build Doc §6.5).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID | RLS |
| `opportunity_id` | UUID | indexed |
| `change_event_id` | UUID FK → `change_events.id` CASCADE | |
| `source_kind` | string | `manual` \| `baseline_diff` \| `rfi` \| `site_instruction` \| `email` \| `meeting_minutes` \| `daily_report` \| `drawing_revision` \| `spec_revision` |
| `document_id` | UUID nullable | ingestion document ref (no FK) |
| `source_page` | int nullable | |
| `source_quote` | string ≤200 | verbatim excerpt; quote-verified before display |
| `external_ref` | string nullable | email Message-ID, RFI number, etc. |
| `text_preview` | string nullable | sanitised excerpt for UI |
| `sha256` | string nullable | content hash for dedup |
| `received_at` | timestamptz nullable | |
| `created_at` | timestamptz | |

### `change_confirmations`

Site confirmation workflow (TS-250). Append-only history — latest row wins for display.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID | RLS |
| `opportunity_id` | UUID | indexed |
| `change_event_id` | UUID FK → `change_events.id` CASCADE | |
| `outcome` | string | `changed` \| `not_changed` \| `clarification_only` \| `contractor_risk` \| `client_risk` \| `unknown` |
| `confirmed_by` | UUID | user id |
| `confirmed_at` | timestamptz | server default now |
| `note` | string nullable | |
| `evidence_ids` | JSON | list of evidence UUIDs (Phase 19 module; no FK) |

### `change_inbox_addresses` (TS-247)

Per-opportunity forward-to-inbox token and display address.

### `change_inbound_emails` (TS-247)

Append-only raw inbound messages (`message_id` unique per workspace).

## Behavior

### Event lifecycle (B1–B6)

- **B1 — Baseline required.** Creating or auto-emitting a change event requires a sealed baseline
  for the opportunity (`baseline.service_factory.latest`). Without a baseline the API returns
  `no_baseline` (404). The module boots with `baseline` disabled but returns empty lists / 404 on
  mutations.
- **B2 — Candidate creation.** Auto-detectors (diff, signal ingestion) create rows with
  `status=candidate` and `confidence_band` set by deterministic rules (e.g. verbatim clause match =
  `high`, keyword-only = `low`). Manual creation requires `title`, `reason`, and ≥1 `change_source`
  with `source_quote` + `source_page` or `document_id`.
- **B3 — Triage inbox (TS-248).** `GET /inbox` returns `candidate` and `triaged` events sorted by
  `confidence_band` then `created_at`. Triage transitions: `candidate → triaged | rejected`,
  `triaged → confirmed | rejected`. Rejected events are retained for audit.
- **B4 — Site confirmation (TS-250).** `POST .../confirmations` appends a confirmation row and, when
  `outcome=changed`, sets event `status=confirmed`. Other outcomes may set `closed` or leave
  `triaged` per operator choice. Every confirmation records `confirmed_by` + timestamp in audit log.
- **B5 — Provenance.** Every user-visible field on an event must trace to a `change_sources` row.
  Display layer runs quote verification against the cited document text (reuse ingestion text
  extraction capability). Failed verification hides the quote and flags `quote_unverified`.
- **B6 — Org isolation.** All queries filter by `workspace_id` from the authenticated principal.

### Baseline diff engine (B7–B9, TS-245)

- **B7 — Text revisions only (Phase 18).** Compare new document text against the sealed baseline
  snapshot clauses and accepted findings. Drawing computer-vision diff is **out of scope** (Build
  Doc Phase 3 note).
- **B8 — Deterministic diff.** Clause segmentation uses `ingestion.segment_clauses` (same registry
  pattern as award compare). Added/changed clauses emit `change_sources` with verbatim quotes.
  Numeric BOQ deltas reuse `baseline.compare_award` finding-diff shape where applicable.
- **B9 — Dedup.** Same `sha256` + `source_kind` + `opportunity_id` within 24h does not create a
  duplicate event; new sources attach to the existing event.

### Signal ingestion (B10–B12, TS-246–TS-247, TS-327)

- **B10 — Source types.** RFIs, site instructions, meeting minutes, daily reports and emails accepted
  as pasted text, uploaded files, or `POST /signals` payloads.
- **B11 — Classification.** Deterministic keyword rules produce `reason`, `notice_type`, and
  confidence; final stored values require a matching `source_quote` span in the text.
- **B12 — Email adapter (TS-247).** Per-opportunity forward address stores raw messages; parsing
  reuses B10–B11. Inbound webhook validates signature; body stored append-only.
- **B12a — Live signal polling (TS-327).** `POST /opportunities/{id}/signals/poll` checks configured
  IMAP/polling adapters for new messages and processes each as an inbound email. Polling is behind
  `TS_CHANGE_SIGNAL_POLLING_ENABLED` and requires configured `notifications.email_inbox` credentials.

### Delay-event critical-path (B13a, TS-328)

- **B13a — Delay analysis.** `POST /opportunities/{id}/delay-analysis` accepts a change `event_id`
  and `delay_days`. It reads schedule activities imported via the `integrations.schedule` adapter
  and returns impacted activities whose start/finish window overlaps the delay window, plus a
  path of successor tasks based on `predecessors`. No auto entitlement is computed.

### Impact linking (B13, TS-249)

- **B13 — Links are IDs only.** `impact_links` JSON holds `cost_code_id`, `finding_id`, `boq_src_row`
  strings resolved via registry capabilities (`baseline.cost_codes_for_opportunity`,
  `findings.store_factory`). Totals and valuations use **minor units**; arithmetic is deterministic
  code, never LLM.

### Notice-deadline engine (B14–B16, TS-251)

- **B14 — Register input.** Load notice rules from `baseline.service_factory.notice_register`
  (enriched Phase-17 register with contacts and deadline arithmetic).
- **B15 — Deterministic formula.** For a confirmed event with `notice_type` and `trigger_date`:
  - `event` trigger: `notice_deadline = trigger_date + deadline_days` (calendar days; same as
    Phase 17 `notice_register.compute_deadline` baseline).
  - `milestone` trigger: resolve milestone date from ingestion confirmed deadlines, then add
    `deadline_days`.
  - Never call an LLM for dates or durations.
- **B16 — Required content.** Copy `required_content` checklist and correspondence block from the
  matching register rule and `bl_notice_contacts` (via baseline API). Store snapshot on the event
  in `notice_deadline_detail`.

### Alerts & drafting (B17–B18, TS-252–TS-253)

- **B17 — Countdown alerts.** Publish `change.notice_deadline_computed`; scheduler (extends
  `notifications`) sends deduped alerts at 7/3/1/0 days before `notice_deadline` per event.
- **B18 — Notice drafting.** `POST .../notice-draft` passes **verified facts only** to
  `drafting.service_factory` with three validators (no invented quotes, no uncited clauses, no
  invented numbers). Human approval in `review` workbench is mandatory before issue.

### Evidence (B19–B20, TS-254–TS-255) — implemented

- **B19 — Delegation.** Evidence attachments live in the `evidence` module.
  `POST /events/{id}/evidence` delegates to `evidence.service_factory.attach`.
- **B20 — Completeness score.** `evidence.completeness_for_event` returns score and missing
  types; surfaced on event detail when the module is present.

### Billing (B21, TS-256) — implemented

- **B21 — Per-project lane.** `billing.is_project_active` gates creation of the third active
  change event per opportunity (`billing_required` / 402). Activation via
  `POST /api/billing/projects/{id}/checkout` with webhook-only truth.

## Response shapes (illustrative)

```jsonc
// GET /api/change/opportunities/{id}/events
{
  "events": [
    {
      "id": "…",
      "status": "candidate",
      "title": "Revised foundation detail — pile depth",
      "reason": "drawing_revision",
      "confidence_band": "high",
      "notice_type": "variation",
      "notice_deadline": null,
      "sources": [
        {
          "source_kind": "baseline_diff",
          "source_page": 12,
          "source_quote": "pile depth increased from 12m to 15m"
        }
      ],
      "latest_confirmation": null
    }
  ]
}
```

```jsonc
// GET /api/change/events/{id}/notice-deadline  (TS-251)
{
  "notice_type": "variation",
  "deadline_days": 14,
  "deadline_basis": "calendar",
  "trigger_date": "2026-08-01",
  "notice_deadline": "2026-08-15",
  "deadline_unknown": false,
  "required_content": ["Written variation notice", "Contract clause reference"],
  "correspondence": { "email": "re@employer.com" }
}
```

## Acceptance criteria

### TS-243 (spec)

- A1: Spec cites Research Doc §4.F and maps every TS-244–TS-256 backlog item to a behavior rule.

### TS-244 (scaffold)

- A2: App boots with `change` enabled; tables exist after migration.
- A3: App boots with `change` disabled; no import errors.
- A4: `POST /events` without sealed baseline returns `no_baseline`.
- A5: Manual event persists with ≥1 source row; list returns it scoped to workspace.

### TS-245–TS-246 (implemented)

- A6 (TS-245): `POST /diff` on revised clause text emits a `baseline_diff` candidate with a
  verbatim `source_quote`.
- A7 (TS-246): `POST /signals` classifies site instructions deterministically; duplicate ingest
  within 24h attaches to the existing event instead of creating a new row.
- A8 (TS-248): `GET /inbox` returns only `candidate`/`triaged` events in confidence order.
- A9 (TS-249): `PUT /impacts` rejects unknown cost-code or finding IDs; exposure totals use minor
  units.
- A10 (TS-250): confirmation outcomes update event status; history is listable.

### TS-251–TS-253 (implemented)

- A11 (TS-251): Deadline matches notice register for same inputs; event trigger uses
  `trigger_date + deadline_days` (calendar days).
- A12 (TS-252): Alert fires once per (user, event, bucket) via `change_notice_alert_log`.
- A13 (TS-253): Draft request blocked until confirmation; artifact `status=draft`; validators pass.

### TS-254–TS-256 (implemented)

- A14 (TS-254): Evidence record persists with `created` custody entry.
- A15 (TS-255): Completeness score lists missing types deterministically.
- A16 (TS-256): Third change event on unactivated project returns 402; webhook activates project.

### TS-247 (implemented)

- A17 (TS-247): Inbound webhook with bad signature returns 400; valid email creates email
  `candidate` with `message_id` dedup.

## Frontend UI (TS-301)

### Public pages

- `/opportunities/{id}` gains a **Changes** tab.
- The tab renders the potential-variation inbox and confirmation workflow.

### Acceptance criteria

- F1: Tab lists `GET /api/change/opportunities/{id}/inbox` events with `status`,
  `title`, `reason`, `confidence_band`, `trigger_date`, and `notice_deadline`.
- F2: Each event exposes outcome buttons: `changed`, `not_changed`, `clarification_only`,
  `contractor_risk`, `client_risk`, `unknown`.
- F3: Recording a confirmation calls `POST /api/change/events/{id}/confirmations` and
  refreshes the list.
- F4: Confirmed events show a **Notice deadline** button that fetches
  `GET /api/change/events/{id}/notice-deadline` and displays `notice_deadline`,
  `deadline_days`, and `required_content`.
- F5: Confirmed events show a **Draft notice** button that calls
  `POST /api/change/events/{id}/notice-draft` and returns an `artifact_id`.
- F6: Users can triage an event via `PUT /api/change/events/{id}/triage` (`triaged` or
  `rejected`).
- F7: Manual event creation is reachable from the tab and calls
  `POST /api/change/opportunities/{id}/events` with at least one `source_quote`.

## Cross-module specs (Phase 18)

| Task | Primary spec | Notes |
|---|---|---|
| TS-252 | `specs/modules/notifications.md` | Notice countdown + dedup |
| TS-253 | `specs/modules/drafting.md` | Verified-facts notice templates |
| TS-254–TS-255 | `specs/modules/evidence.md` (new) | Chain of custody + completeness |
| TS-256 | `specs/modules/billing.md` | Per-project subscription lane |

## Out of scope

- Drawing computer-vision / CAD diff — deferred (`assumption:` text revisions only in Phase 18).
- Autonomous notice issuance — human approval mandatory (Build Doc §11.4).
- Claims valuation and quantum — **Phase 19**.
- Business-day holiday calendars — calendar days only (`assumption:` same as Phase 17).
- Procore / ACC adapters — **Phase 21** (TS-283).

## Assumptions

- `assumption:` Phase 18 uses the same calendar-day notice arithmetic as Phase 17 until a GCC
  business-day calendar lands in a later phase.
- `assumption:` Email ingestion starts with forward-to-inbox + webhook; full mailbox OAuth is Phase 21.
- `assumption:` Evidence tables ship in a sibling `evidence` module spec before TS-254 implementation.
