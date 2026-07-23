# Changelog

All notable changes to TenderShield. Updated **every session** with what was
done and what comes next (see `CLAUDE.md` §1.5). Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); task IDs reference `tasks/backlog.md`.

## [Unreleased]

### Done — 2026-07-23 (session 10: review workbench + audit + export gate)

- **TS-021** — `review` module, the professional-liability spine (Doc §11.4):
  - accept/edit/reject each finding — updates the review columns via the
    findings store capability (never imports findings); requires `reviewer`
    role; bad decision → 400, unknown finding → 404.
  - append-only `audit_log` table + migration `0006` (org-scoped, RLS on
    Postgres; 0001→0006 verified up+down); every decision writes an audit row.
  - **export gate**: `review.gate` returns `export_allowed` only when there are
    findings and none remain `proposed` — the block that stops export before a
    human has reviewed. Published as `review.service_factory` for drafting/export.
  - `GET queue` / `POST findings/{id}` / `GET gate` / `GET audit` endpoints.
  - **Frontend:** Risks tab now shows an export-gate banner and Accept/Reject
    buttons per finding; reviewed findings show their status.
  - Note: `BigInteger` PK uses a SQLite `Integer` variant so autoincrement works
    in tests while staying BIGSERIAL on Postgres.

Test suite: 68 passing, ruff clean; frontend builds clean.

### Done — 2026-07-23 (session 9: findings persistence)

- **TS-013a (findings slice)** — a new pluggable `findings` module owns the
  shared `findings` table (Doc §3.2): SQLAlchemy model + migration `0005`
  (org-scoped, RLS on Postgres; 0001→0005 verified up+down) + `FindingStore`.
  - Producers write via the `findings.store_factory` capability, scoped by a
    `producer` column so a re-run of one producer replaces only its own rows and
    never disturbs another's (unit-tested for idempotency + producer isolation).
  - `risk` now persists its findings on run (still returns them too) and gained
    `findings` as a soft dep — resolved lazily, so risk still runs (in-memory)
    if the findings module is disabled.
  - `GET /api/findings/opportunities/{id}` lists the register, severity-sorted.
  - **Frontend:** the Risks tab now reads the persisted register (with
    review-status), loaded on open and after a run.
  - No module imports another's models — the table stays pluggable behind the
    store capability + the core `Finding` contract.

Test suite: 65 passing, ruff clean; frontend builds clean.

### Done — 2026-07-23 (session 8: deadline extraction + deadline wall)

- **TS-015** — deadline extraction (Doc §6.2), the <3-minute promise:
  - pure `deadlines.py` — deterministic date parsing (DD/MM/YYYY, "15 Aug 2026",
    etc.) with keyword→kind classification (submission/pre-bid/clarification/
    validity/EMD/completion), `[pN]` page tracking, and noise control (bare
    dates with no deadline keyword are skipped). Dates are never invented; each
    carries its verbatim source line + page. LLM/relative-formula resolution are
    follow-ups — the deterministic pass already lights up the wall with no key.
  - `Deadline` model + migration `0004` (org-scoped, RLS on Postgres); also adds
    `submission_due`/`clarification_due` to `opportunities`. 0001→0004 verified.
  - extraction runs on document upload; sets the opportunity's `submission_due`
    from the earliest submission date; `GET …/deadlines` + confirm-chip endpoint.
  - **Frontend:** deadline wall on the opportunity overview (countdown colouring
    red<3d/amber<7d, page citations, confirm chips) and the board countdown
    badge now lights up from `submission_due`.
  - Verified full-stack live: uploading a NIT extracted bid submission (2d, red),
    pre-bid and clarification (1d) with page citations; board shows "2d to
    submission" in red. Screenshots captured.

Test suite: 62 passing, ruff clean; frontend builds clean.

### Done — 2026-07-23 (session 7: frontend skeleton — the UI)

- **TS-025** — Next.js 15 + TypeScript + Tailwind app (`frontend/`), Doc §9:
  - landing page (countdown-wall design + sample risk register), auth
    (signup/login), opportunity **board** (countdown badges: red <3d, amber <7d),
    and opportunity **detail** (document checklist + risk workbench tabs);
  - typed API client (`lib/api.ts`), session context (access token in memory +
    localStorage mirror; production uses httpOnly refresh cookie per Doc §5);
  - tri-state provenance badges (extracted fact / deterministic check / AI
    suggestion) as components, not copy (Doc §11.4);
  - `next build` clean (6 routes); bumped Next to 15.5.x (patched CVE).
- **Backend for the SPA:** `GET /api/ingestion/opportunities` (org-scoped list)
  + CORS middleware (`TS_CORS_ORIGINS`, configurable).
- **Verified full-stack, live:** ran FastAPI + Next together and drove a real
  signup → create two opportunities → upload a document flow with a headless
  browser. Screenshots captured: the uploaded doc classified as NIT and the
  missing-doc checklist flagged GCC/BOQ — all through the real API with RLS
  org-scoping (a second org's board is isolated, covered by a new test).

Test suite: 58 passing, ruff clean. Frontend builds clean.

### Done — 2026-07-23 (session 6: clause segmentation + risk engine)

- **TS-016** — clause segmentation (extends ingestion): pure `segment.py`
  (`segment_clauses` — header detection for Clause/GCC/SCC, `[pN]` page
  tracking, cross-ref extraction), `Clause` model + migration `0003_clauses`
  (org-scoped, RLS on Postgres; 0001→0002→0003 chain verified up+down).
  Documents are segmented on registration; `GET …/clauses` lists them.
- **TS-017** — `risk` module, the pattern engine (Doc §6.3):
  - `severity.py` — **deterministic** severity via a sandboxed AST evaluator
    over the pack's `severity_rule` strings (severity keywords resolve to
    themselves, facts from context, missing → 0, malformed → safe default).
    Severity never comes from the LLM.
  - `engine.py` — anchor retrieval, quote verification (normalized + fuzzy
    ≥0.85), absence detection, finding assembly. Pure over dicts.
  - `classifier.py` — injected LLM boundary: `NullClassifier` (no key → absence
    detection still works) / `AnthropicClassifier` (JSON-only, temp 0, tender
    text as untrusted data). Never returns severity.
  - `RiskService` consumes ingestion + rulepacks purely via registry
    capabilities; `POST /api/risk/opportunities/{id}/run`.
  - **Ran live** on the synthetic tender: correct deterministic severities
    (LD/escalation/termination critical, defect high), quotes verified against
    clause text, and a deliberately-wrong quote flagged unverified.
  - Fixed the synthetic payment clause to 120 days (unambiguous `high`); the
    "is 90 days high or medium?" boundary is a QS-validation calibration item.

Test suite: 57 passing, ruff clean.

### Done — 2026-07-23 (session 5: ingestion module + auth boundary hardening)

- **Auth boundary refactor** — the generic request dependencies (`get_session`,
  `current_principal`, `require`) moved to `app/core/deps.py`, which resolves
  auth purely by capability name. Auth now publishes a plain
  `auth.authenticate(request, session)` + `auth.check_role` (instead of
  Depends-wrapped internals). Result: any module gets auth+RBAC+RLS without
  importing auth; auth's own router consumes the same core deps. 43→still green.
- **TS-014** — `ingestion` module, the opportunity aggregate owner:
  - pure `classify.py` (`classify_text` rules-first anchors, `missing_documents`)
    with DB-free unit tests;
  - `Opportunity` + `Document` models (org-scoped, RLS) + migration
    `0002_ingestion_tables` (RLS emitted on PostgreSQL only; up/down verified on
    the 0001→0002 chain);
  - `IngestionService`: create opportunity, classify+register document,
    missing-doc checklist — all scoped by `org_id` (defense-in-depth with RLS),
    consuming `rulepacks.loader` as a lazy soft dep with built-in fallback
    anchors;
  - routes under `/api/ingestion/opportunities`, auth-gated via `core.deps`.
  - First real cross-module consumer: ingestion uses auth through the registry,
    proven by an org-isolation test (org B gets 404 on org A's opportunity) and
    a soft-dep test (works with rulepacks disabled).

Test suite: 49 passing, ruff clean.

### Done — 2026-07-23 (session 4: auth module)

- **TS-011 / TS-012** — `auth` module (Doc §5), built for isolated testing +
  refactoring:
  - **Pure security primitives** (`security.py`): argon2id hashing, RS256 JWT
    mint/decode with `kid`, ephemeral-keypair generation for dev. `refresh.py`:
    token generation + `evaluate_refresh()` (the reuse-detection *verdict* as a
    DB-free pure function). `rbac.py`: roles + `role_at_least`. All covered by
    `test_auth_security.py` with **no DB and no FastAPI** — rewritable in place.
  - **Module internals** (`models.py`, `service.py`, `deps.py`, `router.py`):
    signup/login/refresh/logout/me/add-member; rotating refresh with
    whole-family revocation on replay; RBAC guard; per-request RLS binding
    (`bind_org_context`). Only capabilities (`auth.current_principal`,
    `auth.require`, `auth.keys`) are exposed — consumers never import internals.
  - **TS-013a (auth slice)** — first real Alembic migration `0001_auth_tables`
    (orgs, users, org_members, refresh_tokens), portable across SQLite/Postgres;
    verified up + down.
- Ruff configured for FastAPI's `Depends`-in-defaults idiom; email fields kept
  as plain `str` to avoid an extra dependency.

Test suite: 43 passing, ruff clean. Added argon2-cffi + PyJWT[crypto].

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

- **TS-020** — drafting: clarification letter + assumptions register from
  ACCEPTED findings (gated by `review.gate`), with the three validators (no
  invented quotes/clauses/numbers) — the artifact a contractor exports.
- **TS-023** — export renderer (DOCX/PDF/XLSX) with the reviewer/date/pack stamp;
  blocked by the export gate until review completes.
- **BOQ write-through** — wire the BOQ engine to an opportunity's uploaded BOQ
  (parse workbook → items) and persist its defects via `findings.store` too.
- Review follow-ups (Doc §11.4): single-member full-screen attestation,
  multi-reviewer approval chain.
- Ingestion follow-ups (Doc §6.2): relative-date formula resolution
  ("21 days from pre-bid") and LLM-assisted extraction for scanned/messy packs.
- Frontend follow-ups: BOQ tab, PDF.js source-page view, shadcn polish, a
  frontend lint/build step in CI.
- With `ANTHROPIC_API_KEY` set on the server, the risk engine's LLM classifier
  activates automatically and the Risks tab populates; without it, absence
  detection still runs. Same key runs the Week-2 accuracy harness.
- Decision still open for founder: collect the 5 real tenders + gold answers
  for the Week-2 accuracy test (Doc §19.2) — code can't substitute for these.
