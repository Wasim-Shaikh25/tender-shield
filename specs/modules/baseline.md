# Baseline lock — Spec

**Status:** implemented
**Requirement refs:** Doc §0.1 (Baseline lock P2 stage), §10 (Phase 2/3),
§1.2 (feature matrix — "Baseline lock + handover pack")
**Task refs:** TS-041, TS-042, TS-043, TS-044, TS-045

## Purpose

Tender knowledge evaporates at handover (Doc §0.1). When a tender is won, the
`baseline` module **freezes** the reviewed commercial state — accepted findings,
confirmed deadlines and opportunity metadata — into an immutable, hash-sealed
snapshot the site/commercial team can rely on after award. From that frozen
graph it derives a **notice-rule register** (contractual time windows that seed
the Phase-3 countdowns), an **award-vs-tender delta** (what changed between two
seals), and a **commercial handover pack**. It is a pluggable module: the app
boots and every other feature works with `baseline` disabled.

## Public interface

- **Capabilities published:** `baseline.service_factory` → `BaselineService(session)`.
- **Capabilities consumed** (registry only — never imported):
  - `findings.store_factory` — read reviewed findings.
  - `review.service_factory` — the export/freeze gate + audit log.
  - `ingestion.service_factory` — opportunity metadata + confirmed deadlines + clauses.
  - `rulepacks.loader` — the merged notice standard (universal + regional) for
    classification + gap detection (degrades to extraction-only when absent).
  - `standards.org_notice_provider` — the org's custom notice standard, merged
    as the third layer (prevail / side-by-side) when present.
- **Events emitted:** `baseline.sealed` `{opportunity_id, baseline_id, version, source}`.
- **Events consumed:** none.
- **API routes** (prefix `/api/baseline`):
  - `POST /opportunities/{id}/freeze` (reviewer) — seal a new baseline version
    from the current accepted state. Body `{source: "tender"|"award", note?}`.
  - `GET  /opportunities/{id}/baselines` (viewer) — list sealed baselines.
  - `GET  /baselines/{baseline_id}` (viewer) — full snapshot.
  - `GET  /baselines/{baseline_id}/verify` (viewer) — recompute the content hash
    and report whether the seal is intact.
  - `GET  /opportunities/{id}/notice-register` (viewer) — notice-rule register.
  - `GET  /opportunities/{id}/compare` (viewer) — latest tender vs latest award
    baseline delta (added / removed / changed findings).
  - `GET  /opportunities/{id}/handover` (estimator) — commercial handover pack.
  - `POST /opportunities/{id}/award-document` (estimator) — upload/parse negotiated contract or award letter
  - `GET  /opportunities/{id}/handover/export` (estimator) — download handover pack as `docx`/`pdf`/`xlsx`

## Data owned

- `baselines` (org-scoped, RLS): `id, org_id, opportunity_id, version, source,
  content_sha256, snapshot (JSON), note, sealed_by, sealed_at`. One row per seal;
  `(opportunity_id, version)` is unique. **Append-only in practice** — rows are
  never updated after insert (B3).
- `award_documents` (org-scoped, RLS): `id, org_id, opportunity_id, filename, text,
  sha256, uploaded_by, created_at`. Stores the extracted text of the negotiated
  contract / award letter used to seal the `source="award"` baseline.

No other module's tables are touched; findings/deadlines/opportunity are read via
capabilities and copied into the frozen snapshot by value.

## Behavior

- **B1 — Freeze gate.** A baseline can be sealed only when review is complete
  (the `review` gate's `export_allowed` is true — Doc §11.4). With `review`
  absent the freeze is refused (`review_unavailable`). This keeps the
  professional-liability spine: nothing is frozen that a human has not signed off.
- **B2 — Snapshot content.** The snapshot freezes, by value: opportunity meta
  (title, employer, employer_family, contract_form, jurisdiction), the
  **accepted/edited** findings only (each with its verbatim provenance —
  `source_page`, `source_quote`), all **confirmed** deadlines, and the derived
  notice-rule register. Rejected/proposed findings and unconfirmed deadlines are
  excluded.
- **B3 — Immutability + hashing.** `content_sha256` is a SHA-256 over the
  canonical JSON of the snapshot **excluding** the volatile `sealed_at`. Sealed
  rows are never mutated; a re-freeze always inserts `version = max+1`. `verify`
  recomputes the hash from the stored snapshot and reports a mismatch (tamper
  detection) — the doc's "baseline freeze (hashes)" requirement.
- **B4 — Notice-rule register is deterministic.** Notice windows are extracted by
  regex over the accepted findings **and the segmented contract clauses** —
  never by an LLM (Doc §4: numbers never come from the model). Reading clauses
  directly means the register populates from the real contract text even when no
  LLM classifier is configured. Each rule carries `days` (normalised: weeks×7,
  months×30), the raw unit, the trigger phrase, and provenance. Deduped by
  `(days, category)`.
- **B5 — Award-vs-tender delta.** `compare` diffs the latest `source="tender"`
  baseline against the latest `source="award"` baseline by finding identity
  (category + title), reporting `added`, `removed`, and `changed`
  (severity/detail/exposure differences). Deterministic; no LLM.
- **B6 — Award-document ingestion.** An uploaded award letter or negotiated contract
  is stored, text-extracted, and the resulting `text` is used when sealing an
  `source="award"` baseline so the award baseline reflects the real signed contract.
- **B7 — Handover pack.** A structured pack assembled from the latest sealed
  baseline: header (opportunity + seal hash), critical/high obligations, the
  notice register, and the confirmed deadline calendar. Requires a sealed
  baseline (`no_baseline` otherwise).
- **B8 — Handover-pack export.** `export_handover` renders the pack to DOCX, PDF,
  or XLSX using the `export` renderer; returns filename, media type, and bytes.
- **B9 — Org isolation.** Every query is filtered by `org_id` explicitly
  (defence in depth alongside RLS), like every other module.
- **B10 — Standards-aware register + gap detection.** When `rulepacks` is present,
  the notice register is analysed against the merged notice standard for the
  opportunity's jurisdiction (universal base + regional overlay, spec rulepacks
  B7). Each extracted window is classified into a semantic category by keyword
  match; every **expected** category with no matching window becomes a `gap`
  (the notice analogue of risk absence detection) — deterministic, no LLM. Gaps
  and the region are frozen into the snapshot and surfaced in the register and
  handover pack. With `rulepacks` disabled the module degrades to
  extraction-only (no classification, no gaps). When `standards` is present the
  org's custom standard is merged as a third layer (spec standards B1) — its
  regimes participate in classification and gap detection, tagged `origin="org"`.

## Acceptance criteria

- **A1:** freezing before review completes returns an error; after all findings
  are reviewed it seals a `version=1` baseline with a non-empty `content_sha256`.
- **A2:** `verify` returns `intact=true` for an untampered seal.
- **A3:** the notice register extracts a "within 14 days" window from a finding
  quote with the correct `days=14` and its provenance.
- **A4:** editing/rejecting a finding then re-freezing as `award` yields a new
  version; `compare` reports the difference against the tender seal.
- **A5:** the handover pack lists the sealed hash and the critical obligations.
- **A6:** `POST /award-document` extracts text, and a subsequent `freeze(source="award")` includes the award text preview.
- **A7:** `GET /handover/export?format=docx|pdf|xlsx` returns non-empty bytes for a sealed baseline.
- **A8:** the app boots and Phase-1 flows pass with `baseline` disabled.

## Out of scope

- BOQ item-level freeze (BOQ is persisted as findings today; a dedicated
  `boq_items` table is a later data-model task).
- Notice-draft generation — Phase 3.
- Automated clause-level award-vs-tender parsing beyond the extracted text preview.

## Assumptions

- `assumption:` "review complete" is defined as the `review` module's existing
  export gate (`export_allowed`); the doc names award as the trigger but does not
  specify the gate, so the reviewed-state gate is reused for consistency.
- `assumption:` notice-window month normalisation uses 30 days (calendar-day
  approximation); business-day/holiday calendars are Phase-4 (GCC) work.
