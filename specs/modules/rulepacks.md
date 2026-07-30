# Rule-Packs — Spec

**Status:** implemented (scaffold + Phase-0 patterns)
**Requirement refs:** Doc §2, §14
**Task refs:** TS-007, TS-008, TS-009, TS-046

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
  as reliable unless `TS_BETA_UNVALIDATED=true` is set; `unvalidated` patterns are
  hidden by default from paying workspaces, or shown with a clear `disclaimer`
  when the beta flag is enabled (Doc §14.3).
- **B3 (versioning):** packs carry `effective_from/to`; generated artifacts embed
  `pack: <id>@<version>`; findings store `pattern_id` + `pattern_version` (Doc §2.4).
- **B4 (governance):** every pack change = PR + golden-tender tests + named
  domain-reviewer sign-off recorded in `pack.yaml` (Doc §2.4).
- **B5 (unit canon):** BOQ normalization map handles real Indian unit chaos
  (`Cum/cum/m3/CuM/M³`, `Rmt/RM/m`, `MT/tonne/Ton`, `Sqm/m2/SqM`) (Doc §2.1).
- **B6 (loader safety):** loader validates YAML against Pydantic schemas at load;
  a malformed pattern is skipped with an error, never crashes the app.
- **B7 (layered standards — universal-first):** notice standards live under
  `notice_standards/*.yaml`, each with a `scope` (`universal` or a region code
  like `IN`). `RulePackLoader.notice_standard(pack_id, region)` returns the
  **universal base with the regional overlay merged on top**: a regional
  category overrides the base category with the same `key` **only in the fields
  it explicitly sets** (`exclude_unset` — an omitted field keeps the base
  value), and region-only categories are appended. This is the flexibility
  mechanism the whole geographic roadmap rides on — adding a market or an
  unexpected clause type is a new YAML file, never a code change. Each category
  carries `expected` (whether a well-formed contract should include the regime),
  `typical_days`, and matching `keywords`; `source` + `confidence` remain
  mandatory (B1/B2 apply).

## Acceptance criteria

- A1: loader parses `in-works` pack; malformed fixture pattern is skipped + logged.
- A2: the 5 Phase-0 patterns (payment_terms, price_escalation, liquidated_damages,
  defect_liability, termination) load with `confidence: unvalidated` and `source:`.
- A3: filtering by `confidence` works (`validated_only=True` hides unvalidated).
- A4: `notice_standard("in-works")` returns the universal base; adding region
  `"IN"` tightens the `claim` window (28→15d), appends the India-only
  `escalation` category, and leaves untouched base categories intact (B7).

## Out of scope

`gcc-fidic` and `uk-jct-nec` packs (Phases 4–5) — but B7's layering is exactly
the seam they plug into (a `gcc.yaml`/`uk.yaml` overlay); employer-family
baselines beyond notice standards (P2).
