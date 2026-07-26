# TenderShield Phase 1.5 — Bid-Decision Extensions

**Status:** requirements & roadmap — not yet implemented  
**Requirement source:** user request (2026-07-26); builds on `docs/TenderShield_Full_Build_Doc.md` v1.0 and the Phase 1 pre-bid workflow  
**Goal:** extend the core pre-bid workflow from "what are the risks?" to "should we bid?" without expanding into adjacent products.

---

## 1. Guiding principles

1. **No new domains.** These features stay inside the pre-bid, tender-review job. They do not become ERP, project management, BIM, procurement, accounting, or site tools.
2. **Existing architecture first.** Each feature is owned by one existing module or one new, pluggable module. Cross-module interaction uses the registry/event bus.
3. **Trust before speed.** Every new output must cite source clauses and be reviewable; deterministic logic preferred; LLMs only for extraction/judgment inside existing guardrails.
4. **Phase 1 exit gate still applies.** Do not ship these as "validated" until the accuracy gate (real tenders + QS review) is met.
5. **Freeze after Bid Decision Intelligence.** Bid Decision Intelligence is the capstone feature; the others are inputs, enablers, or post-validation internal tools.

---

## 2. Domain & market framing

### The pre-bid job
TenderShield's primary user is a mid-market Indian general contractor or specialty contractor bidding on 5–30 tenders per month. Their job is to decide, in a few hours, whether to commit estimating effort to a tender. The current product reduces reading time and surfaces risks. The next pain point is **decision confidence**:

- "Are we even eligible?" (qualification)
- "How risky is this compared to the other tenders on my desk?" (comparison)
- "Did I miss a corrigendum that changed the deal?" (change detection)
- "What is the real deadline cascade?" (timeline)
- "Where else is this clause referenced?" (cross-reference)
- "Why should I believe this risk?" (explainability)
- "Does this violate our own company policy?" (org standards)
- "Which tenders should we prioritize?" (bid/no-bid score)

These are all **information problems inside the same workflow**, not new workflows. That is why they fit Phase 1.5 rather than a Phase 2 product expansion.

### Market value
- **Differentiation:** most tender tools stop at document management; a credible, explainable bid/no-bid recommendation is a wedge into the pre-bid meeting where the MD/owner makes the go/no-go call.
- **Willingness to pay:** the existing pricing tiers are per-tender or per-seat. Bid Decision Intelligence justifies the paid tier by turning risk data into a management decision artifact.
- **Data moat:** structured review outcomes, false-positive flags, and org-standard violations become the feedback loop that improves the rule-packs and the score over time.
- **India-first, GCC/UK later:** all features should work with the existing `in-works` India pack and layered `notice_standards` (`base` + `india`) before regional overlays for GCC/UK.

---

## 3. Feature definitions & module mapping

| # | Feature | ID | What it does | Natural owner | Soft deps | Outcome artifact |
|---|---------|----|--------------|---------------|-----------|------------------|
| 1 | **Bid / No-Bid Recommendation** | TS-048 | Compute a structured Bid Readiness Score from accepted findings, qualification status, deadline pressure, and org-standard violations; present strengths, concerns, and conditional recommendations. | `drafting` (new artifact kind `bid_decision`) | `findings`, `review`, `boq`, `ingestion`, `rulepacks`, `standards` | `bid_decision` artifact (JSON + render to DOCX/PDF) |
| 2 | **Qualification Compliance Matrix** | TS-049 | Extract minimum turnover, experience, equipment, certifications, EMD, bid security, and similar-project requirements; compare against opportunity/org profile; flag gaps. | `qualification` (new module) | `ingestion`, `rulepacks`, `findings` | `qualification_matrix` finding rows + report artifact |
| 3 | **Tender Comparison** | TS-050 | Aggregate risk count, BOQ defect count, bid deadline, qualification status, and confidence for all opportunities in an org; sort/prioritize. | `comparison` (new module) | `findings`, `ingestion`, `review` | Dashboard API + `/opportunities/compare` view |
| 4 | **Clause Change Detection** | TS-051 | When a new version of a document (addendum/corrigendum) is uploaded, diff against the previous version: added/removed/changed clauses and critical terms. | `diff` (new module) or `ingestion` extension | `ingestion` | `document_diff` report + findings |
| 5 | **Tender Timeline** | TS-052 | Expand deadline extraction into a milestone calendar: tender published, pre-bid, clarification cut-off, submission, technical/financial opening, EMD/BG validity, contract signing. | `ingestion` (extended deadline kinds) + `timeline` (new module) | `ingestion`, `baseline` notice register | `/opportunities/{id}/timeline` + iCal/export artifact |
| 6 | **Clause Cross-Reference** | TS-053 | Build a citation graph across documents (NIT → GCC → SCC → addendum → BOQ notes) for a given clause/topic, so users can verify related references quickly. | `crossref` (new module) | `ingestion` (clauses), `findings` | `/opportunities/{id}/crossref?term=...` |
| 7 | **Risk Explainability** | TS-054 | For each finding, surface: matched pattern, verbatim evidence, industry reason, and suggested reviewer, in a structured `explanation` block. | `risk` (extended output) + frontend | `rulepacks`, `findings` | `explanation` field on `Finding` |
| 8 | **Structured Review Outcomes** | TS-055 | Replace coarse `accepted|edited|rejected` with explicit outcomes: `accepted`, `false_positive`, `needs_clarification`; capture rejection reasons for telemetry. | `review` (workflow extension) | `findings` | updated `review_status` + `review_reason` |
| 9 | **Organization Standards Enforcement** | TS-056 | Compare accepted findings and terms against the org's published standards (e.g. "retention never above 5%") and flag `standard_violation` findings. | `standards` (policy check) + `review`/`drafting` | `findings`, `rulepacks`, `standards` | `standard_violation` findings + bid-decision input |
| 10 | **Internal Accuracy Dashboard** | TS-057 | Admin-only metrics: precision/recall, false positives/negatives, most-missed clause types, rule performance, review outcomes by pattern. | `analytics` (new internal module) | `findings`, `review`, `rulepacks` | `/admin/accuracy` API + dashboard |

### Module boundary notes
- **New modules are justified when the feature owns data or a distinct user concern.** `qualification`, `comparison`, `diff`, `crossref`, `analytics` are new. `timeline` is a thin view module because the data (deadlines + notice register) already exists.
- **Feature 1 is intentionally the capstone.** It should be the last implemented because it consumes all the others. The `drafting` spec already anticipates a bid/no-bid score (`specs/modules/drafting.md` B3); TS-048 realizes it.
- **Feature 6 (cross-reference) and 4 (change detection) use fuzzy matching.** They must reuse the existing `verify_quote`/text-normalization utilities or a shared `app.core.text` helper, not duplicate logic.

---

## 4. Prioritization & sequencing

### Must-have for Bid Decision Intelligence to be credible
These are inputs without which the final score would be incomplete:

1. **TS-049 — Qualification Compliance Matrix** (eligibility is a hard go/no-go)
2. **TS-054 — Risk Explainability** (users must trust the score)
3. **TS-055 — Structured Review Outcomes** (score must use refined, not coarse, review data)
4. **TS-056 — Organization Standards Enforcement** (personalized thresholds change the score)
5. **TS-052 — Tender Timeline** (deadline pressure is a major bid/no-bid factor)

### The capstone
6. **TS-048 — Bid / No-Bid Recommendation** (consumes the five above + existing risk/BOQ findings)

### Should-have extensions
7. **TS-053 — Clause Cross-Reference** (increases trust, supports review)
8. **TS-051 — Clause Change Detection** (corrigenda are common in Indian public tenders)

### Portfolio / internal tools
9. **TS-050 — Tender Comparison** (helps allocate effort across multiple tenders)
10. **TS-057 — Internal Accuracy Dashboard** (feeds the rule-pack improvement loop)

### Suggested sprint order
| Sprint | Focus | Tasks | Validation target |
|--------|-------|-------|-------------------|
| 0 | Data quality | TS-054, TS-055 | Reviewers can accept/reject/flag with reasons; every finding shows why it matched. |
| 1 | Eligibility & policy | TS-049, TS-056 | Bid/no-bid score can compute eligibility and org-standard violations. |
| 2 | Capstone decision | TS-048, TS-052 | User can open an opportunity and see Bid Readiness Score + conditional recommendation. |
| 3 | Trust & change | TS-053, TS-051 | Reviewers can cross-reference clauses and see addendum deltas. |
| 4 | Portfolio & ops | TS-050, TS-057 | Management sees tender portfolio priority and rule accuracy metrics. |

**Freeze recommendation:** After TS-048 (and its sprint 0–2 inputs) ship and validate, pause feature expansion. Sprints 3–4 can wait until the Phase 1 accuracy gate is closed.

---

## 5. Acceptance criteria per feature

### TS-048 — Bid / No-Bid Recommendation
- A `bid_decision` artifact can be generated only when `review.gate` is open.
- Score is a deterministic weighted sum over accepted findings; weights are org-editable and stored in `rulepacks/<pack>/playbooks/default_contractor.yaml`.
- The report contains: `Bid Readiness Score (0–100)`, `strengths[]`, `concerns[]`, `recommendation` (proceed / proceed with conditions / do not proceed), and a `conditions[]` list.
- Every concern and condition links to an accepted finding ID and source page.
- The artifact is versioned, passes the three validators (no invented quotes/clauses/numbers), and can be exported as DOCX/PDF/XLSX.
- A unit test proves: identical accepted findings → identical score.

### TS-049 — Qualification Compliance Matrix
- A new `qualification` module publishes `qualification.matrix` capability and writes `Finding` rows of kind `qualification_gap`.
- It extracts at minimum: `minimum_turnover`, `similar_project_experience`, `equipment_requirements`, `engineer_requirements`, `certifications`, `emd_amount`, `bid_security`, `experience_years`.
- Each extracted requirement has `status` (met / not_met / unknown), `evidence` (source page + quote), and `action_required`.
- The matrix is surfaced in the opportunity workbench and feeds the bid/no-bid score.

### TS-050 — Tender Comparison
- `GET /api/comparison/opportunities` returns an array of opportunities with: title, submission_due, risk_count by severity, boq_defect_count, qualification_status, bid_readiness_score, and a `priority_rank`.
- The API is org-scoped and respects review-state gating.
- The frontend `/opportunities/compare` page renders the table and allows sorting.

### TS-051 — Clause Change Detection
- When a document is uploaded with the same `document_type` and a higher version number, `diff` compares extracted clauses to the previous version.
- Output: `added[]`, `removed[]`, `changed[]` with old/new source page and quote.
- Critical terms (payment, LD, escalation, termination, completion period) are highlighted.
- Diffs are stored as a `document_diff` finding/artifact and shown in a "Changes" tab.

### TS-052 — Tender Timeline
- `GET /api/timeline/opportunities/{id}/timeline` returns milestone events with `kind`, `due_at`, `description`, `source_page`, `source_quote`, `confirmed`.
- Kinds include at minimum: `tender_published`, `pre_bid_meeting`, `clarification_cutoff`, `bid_submission`, `technical_opening`, `financial_opening`, `emd_validity`, `bg_submission`, `contract_signing`.
- `GET /api/timeline/opportunities/{id}/timeline.ics` exports the dated milestones to iCal.
- Timeline can also be rendered as a Gantt-like artifact.

### TS-053 — Clause Cross-Reference
- `GET /api/crossref/opportunities/{id}?term=payment` returns a list of `(document_type, clause_ref, page, quote)` matches across all documents for the opportunity.
- Fuzzy matching is used; confidence is shown.
- The feature reuses the existing clause store and does not require a new full-text index for MVP.

### TS-054 — Risk Explainability
- Each `Finding` produced by the `risk` module includes an `explanation` object: `matched_pattern`, `evidence_quote`, `industry_reason`, `suggested_review`.
- The `explanation` is persisted in the `findings` table (new nullable `explanation` JSON column) and rendered on the risk card.
- If `rulepacks` is disabled, the explanation degrades to a generic template.

### TS-055 — Structured Review Outcomes
- `ReviewStatus` enum is extended with `NEEDS_CLARIFICATION` and `FALSE_POSITIVE` (or `rejected` is split with `review_reason`).
- The review endpoint accepts `outcome` and `reason` (e.g. `wrong_clause`, `wrong_severity`, `not_a_risk_here`, `duplicate`, `needs_more_info`).
- The audit log records both fields.
- Review reasons are aggregated by pattern ID for the accuracy dashboard.

### TS-056 — Organization Standards Enforcement
- Org admins can publish numeric/string thresholds in `/standards` (e.g. `max_retention_percent`, `min_payment_days`, `ld_cap_percent`).
- During review and bid-decision generation, `standards` capability `standards.check_violations(findings)` returns `standard_violation` findings.
- Violations cite the org standard and the offending contract term with source page.

### TS-057 — Internal Accuracy Dashboard
- New `analytics` module mounted under `/api/admin/*` and restricted to `admin` role.
- Metrics: `precision` and `recall` (requires gold labels), `false_positive_rate` by pattern, `false_negative_rate` by pattern, `most_missed_clause_types`, `review_outcome_distribution`, `average_review_time`.
- Data is computed from `findings`, `review` audit log, and `rulepacks` pattern metadata.
- No customer data is exposed.

---

## 6. Data-model & contract changes

### Core contracts
- `FindingKind` needs `QUALIFICATION_GAP` and `STANDARD_VIOLATION`.
- `ReviewStatus` needs `NEEDS_CLARIFICATION` and a `review_reason` concept.
- `Finding` needs optional `explanation: dict | None`.

### New tables
- `qualification_checks` (org-scoped) — or write `Finding` rows of kind `qualification_gap`.
- `document_diffs` (org-scoped) — per opportunity, per document pair.
- `crossref_index` (org-scoped) — optional; MVP can query in-memory from `clauses`.
- `analytics_snapshots` (org-scoped, internal) — pre-computed metrics.

### Migrations
Each new table gets its own Alembic migration under `backend/migrations/versions/` and registers `OrgScopedMixin` for RLS.

---

## 7. Out of scope (explicitly preserved)

The following remain outside the product even after these extensions, per the build doc §0.2:

- ERP, project management, BIM, procurement, vendor management, invoice management, construction scheduling, site management, accounting.
- Post-award claim/variation automation (Phase 3).
- Drawing take-off and quantity extraction.
- Live material pricing and cost estimating.
- Legal opinions.

---

## 8. Risks & dependencies

1. **Accuracy gate still blocks trust.** TS-048 amplifies the cost of a wrong recommendation. The score must not ship to paying users until real-tender validation is done.
2. **Weight configuration is a product decision.** Bid/no-bid weights must be editable by org admins and backed by QS input, not hard-coded.
3. **Cross-module feature density.** Several features read `findings`. Keep reads behind the `findings.store_factory` capability; do not import `app.modules.findings` directly.
4. **Frontend surface area grows.** The opportunity workbench will need new tabs: Qualification, Timeline, Cross-Reference, Changes, Comparison, and the Bid Decision card. Consider a small component library soon.
5. **Internal dashboard needs gold labels.** TS-057's precision/recall requires manually labeled real tenders; budget for it in the Phase 1 accuracy work.

---

## 9. Success metrics

- **Adoption:** % of opportunities for which users generate a Bid Decision artifact.
- **Trust:** % of `needs_clarification` findings converted to `accepted` or `false_positive` within one review cycle.
- **Accuracy:** Bid Decision recommendation matches final management bid/no-bid decision in ≥70% of cases on the validation set.
- **Efficiency:** Average time from upload to bid decision < 25 minutes p95 for an 800-page pack + 5k-row BOQ.
- **Rule-pack improvement:** False-positive rate per pattern decreases by ≥10% per month after the accuracy dashboard is live.
