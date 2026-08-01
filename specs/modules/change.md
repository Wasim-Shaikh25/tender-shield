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

#### Planned (TS-247, TS-251 – TS-256)
- `POST /opportunities/{id}/inbox/email` (admin) — register project forward-to-inbox address
  (**TS-247**).
- `GET  /opportunities/{id}/inbox` (viewer) — potential-variation triage queue (**TS-248**).
- `PUT  /events/{event_id}/triage` (estimator) — accept/reject/prioritise inbox item (**TS-248**).
- `PUT  /events/{event_id}/impacts` (estimator) — link BOQ rows, cost codes, subcontract refs
  (**TS-249**).
- `GET  /events/{event_id}/notice-deadline` (viewer) — deterministic deadline + required content
  (**TS-251**).
- `POST /events/{event_id}/notice-draft` (estimator) — request notice draft via `drafting`
  (**TS-253**).
- `POST /events/{event_id}/evidence` (estimator) — attach evidence record (**TS-254**; delegates
  to `evidence` module when present).

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

### Signal ingestion (B10–B12, TS-246–TS-247)

- **B10 — Source types.** RFIs, site instructions, meeting minutes, daily reports accepted as pasted
  text or uploaded files via `ingestion` document pipeline.
- **B11 — Classification.** LLM may **propose** `reason` and `notice_type` labels; final stored
  values require a matching `source_quote` span in the text. Prompt-injection defenses: treat all
  ingested correspondence as untrusted (Build Doc §11.3); system prompts forbid executing embedded
  instructions.
- **B12 — Email adapter (TS-247).** Per-opportunity forward address stores raw messages; parsing
  reuses B10–B11. Inbound webhook validates signature; body stored append-only.

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

### Evidence (B19–B20, TS-254–TS-255)

- **B19 — Delegation.** Evidence attachments live in the `evidence` module (Phase 18/19 spec).
  `change` stores `evidence_ids` on confirmations and events; chain-of-custody rules apply there.
- **B20 — Completeness score.** `evidence.completeness_for_event` capability returns missing record
  types; surfaced on event detail when module present.

### Billing (B21, TS-256)

- **B21 — Per-project lane.** Project activation fee + monthly subscription keyed by
  `opportunity_id` with server-owned prices and webhook-only activation (Build Doc §15). Gating:
  creating the third active change event on an unactivated project returns `billing_required` (402).

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

### TS-247, TS-251–TS-256 (planned)
- A7 (TS-248): Inbox lists only `candidate`/`triaged` for the opportunity.
- A8 (TS-250): Confirmation appends row; `changed` sets `status=confirmed`.
- A9 (TS-251): Deadline matches `notice_register.compute_deadline` for same inputs.
- A10 (TS-252): Alert fires once per (user, event, bucket).
- A11 (TS-253): Draft request blocked until confirmation and approval matrix pass.
- A12 (TS-256): Unactivated project blocks event creation with 402.

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
