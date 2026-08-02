# Claims & Evidence Workspace — Spec

**Status:** draft
**Requirement refs:** Research Doc §4.G, §5.3, §13; `docs/TenderShield_Roadmap_Stage1_to_5.md` §4 (Stage 4), §3.1; `docs/TenderShield_Market_Strategy_2026.md` §B.3, §12.1
**Task refs:** TS-257, TS-258, TS-259, TS-260, TS-261, TS-262, TS-263, TS-264, TS-265, TS-266, TS-267, TS-268, TS-269, TS-270

## Purpose

Stage 4 turns the contemporaneous records captured in Stage 3 into defensible claim packages. The `claims` module assembles a cited **chronology**, an **evidence checklist** per claim type, a deterministic **quantum workspace**, a **delay-event register**, draft generators (particulars, variation proposal, EOT, full claim pack), and a negotiation/settlement lifecycle. It also produces the **chain-integrity test** and feeds any recovered value into the `margin_protected` north-star metric.

The evidence chain remains unbroken:

```
tender clause → baseline obligation → change event → notice → evidence → claim → outcome
```

Without Stage 3 evidence the module degrades gracefully; without a baseline the quantum and delay registers still record facts, but chain-integrity tests will flag the missing upstream link.

## Public interface

### Capabilities published

- `claims.service_factory` → `ClaimsService(session)`.
- `claims.chronology_for_claim` — cited chronology list for a claim id (TS-259).
- `claims.checklist_for_claim` — evidence checklist with present/missing flags (TS-260).
- `claims.quantum_for_claim` — deterministic quantum summary (TS-261).
- `claims.delay_register_for_opportunity` — delay events with programme links (TS-262).
- `claims.draft_for_claim` — generate a claim draft of a given kind (TS-263).
- `claims.negotiation_timeline` — issue → response → negotiation → settlement (TS-264).
- `claims.chain_integrity` — verify the tender→claim link (TS-266).
- `claims.conflict_check` — flag opposing-party conflicts (TS-267).
- `claims.cycle_metrics` — claim-cycle-time metrics for analytics (TS-268).
- `claims.record_outcome` — record settlement/recovered value (TS-265, TS-269).

### Capabilities consumed (soft — registry only)

| Capability | Use |
|---|---|
| `change.service_factory` | Read confirmed change events, sources, notices |
| `evidence.service_factory` | List evidence records for an event |
| `baseline.service_factory` | Read notice register, cost codes, sealed baseline |
| `findings.store_factory` | Read accepted findings for impact/value |
| `drafting.service_factory` | Generate claim draft artifacts (TS-263) |
| `export.service_factory` | Render claim pack to DOCX/PDF/XLSX |
| `review.service_factory` | Audit log and human approval gate |
| `auth.approval_matrix` | Gate claim submission/settlement |
| `outcomes.service_factory` | Record settlement/recovered value (TS-265, TS-269) |
| `analytics.service_factory` | Push workflow metrics (TS-268) |
| `notifications.sender` | Notify claim deadlines/escalations |

### Events emitted

| Event | Payload (minimum) |
|---|---|
| `claim.created` | `workspace_id`, `opportunity_id`, `claim_id`, `claim_type` |
| `claim.submitted` | `workspace_id`, `claim_id`, `submitted_by` |
| `claim.response_received` | `workspace_id`, `claim_id`, `response_kind` |
| `claim.negotiated` | `workspace_id`, `claim_id`, `round`, `status` |
| `claim.settled` | `workspace_id`, `claim_id`, `outcome`, `recovered_amount_minor` |
| `claim.chain_broken` | `workspace_id`, `claim_id`, `missing_link` |
| `quantum.computed` | `workspace_id`, `claim_id`, `total_minor`, `currency` |
| `delay.registered` | `workspace_id`, `opportunity_id`, `delay_event_id` |

### Events consumed

| Event | Action |
|---|---|
| `change.event_confirmed` | Optional auto-suggest a claim candidate when `outcome=changed` (manual approval still required) |
| `change.notice_deadline_computed` | Link claim to upstream notice deadline |
| `evidence.record_attached` | Update evidence-completeness score on linked events |
| `baseline.sealed` | Refresh baseline reference for chain-integrity checks |

### API routes (prefix `/api/claims`)

#### Scaffold & lifecycle (TS-258)

- `GET  /opportunities/{id}/claims` (viewer) — list claims for an opportunity.
- `POST /opportunities/{id}/claims` (estimator) — create a claim, optionally from a `change_event_id`.
- `GET  /claims/{claim_id}` (viewer) — claim detail with latest status.
- `PUT  /claims/{claim_id}` (estimator) — update title/description/claim_amount.
- `POST /claims/{claim_id}/submit` (estimator) — submit claim; approval matrix `claim_submit` may gate.

#### Chronology (TS-259)

- `GET  /claims/{claim_id}/chronology` (viewer) — every entry cited with source quote/page/document.

#### Evidence checklist (TS-260)

- `GET  /claims/{claim_id}/checklist` (viewer) — required types for `claim_type` with present/missing flags.
- `POST /claims/{claim_id}/checklist/{item_id}/override` (estimator) — mark required item N/A with reason.

#### Quantum workspace (TS-261)

- `GET  /claims/{claim_id}/quantum` (viewer) — quantum summary with totals.
- `POST /claims/{claim_id}/quantum/line-items` (estimator) — add measured/daywork line item.
- `PUT  /claims/{claim_id}/quantum/line-items/{line_id}` (estimator).
- `DELETE /claims/{claim_id}/quantum/line-items/{line_id}` (estimator).

#### Delay register (TS-262)

- `GET  /opportunities/{id}/delay-register` (viewer) — list delay events.
- `POST /opportunities/{id}/delay-register` (estimator) — record a delay event.
- `GET  /delay-register/{event_id}` (viewer).

#### Draft generators (TS-263)

- `POST /claims/{claim_id}/drafts/{kind}` (estimator) — generate `particulars`, `variation_proposal`, `eot`, `full_pack`.
- `GET  /claims/{claim_id}/drafts` (viewer) — list drafts.
- `GET  /drafts/{draft_id}` (viewer).
- `POST /drafts/{draft_id}/approve` (reviewer) — approve for issue.

#### Negotiation & settlement (TS-264)

- `POST /claims/{claim_id}/responses` (estimator) — record a response.
- `POST /claims/{claim_id}/negotiations` (estimator) — record a negotiation round.
- `POST /claims/{claim_id}/settlement` (estimator) — settle / withdraw / dispute.
- `GET  /claims/{claim_id}/timeline` (viewer) — issue→response→negotiation→settlement.

#### Conflicts & integrity (TS-266, TS-267)

- `GET /claims/{claim_id}/chain-integrity` (viewer) — pass/fail with missing link.
- `GET /claims/{claim_id}/conflicts` (admin) — flag opposing parties on same opportunity.

#### Metrics (TS-268)

- `GET /opportunities/{id}/claim-metrics` (viewer) — cycle-time and status counts (consumed by `analytics`).

## Data owned

All tables are workspace-scoped (RLS). Other modules reference claim data by UUID + events only — **no foreign keys into `change`, `baseline`, `findings`, or `evidence` tables**.

### `claims`

Core claim record.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID | RLS |
| `opportunity_id` | UUID | indexed; logical ref to ingestion opportunity |
| `change_event_id` | UUID nullable | linked change event (no FK) |
| `baseline_id` | UUID nullable | sealed baseline used for chain-integrity (no FK) |
| `claim_type` | string | `variation` \| `extension_of_time` \| `disruption` \| `prolongation` \| `final_account` |
| `claimant_party` | string nullable | `contractor` \| `employer` \| `engineer` \| `other`; used for conflict detection |
| `status` | string | `draft` \| `submitted` \| `under_review` \| `negotiated` \| `settled` \| `disputed` \| `withdrawn` |
| `title` | string | |
| `description` | text nullable | |
| `claim_amount_minor` | bigint nullable | asserted by contractor (minor units) |
| `recovered_amount_minor` | bigint nullable | settled/recovered (minor units) |
| `currency` | string | ISO 4217, default `INR` |
| `submitted_at` | timestamptz nullable | |
| `submitted_by` | UUID nullable | |
| `approved_by` | UUID nullable | |
| `settled_at` | timestamptz nullable | |
| `created_by` | UUID | |
| `created_at`, `updated_at` | timestamptz | |

### `claim_chronology_entries`

Append-only cited chronology.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID | RLS |
| `opportunity_id` | UUID | indexed |
| `claim_id` | UUID FK → `claims.id` CASCADE | |
| `entry_type` | string | `event` \| `notice` \| `evidence` \| `correspondence` \| `response` \| `negotiation` \| `settlement` \| `delay` |
| `source_id` | UUID | opaque ref to the upstream row |
| `source_kind` | string | `change_event` \| `change_source` \| `evidence_record` \| `claim_response` \| `claim_negotiation` \| `claim_settlement` \| `claim_delay` |
| `title` | string | human-readable summary |
| `occurred_at` | timestamptz | when the entry happened |
| `source_page` | int nullable | |
| `source_quote` | string ≤200 | verbatim citation |
| `document_id` | UUID nullable | optional ingestion document ref |
| `custody_chain` | JSON | copy of evidence record custody chain (if any) |
| `created_at` | timestamptz | |

### `claim_evidence_checklist_items`

Per-claim checklist (TS-260).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID | RLS |
| `claim_id` | UUID FK → `claims.id` CASCADE | |
| `item_type` | string | `instruction` \| `baseline` \| `revised_scope` \| `labour` \| `plant` \| `material` \| `schedule` \| `photos` \| `approvals` \| `quantum` \| `delay` \| `correspondence` |
| `required` | bool | from static claim-type map |
| `present` | bool | |
| `evidence_record_ids` | JSON | list of evidence UUIDs |
| `override_note` | string nullable | N/A reason |
| `updated_at` | timestamptz | |

### `claim_quantum_line_items`

Deterministic quantity/rate/daywork lines (TS-261).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID | RLS |
| `claim_id` | UUID FK → `claims.id` CASCADE | |
| `cost_code_id` | UUID nullable | logical ref to `bl_cost_codes` |
| `description` | string | |
| `quantity` | Numeric(20,4) | measured quantity |
| `unit` | string | e.g. `m3`, `m`, `nos` |
| `rate_minor` | bigint | rate per unit in minor units |
| `daywork_days` | int nullable | daywork days |
| `daywork_rate_minor` | bigint nullable | daywork rate per day in minor units |
| `currency` | string | ISO 4217 |
| `created_by` | UUID | |
| `created_at` | timestamptz | |

### `claim_delay_events`

Delay-event register (TS-262).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID | RLS |
| `opportunity_id` | UUID | indexed |
| `claim_id` | UUID nullable | linked claim (no FK) |
| `change_event_id` | UUID nullable | linked change event (no FK) |
| `event_date` | date | |
| `description` | string | |
| `delay_days` | int | factual delay duration |
| `programme_activity` | string nullable | linked programme activity |
| `source_page` | int nullable | |
| `source_quote` | string ≤200 | |
| `document_id` | UUID nullable | |
| `created_by` | UUID | |
| `created_at` | timestamptz | |

### `claim_responses`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID | RLS |
| `claim_id` | UUID FK → `claims.id` CASCADE | |
| `response_kind` | string | `acknowledgment` \| `rejection` \| `request_info` \| `counter_proposal` |
| `received_at` | date | |
| `due_at` | date nullable | next response due |
| `responder` | string | |
| `notes` | text nullable | |
| `document_id` | UUID nullable | |

### `claim_negotiations`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID | RLS |
| `claim_id` | UUID FK → `claims.id` CASCADE | |
| `round` | int | 1-indexed |
| `offered_amount_minor` | bigint | |
| `counter_amount_minor` | bigint | |
| `status` | string | `open` \| `accepted` \| `rejected` |
| `recorded_by` | UUID | |
| `recorded_at` | timestamptz | |

### `claim_settlements`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID | RLS |
| `claim_id` | UUID FK → `claims.id` CASCADE | unique: one settlement per claim |
| `outcome` | string | `approved` \| `negotiated` \| `rejected` \| `withdrawn` \| `disputed` |
| `settled_amount_minor` | bigint | |
| `currency` | string | |
| `notes` | text nullable | |
| `recorded_by` | UUID | |
| `recorded_at` | timestamptz | |

### `claim_drafts`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | UUID | RLS |
| `claim_id` | UUID FK → `claims.id` CASCADE | |
| `draft_kind` | string | `particulars` \| `variation_proposal` \| `eot` \| `full_pack` |
| `status` | string | `draft` \| `approved` |
| `body` | JSON | structured draft payload |
| `version` | int | |
| `created_by` | UUID | |
| `created_at` | timestamptz | |

## Behavior

### Lifecycle & upstream links (B1–B3, TS-258)

- **B1 — Create claim.** `POST /opportunities/{id}/claims` creates a `draft` claim. If `change_event_id` is supplied, the service copies `change_event_id` and `baseline_id` from the event. If `change` module is unavailable, manual creation is allowed but `change_event_id` and `baseline_id` are null.
- **B2 — Workspace/project anchor.** `opportunity_id` is the anchor, consistent with `change` and `baseline`. `claims` does not import `opportunities`; it stores the UUID only.
- **B3 — Degradation.** The module boots and serves empty lists even when `change`, `evidence`, or `baseline` are disabled. Missing upstream modules only disable the relevant helper endpoints (`/chronology`, `/chain-integrity`, `/checklist`).

### Chronology builder (B4–B6, TS-259)

- **B4 — Everything cited.** Every chronology entry carries `source_quote`, `source_page`, and `document_id` when available. Entries without a verifiable citation are hidden with a `citation_missing` flag.
- **B5 — Sources.** The builder gathers: the linked `change_event` and its `change_sources`; the computed notice deadline; attached `evidence_records` (with custody chain copied); `claim_responses`; `claim_negotiations`; `claim_settlements`; `claim_delay_events`; and any manually added entries.
- **B6 — Sorting.** Entries are returned in `occurred_at` ascending. Ties use `entry_type` order: `event`, `notice`, `evidence`, `delay`, `correspondence`, `response`, `negotiation`, `settlement`.

### Evidence checklist (B7–B9, TS-260)

- **B7 — Static claim-type map.** A deterministic map defines required `item_type` values per `claim_type` (never LLM). Example: `variation` requires `instruction`, `baseline`, `revised_scope`, `quantum`, `correspondence`; `extension_of_time` adds `delay` and `schedule`.
- **B8 — Present flag.** `present` becomes `true` when at least one evidence record of the matching type is linked to the claim or to its linked change event. Override with `override_note` sets `present=true` and records the reason.
- **B9 — Completeness score.** `len(present) / len(required)` as a 0–100 integer, surfaced on claim detail.

### Quantum workspace (B10–B13, TS-261)

- **B10 — Zero LLM.** All arithmetic is deterministic Python `Decimal`/`int`. Total measured = `Σ(quantity × rate_minor)`. Total daywork = `Σ(daywork_days × daywork_rate_minor)`. Grand total = measured + daywork.
- **B11 — Money in minor units.** `rate_minor` and output totals are integers in the claim's `currency` minor units. Quantity is `Numeric(20,4)` to preserve fractional units.
- **B12 — Explicit inputs.** Every total exposes its inputs (`line_items[]`) so the calculation is auditable. No invented numbers.
- **B13 — Cost-code link optional.** `cost_code_id` is an opaque UUID. If `baseline` is disabled, the line item still stores the id but no validation is performed.

### Delay-event register (B14–B16, TS-262)

- **B14 — Fact only.** The register records `event_date`, `description`, `delay_days`, `programme_activity`, plus provenance. It **never** computes an autonomous entitlement or EOT conclusion.
- **B15 — Link optional.** A delay event may link to a `claim_id` and/or `change_event_id`; it may also stand alone.
- **B16 — Roll-up.** `/claim-metrics` returns the sum of `delay_days` per opportunity as a factual roll-up.

### Draft generators (B17–B19, TS-263)

- **B17 — Verified facts only.** Drafts are assembled from the chronology, quantum summary, evidence checklist, and claim metadata. They are passed through the same three validators as `drafting`: no invented quotes, no uncited clauses, no invented numbers.
- **B18 — Draft status.** Generated drafts have `status=draft` and require human approval (`POST /drafts/{id}/approve`) before issue. The `claim_submit` approval-matrix action may gate approval.
- **B19 — Delegation.** `claims` calls `drafting.service_factory` or `export.service_factory` for rendering; if unavailable, it returns a structured JSON draft body.

### Negotiation & settlement (B20–B22, TS-264, TS-265)

- **B20 — Append-only history.** Responses, negotiation rounds, and settlements are inserted, never mutated. The latest settlement determines `claims.status` and `recovered_amount_minor`.
- **B21 — Settlement outcomes.** Valid outcomes: `approved`, `negotiated`, `rejected`, `withdrawn`, `disputed`. `settled` is a terminal state for `approved` and `negotiated`; `disputed` and `withdrawn` are also terminal.
- **B22 — Outcome feedback.** On settlement, `claims` publishes `claim.settled` and, if `outcomes` is enabled, calls `outcomes.record_claim_outcome` with the recovered amount so `margin_protected` can grow (TS-269).

### Chain-integrity test (B23–B25, TS-266)

- **B23 — Required links.** A claim is `intact` only when it can trace: `claim` → `change_event` → `baseline` → `tender clause` (via the baseline snapshot) → `notice` (via `change.notice_deadline` or baseline notice register). Missing any link returns `chain_broken` with `missing_link` set to the first gap.
- **B24 — Trigger.** `GET /claims/{id}/chain-integrity` runs the test on demand. `POST /claims/{id}/submit` also runs it and rejects submission if broken.
- **B25 — Event.** A broken chain emits `claim.chain_broken` for audit/alerts.

### Conflicts control (B26, TS-267)

- **B26 — Opposing parties.** `GET /claims/{id}/conflicts` checks whether another claim on the same `opportunity_id` carries a conflicting `claimant_party` marker (e.g. `contractor` vs `employer`/`engineer`). `claimant_party` is set per claim (`contractor` | `employer` | `engineer` | `other`) because the auth module does not yet expose party metadata. When a conflict is found, the endpoint returns `conflict_detected: true` and a list of the opposing claims for admin review.

### Metrics (B27–B28, TS-268, TS-269)

- **B27 — Cycle time & notice timeliness.** `claims.cycle_metrics` computes `submitted_at - created_at`, `first_response_at - submitted_at`, and `settled_at - submitted_at` per claim. It exposes `status_counts`, per-claim `cycle_times`, `averages`, and a `notice_timeliness` block comparing each `submitted_at` to the linked event's `notice_deadline` (on-time / late / on-time-rate).
- **B28 — Recovered value.** `recovered_amount_minor` flows to `outcomes.record_claim_outcome` on settlement to update the `margin_protected` north-star metric, but only when the claim is `settled` or `negotiated`.

### Site evidence (B29, TS-270)

- **B29 — Record types.** The checklist recognizes additional evidence `record_type` values from `evidence`: `geotagged_photo`, `labour`, `plant`, `daywork`. These count toward the `photos`, `labour`, `plant`, `daywork` checklist items respectively. Full mobile/offline sync is deferred to Phase 21; this is only the storage hook.

### Org isolation & provenance (B30–B31)

- **B30 — RLS.** Every query filters by `workspace_id`. The service never trusts path parameters for scoping.
- **B31 — Provenance.** Every draft, chronology entry, and delay event carries `source_quote` and `document_id` when the source provides them. No uncited facts in generated artifacts.

## Response shapes (illustrative)

```jsonc
// GET /api/claims/opportunities/{id}/claims
{
  "claims": [
    {
      "id": "…",
      "claim_type": "variation",
      "status": "draft",
      "title": "Additional pile depth — revised drawing P-12",
      "claim_amount_minor": 175000,
      "currency": "INR",
      "completeness_score": 60,
      "chain_integrity": "intact"
    }
  ]
}
```

```jsonc
// GET /api/claims/claims/{id}/quantum
{
  "currency": "INR",
  "measured_total_minor": 150000,
  "daywork_total_minor": 25000,
  "total_minor": 175000,
  "line_items": [
    {
      "description": "Additional RCC pile",
      "quantity": "3.50",
      "unit": "m3",
      "rate_minor": 50000,
      "measured_total_minor": 175000
    }
  ]
}
```

## Acceptance criteria

- **A1 (TS-257):** Spec cites Research Doc §4.G/§5.3/§13 and maps every TS-258–TS-270 backlog item to a behavior rule.
- **A2 (TS-258):** App boots with `claims` enabled; tables exist after migration. App also boots with `claims` disabled.
- **A3 (TS-259):** `GET /claims/{id}/chronology` returns entries sorted by `occurred_at`; every entry has `source_quote` and `document_id` when the source provides them.
- **A4 (TS-260):** Checklist for a `variation` claim lists missing items until evidence of matching type is attached; override persists a reason.
- **A5 (TS-261):** Quantum total equals `Σ(quantity × rate_minor) + Σ(daywork_days × daywork_rate_minor)`; no LLM is invoked.
- **A6 (TS-262):** Delay register records `delay_days` with provenance and does not emit an entitlement conclusion.
- **A7 (TS-263):** Generated `full_pack` draft contains chronology, quantum, and checklist; `status=draft`; validators pass.
- **A8 (TS-264):** Settlement route records outcome and updates claim `status` and `recovered_amount_minor`.
- **A9 (TS-265):** A settled claim publishes `claim.settled` with the recovered amount.
- **A10 (TS-266):** Submitting a claim with no linked change event fails chain integrity and returns `chain_broken`.
- **A11 (TS-267):** Conflict endpoint flags when claims from opposing parties exist on the same opportunity.
- **A12 (TS-268):** `/claim-metrics` returns cycle-time averages, status counts, and notice-timeliness on-time rate.
- **A13 (TS-269):** Settled `recovered_amount_minor` is passed to `outcomes` for the `margin_protected` metric.
- **A14 (TS-270):** Site evidence record types (`geotagged_photo`, `labour`, `plant`, `daywork`) count toward checklist items.

## Out of scope

- GCC/FIDIC-specific entitlement law — only facts and deadlines.
- Autonomous claim submission or issue — human approval is mandatory (Build Doc §11.4).
- Mobile offline sync and native apps — Phase 21.
- Litigation/court-tracking — out.
- Auto-extraction of quantum from documents — manual entry with deterministic compute.
- Business-day/holiday calendars for delay analysis — calendar days only in Phase 19.

## Assumptions

- `assumption:` `claims` uses `opportunity_id` as the project anchor, consistent with `change` and `baseline`.
- `assumption:` Currency defaults to `INR`; every monetary field carries explicit `currency`.
- `assumption:` Quantity is `Numeric(20,4)`; rate and totals are minor-unit integers.
- `assumption:` Approval-matrix action names for claims are `claim_submit` and `claim_settle`.
- `assumption:` Evidence checklist is static per `claim_type` in Phase 19; org-custom checklists are deferred.
- `assumption:` `outcomes` records settlement value via an `outcomes.record_claim_outcome` capability; if absent the event is still published.
