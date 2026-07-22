# Rule-Packs — Spec

**Status:** draft
**Requirement refs:** Doc §2, §14
**Task refs:** TS-007, TS-008, TS-009

## Purpose

A rule-pack is **versioned data + code + tests — not prompt text**. It encodes a
jurisdiction's contract knowledge: doc-type schemas, deadline calculators, risk
patterns, playbooks, BOQ canon + checks, trade checklists, artifact templates,
citable references, and golden tests. Launch pack: `in-works` (India works).

## Public interface

- **Capability published:** `rulepacks.loader` — `get_pack(pack_id, version=None)
  -> RulePack`, `list_patterns(pack_id) -> list[RiskPattern]`.
- **Events:** none (pure data provider).
- **Consumers:** `risk` (patterns, playbooks), `boq` (canon map, checks, trade
  checklists), `ingestion` (doc_types, expected-doc set, deadline calculators),
  `drafting` (templates).

## Data owned

`rulepacks/<pack-id>/` file tree per Doc §2 layout (`pack.yaml`, `doc_types.yaml`,
`risk_patterns/*.yaml`, `playbooks/`, `boq/`, `templates/`, `references/`, `tests/`).

## Behavior

- **B1 (pattern shape):** every risk pattern YAML carries `id`, `category`,
  `severity_rule`, `source` (public document + section), `confidence:
  unvalidated|validated`, `default_playbook` (`acceptable` / `flag_when`),
  anchor queries, and judgment-prompt spec (Doc §14.1 example).
- **B2 (validation state):** only `validated` patterns are shown to paying users
  as reliable; `unvalidated` are hidden or badged "beta — unverified" (Doc §14.3).
- **B3 (versioning):** packs carry `effective_from/to`; generated artifacts embed
  `pack: <id>@<version>`; findings store `pattern_id` + `pattern_version` (Doc §2.4).
- **B4 (governance):** every pack change = PR + golden-tender tests + named
  domain-reviewer sign-off recorded in `pack.yaml` (Doc §2.4).
- **B5 (unit canon):** BOQ normalization map handles real Indian unit chaos
  (`Cum/cum/m3/CuM/M³`, `Rmt/RM/m`, `MT/tonne/Ton`, `Sqm/m2/SqM`) (Doc §2.1).
- **B6 (loader safety):** loader validates YAML against Pydantic schemas at load;
  a malformed pattern is skipped with an error, never crashes the app.

## Acceptance criteria

- A1: loader parses `in-works` pack; malformed fixture pattern is skipped + logged.
- A2: the 5 Phase-0 patterns (payment_terms, price_escalation, liquidated_damages,
  defect_liability, termination) load with `confidence: unvalidated` and `source:`.
- A3: filtering by `confidence` works (`validated_only=True` hides unvalidated).

## Out of scope

`gcc-fidic` and `uk-jct-nec` packs (Phases 4–5); employer-family baselines (P2).
