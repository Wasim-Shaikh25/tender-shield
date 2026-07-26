# Risk Engine — Spec

**Status:** implemented — retrieval, deterministic severity, quote verification,
absence detection, explainability (TS-017, TS-054). LLM classifier is injected
(NullClassifier without a key; AnthropicClassifier with one).
**Requirement refs:** Doc §6.3, Phase 1.5 doc §5
**Task refs:** TS-017, TS-054

## Purpose

Run rule-pack risk patterns against an opportunity's clauses: retrieval →
bounded LLM classification → verification gates → `findings` rows with exact
provenance and deterministic severity.

## Public interface

- **Capabilities published:** `risk.findings` (query findings for an opportunity),
  `risk.run` (trigger pattern run).
- **Capabilities consumed (soft):** `rulepacks.loader`, `ingestion.clauses`,
  `ingestion.doc_text`.
- **Events emitted:** `finding.created`, `risk.run_completed`.
- **Events consumed:** `clauses.segmented` (auto-start pattern runs).
- **API routes:** `/api/opportunities/{id}/findings` (filter by kind/category/severity).

## Data owned

`findings` rows with `kind='risk_clause' | 'missing_doc'` (shape from core contracts).

## Behavior

- **B1 (one pattern = one judgment):** per pattern, retrieve ≤k candidate clauses
  (hybrid anchors + embeddings), classify against pattern spec + org playbook at
  temperature 0 — never "find all risks in 800 pages".
- **B2 (deterministic severity):** severity computed by the pattern's
  `severity_rule` code, never by LLM output. Identical tenders score identically.
- **B3 (absence detection first-class):** zero candidates → evaluate the
  pattern's absence finding (e.g. "no escalation clause at all").
- **B4 (verification gate):** every finding's quote verified verbatim on the
  cited page before persisting; unverifiable → confidence-low, never silent.
- **B5 (traceability):** findings store `pattern_id` + `pattern_version`.
- **B8 (explainability):** every `risk_clause` finding carries an `explanation`
  object: matched pattern (id/title/category), evidence quote, industry reason,
  and suggested reviewer. Pattern YAML may include `industry_reason`; otherwise a
  safe default is used.
- **B6 (playbook comparison):** deviation measured against org playbook override,
  else pack default, keyed by employer family.
- **B7 (validation display rule):** unvalidated-pattern findings are excluded or
  badged per rulepacks B2.

## Acceptance criteria

- A1: severity for a capless-LD fixture is `critical` regardless of LLM text.
- A2: absence finding fires when no escalation clause matches on a >18-month fixture.
- A3: a finding whose quote fails verification persists as low-confidence.
- A4: every risk finding returned by `run_pattern` includes a non-null
  `explanation` with `matched_pattern.id` equal to the pattern id.

## Out of scope

Full taxonomy beyond top-25 (P2), custom playbook UI (P2), cross-tender analytics (P3).
