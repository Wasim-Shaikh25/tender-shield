# Drafting & Export — Spec

**Status:** draft
**Requirement refs:** Doc §6.5, §1.1(6,8), §11.4
**Task refs:** TS-020, TS-023

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
- **B3 (bid/no-bid score):** transparent weighted sum over accepted findings,
  weights org-editable, rendered with its factor table — never an ML black box.
- **B4 (export gating):** export blocked until reviewer completes review (via
  `review.gate`); every export stamps reviewer name, date, pack version.
- **B5 (watermark):** free-tier artifacts watermarked "DRAFT — TenderShield".
- **B6 (formats):** docxtpl (DOCX), WeasyPrint (PDF), openpyxl (XLSX).
- **B7 (immutability):** new generation = new version; approved artifacts are
  never mutated.

## Acceptance criteria

- A1: a draft with an invented quote is rejected by the validator (unit fixture).
- A2: export without completed review returns 403 with gate reason.
- A3: identical accepted findings → identical bid/no-bid score.

## Out of scope

Tone/format variants (P2), white-label (P2), bilingual AR (P4).
