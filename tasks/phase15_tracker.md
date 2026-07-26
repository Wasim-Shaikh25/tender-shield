# Phase 1.5 Extensions — Progress Tracker

Source requirements: `docs/TenderShield_Phase15_Extensions.md`  
Goal: extend the pre-bid workflow from risk surfacing to a defensible bid/no-bid decision, then freeze feature expansion.

## Sprint map

| Sprint | Theme | Tasks | Status |
|--------|-------|-------|--------|
| 0 | Data quality | TS-054 Risk Explainability, TS-055 Structured Review Outcomes | done |
| 1 | Eligibility & policy | TS-049 Qualification Matrix, TS-056 Org Standards Enforcement | in-progress |
| 2 | Bid decision capstone | TS-048 Bid/No-Bid Recommendation, TS-052 Tender Timeline | in-progress |
| 3 | Trust & change | TS-053 Clause Cross-Reference, TS-051 Clause Change Detection | todo |
| 4 | Portfolio & ops | TS-050 Tender Comparison, TS-057 Internal Accuracy Dashboard | todo |

## Feature tracker

| ID | Feature | Module(s) | Priority | Status | Acceptance Gate | Blockers |
|----|---------|-----------|----------|--------|-----------------|----------|
| TS-048 | Bid / No-Bid Recommendation | `drafting` | P0 — capstone | todo | Score is deterministic, org-editable weights, cites accepted findings, gated by review | TS-049, TS-054, TS-055, TS-056, TS-052 |
| TS-049 | Qualification Compliance Matrix | `qualification` (new) | P0 — input | done | Extracts ≥8 requirement types, writes `qualification_gap` findings, feeds bid score | rulepack patterns for qualification |
| TS-050 | Tender Comparison | `comparison` (new) | P2 | todo | `/opportunities/compare` API + page, priority rank | TS-048 (score useful) |
| TS-051 | Clause Change Detection | `diff` (new) or `ingestion` | P2 | todo | Added/removed/changed clauses for new document versions | document versioning in `ingestion` |
| TS-052 | Tender Timeline | `ingestion` + `timeline` (new) | P0 — input | done | ≥9 milestone kinds, timeline view/export | existing deadline extraction |
| TS-053 | Clause Cross-Reference | `crossref` (new) | P2 | todo | Cross-document term search with confidence | clause store |
| TS-054 | Risk Explainability | `risk` + frontend | P0 — input | done | `explanation` object on every finding, rendered in UI | core `Finding` contract change |
| TS-055 | Structured Review Outcomes | `review` | P0 — input | done | New `NEEDS_CLARIFICATION`/`FALSE_POSITIVE` states, rejection reasons, audit logging | core `ReviewStatus` change |
| TS-056 | Organization Standards Enforcement | `standards` + `review`/`drafting` | P0 — input | todo | Org thresholds → `standard_violation` findings, used by bid score | TS-047 org standards editor |
| TS-057 | Internal Accuracy Dashboard | `analytics` (new) | P3 | todo | Admin-only precision/recall/FP/FN by pattern | real-tender gold labels |

## Definition of done for Phase 1.5

- [ ] Sprint 0 complete and tests passing.
- [ ] Sprint 1 complete and at least one real tender validated for qualification extraction.
- [ ] Sprint 2 complete; Bid Decision artifact generated end-to-end in the UI.
- [ ] QS review confirms the score factors and weights are commercially reasonable.
- [ ] Phase 1 accuracy gate remains open until the validation set passes ≥70% QS acceptance.
