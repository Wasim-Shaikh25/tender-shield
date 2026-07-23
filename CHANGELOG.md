# Changelog

All notable changes to TenderShield. Updated **every session** with what was
done and what comes next (see `CLAUDE.md` §1.5). Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); task IDs reference `tasks/backlog.md`.

## [Unreleased]

### Done — 2026-07-23 (session 3: deterministic BOQ engine + synthetic tender)

- **Synthetic sample tender** (`evals/in-works/sample_tender/`): a hand-written
  fixture with deliberately planted traps — `boq.csv` (9 rows), `conditions.md`
  (5 clause traps + `[pN]` markers), and `gold_answer.yaml` as its own ground
  truth. Lets the pipeline be proven end-to-end without a real tender or API key.
- **TS-018** — `boq` module: deterministic engine (Doc §6.4, zero LLM) —
  `normalize()` (unit-canon folding + `amount_calc`), DuckDB `run_checks()`
  (arithmetic error, blank rate, duplicate, quantity outlier, grand-total /
  carry-forward mismatch). Findings use the new shared `Finding` contract in
  `app/core/contracts/findings.py`, tagged `deterministic_check`.
- **TS-019** — scope-gap engine: `SpecTextIndex` + trade-checklist cross-
  reference; a gap fires only when a spec trigger is present AND no BOQ line
  matches. `boq` consumes `rulepacks.loader` as a lazily-resolved soft dep and
  degrades to built-in defaults when rulepacks is disabled.
- **Ran it live:** the engine catches exactly the planted defects (duplicate ×2,
  arithmetic, blank rate, grand-total) and 5 civil scope gaps with zero false
  positives (waterproofing correctly NOT flagged). `test_boq.py` asserts this
  against the gold answer, including a determinism (identical-rerun) check.
- **Accuracy harness** now accepts `.md`/`.txt` (not just PDF), so the LLM half
  runs on `conditions.md` directly with an API key.

Test suite: 30 passing, ruff clean. pandas + duckdb added.

### Done — 2026-07-22 (session 2: Phase-0 completion + DB foundation)

- **TS-009** — 3 trade checklists (civil_structure, electrical, hvac) for
  scope-gap detection, drafted from public sources with `confidence:
  unvalidated`; loader parses `boq/trade_checklists/*.yaml` into typed schemas.
- **TS-006** — Phase-0 Week-2 accuracy harness (`scripts/phase0_accuracy_test.py`,
  throwaway by design): runs the 5 in-works patterns over tender PDFs at
  temperature 0, verifies every quote verbatim (invented quote → RED_FLAG),
  wraps tender text as untrusted data.
- **TS-010** — Eval golden-set scaffold `evals/in-works/`
  (classification, deadlines, risk_patterns, boq, drafting) + the scored
  pass/fail bar in `scorecard.md` (Doc §19.5, §11.5).
- **TS-013** — DB foundation in `app/core/db.py`: declarative `Base`,
  `OrgScopedMixin` (org_id + RLS self-registration), `TimestampMixin`,
  `rls_statements()`, `bind_org_context()`, engine/session builders published
  as `db.engine`/`db.sessionmaker` registry capabilities. Alembic scaffold with
  pluggable per-module model discovery; CI gains an up/down migration check.
  Per-module models split out to **TS-013a** (land with each module).

Test suite: 23 passing, ruff clean.

### Done — 2026-07-22 (session 1: project bootstrap)

- **TS-001** — Repo bootstrapped: mandatory AI workflow rules for Claude
  (`CLAUDE.md`) and Cursor (`.cursor/rules/` — workflow, architecture,
  specs/tasks conventions); build blueprint v1.0 vendored to
  `docs/TenderShield_Full_Build_Doc.md` as the requirement source of truth.
- **TS-002** — Task backlog `TS-001`–`TS-025` derived from the blueprint
  (bootstrap + Phase 0 + Phase 1, in the doc's value order; Phase 2+ excluded
  by design until gates pass).
- **TS-003** — Spec suite generated in `specs/`: product overview, data-model
  ownership map, Phase-0 accuracy test, frontend, and per-module specs (core,
  rulepacks, auth, ingestion, risk, boq, drafting, review, billing, assistant),
  each citing its build-doc sections and defining capabilities/events.
- **TS-004** — Backend core: pluggable module framework (FastAPI modular
  monolith). `ModuleSpec` plugin contract, fail-isolated loader
  (`TS_ENABLED_MODULES` boots any subset), `ServiceRegistry` + `EventBus` as
  the only cross-module channels, `health` module, and an architecture test
  that fails the build on any hard cross-module import. 13 tests.
- **TS-005** — CI: ruff + pytest on every push (GitHub Actions).
- **TS-007** — `rulepacks/in-works/` scaffold: pack.yaml, doc-type anchors +
  expected-doc set, BOQ unit-canon map + check thresholds, default contractor
  playbook; backend `rulepacks` module with Pydantic-validated loader
  (malformed YAML skipped, never fatal), `validated_only` filter, REST
  endpoints, `rulepacks.loader` capability.
- **TS-008** — First 5 Phase-0 risk patterns from public sources (payment
  terms, price escalation, LD cap, defect liability/retention, termination
  for convenience) — all `confidence: unvalidated` with `source:` citations
  (Doc §14.1). Test suite now 18 passing, ruff clean.

### Next

- **TS-011 / TS-012** — `auth` module: users/orgs/org_members models +
  migration (TS-013a), argon2id passwords, RS256 JWT (15 min) + rotating
  refresh with reuse detection, RBAC guard, and the per-request RLS binding.
- **TS-014** — `ingestion` module: opportunity + document models, resumable
  upload stub, rules-first classification (using the pack's doc-type anchors),
  missing-doc checklist against the pack's expected set.
- **TS-013a (boq slice)** — persist `boq_items` + BOQ `findings` so the engine
  writes through to the DB, not just DataFrames.
- To run the LLM half of the accuracy test: set `ANTHROPIC_API_KEY` and run
  `python scripts/phase0_accuracy_test.py evals/in-works/sample_tender/conditions.md`.
- Decision still open for founder: collect the 5 real tenders + gold answers
  for the Week-2 accuracy test (Doc §19.2) — code can't substitute for these.
