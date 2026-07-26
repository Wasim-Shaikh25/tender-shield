# Drafting & Export — Spec

**Status:** implemented (generation) — clarification letter + assumptions
register + bid/no-bid decision generated from ACCEPTED findings; the three validators
(no invented quotes/clauses/numbers) gate every artifact; versioned, never mutated.
Deterministic assembly (no LLM key needed); LLM polish pass and the file
export renderer done for DOCX + XLSX (TS-023, gated by review + stamped); PDF (reportlab) now included; LLM polish is a follow-up.
**Requirement refs:** Doc §6.5, §1.1(6,8), §11.4, Phase 1.5 doc §5
**Task refs:** TS-020, TS-023, TS-048

## Purpose

Generate the bid-decision artifacts (clarification letter, assumptions &
exclusions register, risk-register export, bid/no-bid score, Bid Review Pack)
from **accepted findings only** — facts injected, prose generated, everything
gated by validators.

## Public interface

- **Capabilities published:** `drafting.generate(opportunity_id, kind)`,
  `drafting.export(artifact_id, format)`.
- **Capabilities consumed (soft):** `rulepacks.loader` (templates),
  `risk.findings` / `boq.items` (accepted findings via registry),
  `review.gate` (export authorization), `billing.metering`.
- **Events emitted:** `artifact.generated`, `artifact.exported`.
- **API routes:** `/api/opportunities/{id}/artifacts` (generate/list/version),
  `/api/artifacts/{id}/export`.

## Data owned

`artifacts` (versioned; `UNIQUE(opportunity_id, kind, version)`; `body` JSONB
with `evidence_refs[]` + `citations[]`; `model_meta`).

## Behavior

- **B1 (fact table is the only source):** quotes/refs/amounts come exclusively
  from the accepted-findings fact table; LLM writes prose around injected facts.
- **B2 (three validators — the spine):** reject drafts containing
  (a) quotes not in the fact table, (b) clause refs not cited, (c) currency
  amounts not matching facts (tol 0.5). Regenerate on failure; hard-fail to
  human review after 2 attempts.
- **B3 (bid/no-bid score):** transparent weighted sum over accepted findings
  (`risk_clause`, `qualification_gap`, `boq_defect`, `standard_violation`); weights
  default to a documented table and can be overridden per rule-pack playbook
  (`default_contractor.bid_decision_weights`) — never an ML black box. Output is
  a `bid_decision` artifact with score (0–100), strengths, concerns, recommendation
  (`proceed` / `proceed_with_conditions` / `do_not_proceed`), and conditions.
- **B4 (bid-decision gating):** a `bid_decision` artifact can only be generated
  when every finding is resolved (no `proposed` or `needs_clarification`).
- **B5 (export gating):** export blocked until reviewer completes review (via
  `review.gate`); every export stamps reviewer name, date, pack version.
- **B6 (watermark):** free-tier artifacts watermarked "DRAFT — TenderShield".
- **B7 (formats):** docxtpl (DOCX), WeasyPrint (PDF), openpyxl (XLSX).
- **B8 (immutability):** new generation = new version; approved artifacts are
  never mutated.

## Acceptance criteria

- A1: a draft with an invented quote is rejected by the validator (unit fixture).
- A2: export without completed review returns 403 with gate reason.
- A3: identical accepted findings → identical bid/no-bid score.
- A4: `bid_decision` generation returns a score between 0 and 100, a recommendation,
  and at least one strength when no critical concerns exist.

## Out of scope

Tone/format variants (P2), white-label (P2), bilingual AR (P4).
