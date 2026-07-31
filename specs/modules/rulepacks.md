# Rule-Packs — Spec

**Status:** implemented (scaffold + Phase-0 patterns + pack SDK + domain-ladder Rung 1)
**Requirement refs:** Doc §2, §14; `docs/TenderShield_Market_Strategy_2026.md` §C.2, §C.4, §D.2, §D.4
**Task refs:** TS-007, TS-008, TS-009, TS-046, TS-202, TS-204, TS-220, TS-221

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
- **B8 (price impact — TS-202):** a risk pattern may carry an optional
  `price_impact` block (`basis`, `formula`, `inputs`, `confidence`). `formula`
  names a versioned pure function in `app.modules.pricing.formulas` — never
  free-form code, never itself LLM-computed. See `specs/modules/pricing-intel.md`.
- **B9 (rate schedules — TS-204):** `rulepacks/<pack>/rates/<authority>/<year>.yaml`
  loads into `RulePack.rate_schedules`, keyed `"<authority>/<year>"`. Ships
  **empty by design** in `in-works` — a Schedule-of-Rates is authoritative
  regulatory data; see `rulepacks/in-works/rates/README.md` for why none is
  checked in yet, and why an empty/missing directory is a valid, error-free state.
- **B10 (domain ladder — TS-221):** `trade_checklists/` holds one YAML per trade
  with zero code required to add one (Strategy §D.2 Rung 1). `in-works` currently
  carries 7: `civil_structure`, `electrical`, `hvac` (Phase 0) plus `plumbing`,
  `fire_fighting`, `structural_steel`, `lifts` (Rung 1, TS-221). Rung 2
  (supply-and-erection patterns, TS-222) is explicitly gated on a paying customer
  asking (Strategy §D.2) and is deliberately not built yet — adding it before
  that signal would be the scope reflex the roadmap warns against
  (Build Doc §12.6).

## Pack SDK (TS-220)

Strategy §D.4: "schema + validator + test harness so a QS consultancy can write and verify a
pack" — the distribution mechanism that turns domain-agnosticism into a marketplace rather than
requiring every pack to be authored in-house.

Implemented in `backend/app/packsdk/` (outside `app/modules/` — tooling for pack authors, not a
product feature, matching `evalcorpus`/`evalinvariants`/`evalrunner`):

- **Schema** is not duplicated: the Pydantic models in `app.modules.rulepacks.schemas` **are** the
  schema, for both the product and any third party. `validate_pack()` reuses `RulePackLoader`
  itself so there is exactly one definition of "valid."
- **`validate.py`** adds lint rules the loader deliberately does not enforce, because production
  optimizes for graceful degradation (skip a bad file, keep booting) where pre-publish validation
  should instead fail loudly: empty `source`, a `severity_rule` that isn't valid expression syntax,
  duplicate pattern/checklist ids across files (which the loader's dict cache would otherwise
  silently overwrite), duplicate checklist item keys, an `id` mismatch between `pack.yaml` and the
  directory name, and a `price_impact.formula` that isn't registered (warning, not an error — a
  third-party pack may ship its own formula).
- **`packtest.py`** is a **deterministic** test harness: BOQ scope-gap / trade-checklist matching
  (`app.modules.boq.engine.scope_gaps`) is pure Python with no LLM call, so a pack author writes
  test cases — `<pack>/tests/scope_gaps/*.yaml`: spec text, BOQ rows, `expect_gap_keys` and
  `expect_no_gap_keys` — and verifies them fully offline, no API key. Risk-pattern *judgment*
  (does this clause text match this pattern?) is LLM-graded and cannot be verified this way; that
  half is what `specs/eval-at-scale.md` exists for, against real documents at scale.
- **CLIs:** `scripts/pack_validate.py --pack-dir <path>`, `scripts/pack_test.py --pack-dir <path>`.
- **The acceptance gate proven directly:** `evals/pack-sdk-example/` is a complete, self-contained,
  third-party-style pack (one pattern, one trade checklist, one deterministic test case) that both
  CLIs validate and test cleanly — see `backend/tests/test_packsdk.py`.

## Acceptance criteria

- A1: loader parses `in-works` pack; malformed fixture pattern is skipped + logged.
- A2: the 5 Phase-0 patterns (payment_terms, price_escalation, liquidated_damages,
  defect_liability, termination) load with `confidence: unvalidated` and `source:`.
- A3: filtering by `confidence` works (`validated_only=True` hides unvalidated).
- A4: `notice_standard("in-works")` returns the universal base; adding region
  `"IN"` tightens the `claim` window (28→15d), appends the India-only
  `escalation` category, and leaves untouched base categories intact (B7).
- A5: `validate_pack()` passes cleanly on both `rulepacks/in-works` and
  `evals/pack-sdk-example`, and catches each lint rule on a deliberately broken
  fixture (missing source, bad severity rule, duplicate id, duplicate item key).
- A6: `run_pack_tests()` passes on `evals/pack-sdk-example`'s one case, and correctly
  fails on a case whose `expect_gap_keys`/`expect_no_gap_keys` don't match reality.

## Out of scope

`gcc-fidic` and `uk-jct-nec` packs (Phases 4–5) — but B7's layering is exactly
the seam they plug into (a `gcc.yaml`/`uk.yaml` overlay); employer-family
baselines beyond notice standards (P2); Rung 2 supply-and-erection patterns
(TS-222, gated on a paying customer asking, Strategy §D.2).
