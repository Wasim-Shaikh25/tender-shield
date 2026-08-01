# Baseline lock — Spec

**Status:** partial — Phase 1 scaffold **implemented** (TS-041–TS-045); Phase 17 completion
**agreed** in spec (TS-235); implementation tasks TS-236–TS-242 **todo**
**Requirement refs:** Doc §0.1 (Baseline lock P2 stage), §10 (Phase 2/3), §1.2 (feature matrix);
Research Doc §4.E, §5.2(10–13); `docs/TenderShield_Roadmap_Stage1_to_5.md` §4
**Task refs:** TS-041, TS-042, TS-043, TS-044, TS-045, TS-235, TS-236, TS-237, TS-238, TS-240, TS-241

## Purpose

Tender knowledge evaporates at handover (Doc §0.1). The `baseline` module **freezes** the reviewed
commercial state — accepted findings, confirmed deadlines, opportunity metadata — into an immutable,
hash-sealed snapshot the site/commercial team can rely on after award.

**Phase 1 (done)** delivers freeze, verify, a regex-based notice register, finding-level
award-vs-tender compare, and a single handover pack + export.

**Phase 17 (this spec)** completes the Research Doc §4.E bridge to Stage 3: convert accepted tender
risks into **project watchlists**, enrich the **notice-rule register** with correspondence and
authority metadata, introduce a **cost-code model** mapped to BOQ and variation categories, and ship
**role-specific handover views**. Approval limits live in `auth` (TS-239) but are enforced at
baseline handover actions. Baseline adoption telemetry lives in `analytics` (TS-242).

Without these controls there is nothing deterministic for Phase 18 change detection to diff against.

## Public interface

### Implemented (Phase 1)

- **Capabilities published:** `baseline.service_factory` → `BaselineService(session)`.
- **Capabilities consumed** (registry only — never imported):
  - `findings.store_factory` — read reviewed findings.
  - `review.service_factory` — export/freeze gate + audit log.
  - `ingestion.service_factory` — opportunity metadata + confirmed deadlines + clauses.
  - `rulepacks.loader` — merged notice standard for classification + gap detection.
  - `standards.org_notice_provider` — org custom notice standard (third layer).
  - `export.service_factory` — handover render (DOCX/PDF/XLSX).
- **Events emitted:** `baseline.sealed` `{workspace_id, opportunity_id, baseline_id, version, source}`.
- **API routes** (prefix `/api/baseline`):
  - `POST /opportunities/{id}/freeze` (reviewer) — seal `{source: tender|award, note?}`.
  - `GET  /opportunities/{id}/baselines` (viewer) — list sealed baselines.
  - `GET  /baselines/{baseline_id}` (viewer) — full snapshot.
  - `GET  /baselines/{baseline_id}/verify` (viewer) — recompute content hash.
  - `GET  /opportunities/{id}/notice-register` (viewer) — notice-rule register (basic).
  - `GET  /opportunities/{id}/compare` (viewer) — latest tender vs award finding delta.
  - `GET  /opportunities/{id}/handover` (estimator) — commercial handover pack (single view).
  - `POST /opportunities/{id}/award-document` (estimator) — upload negotiated contract.
  - `GET  /opportunities/{id}/handover/export` (estimator) — download handover pack.

### Planned (Phase 17 — TS-236–TS-241)

- **Additional capabilities published:**
  - `baseline.watchlist_for_opportunity` — list active watchlist controls for an opportunity.
  - `baseline.cost_codes_for_opportunity` — cost-code tree + BOQ mappings.
- **Additional capabilities consumed:**
  - `auth.approval_matrix` (TS-239) — role/action limits for handover acknowledgement and notice prep.
  - `boq.store` or findings BOQ rows — map accepted BOQ defects / line items to cost codes (soft).
- **Additional events:**
  - `baseline.watchlist_updated` — control owner or cadence changed.
  - `baseline.cost_codes_locked` — cost-code map frozen with baseline version.
- **Additional API routes:**
  - `GET  /opportunities/{id}/watchlist` (viewer) — project controls derived from accepted findings.
  - `PUT  /watchlist/{control_id}` (estimator) — set owner, trigger, review cadence.
  - `GET  /opportunities/{id}/compare/award` (viewer) — **TS-236** full award delta: findings + clause
    concessions + BOQ assumption changes, each with `source_quote` / `document_id`.
  - `PUT  /opportunities/{id}/notice-register/contacts` (admin) — correspondence addresses + authorized
    representatives per notice type (**TS-238**).
  - `GET  /opportunities/{id}/cost-codes` (viewer) — cost-code tree.
  - `POST /opportunities/{id}/cost-codes` (estimator) — create/update codes + BOQ mappings (**TS-240**).
  - `GET  /opportunities/{id}/handover?view={site|planning|procurement|finance}` (estimator) — filtered
    handover pack (**TS-241**).
  - `GET  /opportunities/{id}/handover/export?view=…` (estimator) — per-view export with baseline seal
    reference embedded.

## Data owned

### Implemented

- `baselines` (workspace-scoped, RLS): `id, workspace_id, opportunity_id, version, source,
  content_sha256, snapshot (JSON), note, sealed_by, sealed_at`. Append-only; `(opportunity_id,
  version)` unique.
- `award_documents` (workspace-scoped, RLS): uploaded negotiated contract / award letter text +
  `sha256`.

### Planned (Phase 17)

- `bl_watchlist_controls` (workspace-scoped, RLS): one row per monitored obligation.
  - `id, workspace_id, opportunity_id, baseline_id, finding_id?`, `obligation_key` (stable hash of
    category+title or clause ref), `title, severity, owner_user_id?, trigger_text, review_cadence`
    (`weekly|fortnightly|monthly|milestone`), `next_review_at, status` (`active|closed`),
    `source_page, source_quote, document_id`, `created_at, updated_at`.
  - Seeded from accepted findings at freeze; editable post-freeze without mutating the sealed snapshot.
- `bl_notice_contacts` (workspace-scoped, RLS): per-opportunity notice metadata not inferable from
  contract text alone.
  - `id, workspace_id, opportunity_id, notice_type` (matches register `category`), `party`
    (`employer|contractor|engineer`), `role_label`, `authorized_representative`, `postal_address`,
    `email`, `required_content checklist (JSON)`, `updated_by, updated_at`.
- `bl_cost_codes` (workspace-scoped, RLS): hierarchical cost codes for the project.
  - `id, workspace_id, opportunity_id, parent_id?, code, label, variation_category?, locked_at?`.
- `bl_cost_code_mappings` (workspace-scoped, RLS): BOQ line → cost code.
  - `id, workspace_id, opportunity_id, cost_code_id, boq_src_row?, finding_id?, description_match?`.

No foreign keys into other modules' tables — `finding_id` and `boq_src_row` are opaque references
copied at mapping time.

## Behavior

### Phase 1 — implemented

- **B1 — Freeze gate.** Seal only when `review.export_allowed` is true (`review_incomplete` /
  `review_unavailable` otherwise).
- **B2 — Snapshot content.** Freezes opportunity meta, **accepted/edited** findings (with provenance),
  confirmed deadlines, and the derived notice register. Rejected/proposed findings excluded.
- **B3 — Immutability + hashing.** `content_sha256` over canonical snapshot JSON (excluding volatile
  `sealed_at`). Rows never mutated; re-freeze inserts next version atomically. `verify` detects tamper.
- **B4 — Notice register (basic).** Regex extraction over findings + segmented clauses — **no LLM**.
  Each rule: `days`, unit, trigger phrase, provenance. Deduped by `(days, category)`.
- **B5 — Award-vs-tender delta (findings).** `compare` diffs latest `tender` vs `award` baselines by
  finding identity (category + title): `added`, `removed`, `changed`.
- **B6 — Award-document ingestion.** Upload → text extract → used when sealing `source="award"`.
- **B7 — Handover pack (single view).** From latest seal: header + hash, critical/high obligations,
  notice register, deadline calendar. `no_baseline` when none sealed.
- **B8 — Handover export.** DOCX/PDF/XLSX via `export` renderer.
- **B9 — Workspace isolation.** Every query filtered by `workspace_id` (RLS + explicit).
- **B10 — Standards-aware register + gaps.** When `rulepacks` present, classify windows against merged
  notice standard; expected-but-missing categories → `gap` rows in snapshot. Degrades to extraction-only
  when `rulepacks` disabled. Org standard merged as third layer when `standards` present.

### Phase 17 — planned

- **B11 — Watchlist seeding (TS-237).** On `baseline.sealed`, for each accepted finding with severity
  `critical` or `high`, insert a `bl_watchlist_controls` row unless one with the same `obligation_key`
  already exists. Default `review_cadence=monthly`, `status=active`. Owner unset until assigned.
  Watchlist rows carry the finding's `source_quote` and `document_id` — never paraphrased.
- **B12 — Watchlist maintenance.** Estimators may set `owner_user_id`, `trigger_text` (site trigger),
  and `review_cadence`. Changes emit `baseline.watchlist_updated`. Closing a control sets
  `status=closed` without deleting history.
- **B13 — Award comparison with citations (TS-236).** Extends B5:
  - **Finding delta** — same as today, plus `source_quote` on each side when changed.
  - **Clause concessions** — deterministic diff of segmented clauses between tender seal snapshot and
    award-document text: new/changed/deleted clauses reported with verbatim `source_quote` ≤200 chars
    and `document_id`. No LLM summarisation of concessions.
  - **BOQ assumption delta** — compare accepted BOQ-related findings (defects, scope gaps) between
    seals; flag lines whose `amount_exposure` or description changed beyond tolerance.
  - Output shape: `{findings: {added, removed, changed}, clauses: [...], boq: [...], baseline_refs:
    {tender_id, award_id}}`.
- **B14 — Notice register completion (TS-238).** Extends B4/B10:
  - Each register row gains: `notice_type`, `trigger_event` (normalised enum: `event|date|milestone`),
    `deadline_days`, `deadline_basis` (`calendar|business` — business deferred to Phase 4 GCC),
    `required_content` (checklist from rule-pack category or manual), `correspondence` (from
    `bl_notice_contacts`), `authorized_representative`.
  - Deadline arithmetic is **deterministic**: `notice_deadline = trigger_date + deadline_days` when
    trigger is a known milestone from confirmed deadlines; otherwise `deadline_unknown` with reason.
  - Contacts are **never invented** — empty until user fills `PUT …/notice-register/contacts`.
- **B15 — Cost-code model (TS-240).** Estimators create a hierarchy of `bl_cost_codes` per opportunity.
  Mappings link BOQ `src_row` and/or accepted BOQ-defect findings to a code. Variation categories
  (string tags) optional for Phase 18. On freeze, optionally `lock` mappings into snapshot
  (`cost_codes_locked` event) — locked rows are read-only until next baseline version.
- **B16 — Multi-view handover pack (TS-241).** `view` filter selects sections:
  - `site` — watchlist controls, critical obligations, notice deadlines.
  - `planning` — milestone calendar + notice register.
  - `procurement` — BOQ assumptions, cost-code summary, scope-gap findings.
  - `finance` — exposure totals (minor units + currency), retention/LD notice windows.
  Every view embeds `baseline_id`, `content_sha256`, and `sealed_at` in the header.
- **B17 — Approval enforcement (TS-239, consumed).** Actions that mutate post-award controls
  (`PUT watchlist`, `PUT notice-register/contacts`, `POST cost-codes` after lock) check
  `auth.approval_matrix` for the principal's role. Missing matrix → allow (degrade gracefully when
  `auth` disabled); matrix present → deny with `approval_denied` when over limit.

## Acceptance criteria

### Phase 1 — implemented

- **A1:** freezing before review completes returns an error; after review it seals `version=1` with
  non-empty `content_sha256`.
- **A2:** `verify` returns `intact=true` for an untampered seal.
- **A3:** notice register extracts "within 14 days" with `days=14` and provenance.
- **A4:** re-freeze as `award` yields new version; `compare` reports diff vs tender seal.
- **A5:** handover pack lists sealed hash and critical obligations.
- **A6:** award-document upload + `freeze(award)` includes award text preview.
- **A7:** handover export returns non-empty bytes for docx/pdf/xlsx.
- **A8:** app boots with `baseline` disabled.

### Phase 17 — planned

- **A9 (TS-237):** sealing a baseline with two accepted critical findings creates two watchlist rows;
  assigning an owner persists; cross-workspace read returns empty.
- **A10 (TS-236):** `compare/award` reports a clause concession with verbatim quote present in award
  text; no quote passes M1 quote-integrity if checked against source pages.
- **A11 (TS-238):** setting notice contacts surfaces in register and handover; deadline arithmetic on
  a confirmed milestone date is deterministic and reproducible.
- **A12 (TS-240):** cost codes map to BOQ rows; locked map included in snapshot on freeze; totals use
  minor units with explicit currency.
- **A13 (TS-241):** `handover?view=site` omits finance-only sections; export embeds baseline hash.
- **A14 (TS-239):** user below approval limit receives `approval_denied` on locked cost-code edit.
- **A15 (TS-242):** analytics reports count of opportunities with ≥1 sealed baseline and weekly active
  baseline users (see `specs/modules/analytics.md`).

## Cross-module specs (Phase 17)

| Task | Primary spec | Notes |
|---|---|---|
| TS-238 | `specs/modules/standards.md` | Org notice categories feed B14 classification |
| TS-239 | `specs/modules/auth.md` | Approval matrix schema + enforcement hooks |
| TS-241 | `specs/modules/export.md` | Per-view renderers + seal stamp |
| TS-242 | `specs/modules/analytics.md` | `baseline.weekly_active_users` metric |

## Out of scope

- Change-event detection, notice drafting, countdown alerts — **Phase 18** (`change` module).
- Claims workspace, evidence chain of custody — **Phase 19**.
- Business-day/holiday calendars for notice deadlines — Phase 4 GCC (`assumption:` calendar-day only
  in Phase 17).
- BOQ item-level dedicated table freeze — BOQ remains findings-backed until data-model task lands.
- Automated LLM parsing of award contracts beyond stored text + clause segmentation.

## Assumptions

- `assumption:` "review complete" reuses the `review` module's `export_allowed` gate.
- `assumption:` month normalisation for notice windows uses 30 calendar days (existing B4).
- `assumption:` `obligation_key` for watchlist dedup is `sha256(category + "|" + title)` unless a
  `pattern_id` is present on the finding (then pattern_id wins).
- `assumption:` Phase 17 does not require a paying customer gate — unlike SAE patterns (Strategy §D.2),
  baseline controls are core Stage 2 product.
