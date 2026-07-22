# Changelog

All notable changes to TenderShield. Updated **every session** with what was
done and what comes next (see `CLAUDE.md` §1.5). Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); task IDs reference `tasks/backlog.md`.

## [Unreleased]

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

- **TS-009** — 3 trade checklists (civil_structure, electrical, hvac) in the
  in-works pack for scope-gap detection.
- **TS-006** — Phase-0 Week-2 accuracy test harness (`scripts/`) + scorecard
  template — the de-risk experiment gating the full build (Doc §19).
- **TS-010** — Eval/golden-set folder scaffold (`evals/in-works/…`).
- **TS-013** — DB foundation (SQLAlchemy 2 + Alembic, canonical data model
  with RLS) — prerequisite for auth (TS-011/012) and ingestion (TS-014).
- Decision needed from founder: collect the 5 real tenders + gold answers for
  the accuracy test (Doc §19.2) — code can't substitute for these inputs.
