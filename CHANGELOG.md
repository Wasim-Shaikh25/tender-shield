# Changelog

All notable changes to TenderShield. Updated **every session** with what was
done and what comes next (see `CLAUDE.md` §1.5). Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); task IDs reference `tasks/backlog.md`.

## [Unreleased]

### Done — 2026-07-31 (TS-222: SAE Rung 2 risk patterns)

- **TS-222 supply-and-erection patterns** — five unvalidated risk patterns in
  `rulepacks/in-works/risk_patterns/sae_*.yaml` (customs/GST variation, split
  delivery/erection LD, PG tests, free-issue material, O&M tail); YAML only,
  zero code; customer validation gate unchanged (Strategy §D.2).

Tests: 495 passed / 5 skipped.

### Next

- Phase 17 — TS-235 (baseline spec).

### Done — 2026-07-31 (TS-233 + TS-234: M5 gold set + margin protected metric)

- **TS-233 M5 human gold set** — 50-case manifest under `evals/gold-set/`; `evalgold` scorer +
  `FixtureClassifier` for synthetic fixtures; `scripts/generate_gold_set.py` and
  `scripts/eval_gold_set.py`; scorecard reads `goldset.json` when present.
- **TS-234 North-star metric** — `compute_margin_protected()` over reviewed findings, declined
  exposure, BOQ corrections, and materialized impact; `GET /api/outcomes/metrics/margin-protected`;
  `outcomes.margin_protected` capability.

Tests: 494 passed / 5 skipped.

### Done — 2026-07-31 (TS-228 + TS-232: M3 backtest + CI eval smoke)

- **TS-228 M3 outcome backtest** — `evalbacktest/m3.py` time-split train/test on award
  records; L1 MAPE, bidder-count MAE, award-latency MAE, retender AUC; `scripts/eval_backtest.py`;
  scorecard reads `backtest.json` when present.
- **TS-232 CI gates** — `scripts/eval_ci_smoke.py` (M1 + M4 on smoke slice);
  `--run-m4` on `bulk_eval.py`; backend CI job runs smoke gate; orchestrator tracks `m4_pass_rate`.

Tests: 485 passed / 5 skipped.

### Next

- TS-233 (human gold set), TS-234 (north-star margin metric), TS-222 (gated).

### Done — 2026-07-31 (TS-218 + TS-197: correction loop + P0 harvest adapters)

- **TS-218 correction loop** — `CorrectionProposal` table + migration; aggregates reviewed
  findings by `(pattern_id, employer_family)`; proposes overlays when ≥5 reviews and
  ≥50% false-positive/rejected; admin routes `POST /api/rulepacks/corrections/scan`,
  `GET /api/rulepacks/corrections/proposals`, `POST .../dismiss`; emits
  `pattern.correction_suggested`; never auto-mutates packs.
- **TS-197 P0 harvest adapters** — `cppp` (offline OCDS `--path` + best-effort network
  feed) and `state-nic` (maharashtra/karnataka/gujarat) with legality review in docstrings;
  `--state` CLI flag on `scripts/corpus_harvest.py`.

Tests: 469 passed / 5 skipped.

### Done — 2026-07-31 (TS-225 + TS-227 + TS-229: adapters + M2/M4 eval scoring)

- **TS-225 harvest adapters** — `ocds-registry` and `etimad` with legality review.
- **TS-227 M2** — portal-metadata agreement scoring in `evalmetadata/`.
- **TS-229 M4** — metamorphic order/redundancy checks in `evalmetamorphic/`.

### Done — 2026-07-31 (TS-211–214: express revenue lane)

- **TS-211 server-owned checkout** — `express/prices.py` tier table; `POST
  /api/express/sessions/{token}/checkout` creates provider order via
  `billing.provider_factory`; client `amount_minor` mismatch rejected.
- **TS-212 webhook-only activation** — verified Razorpay/Stripe webhooks with
  `kind: express` activate `ex_purchases`; `GET /api/express/sessions/{token}/report`
  returns locked (402) until activation.
- **TS-213 unreviewed export** — `export_unreviewed()` watermarks DOCX/PDF/XLSX;
  `GET /api/express/sessions/{token}/export?format=` gated on webhook activation;
  pricing-intel artifact kinds excluded; acknowledgment audit logged on session create.
- **TS-214 anti-abuse + retention + claim** — email/IP/teaser rate limits; teaser dedupe
  by document hash; `express.purge_retention` capability; `POST
  /api/express/sessions/{token}/claim` transfers ephemeral workspace to authenticated user.
- **Fix** — SQLite-safe `acknowledgment_version` migration (`b7e4a1c93f20`).

Tests: 457 passed / 5 skipped.

### Done — 2026-07-31 (TS-200/210: employer context + express teaser)

- **TS-200 employer context** — `marketdata.employer_context_for_family` capability;
  findings and risk run responses include optional `employer_context`; new
  `GET /api/marketdata/opportunities/{id}/employer-context` route; degrades
  silently when marketdata disabled or employer family unset.
- **TS-210 express teaser** — `GET /api/express/sessions/{token}/teaser` renders
  deadline wall, missing-doc checklist, severity/category counts, BOQ summary, and
  two cited sample findings; upload pipeline wires ingestion + risk via registry;
  `risk.run_opportunity` capability published; `ex_sessions.opportunity_id` migration.

Tests: 450 passed / 5 skipped.

### Next

- TS-211+ (express checkout/activation) and TS-218 (correction loop).
- TS-197 (P0 harvest adapters).

### Done — 2026-07-31 (TS-198/199: marketdata resolution + aggregates)

Employer Behaviour Graph moves from schema-only to queryable aggregates:

- **TS-198 employer resolution** — `rulepacks/in-works/employer_families.yaml` +
  deterministic `resolution.py` pipeline (honorific strip, abbreviation expand, alias
  match); unresolved buyers stay unresolved; `resolve_tender_buyer` links `md_tenders`
  to `md_employers`.
- **TS-199 aggregates** — `aggregates.py` computes bidder-count percentiles, L1-to-
  estimate, award latency, retender rate, winner HHI; `n ≥ 12` suppression enforced;
  `comparables.py` builds disclosed filter sets; `employer_profile` / comparables /
  benchmark routes return real data when sample size permits.

Tests: 448 passed / 5 skipped.

### Next

- TS-200 (employer context on findings) and TS-197 (P0 harvest adapters).
- TS-210 (express teaser) and TS-218 (correction loop).

### Done — 2026-07-31 (TS-196/209/216/294/295: Phase 16 batch 2)

Five smaller Phase 16 tasks landed together:

- **TS-196 `marketdata` corpus** — `md_employers`, `md_tenders`, `md_awards`, `md_profiles`,
  `md_harvest_runs` tables (non-tenant); `MarketDataStore` with `upsert_tender`/`upsert_award` and
  `award_prefill` capability.
- **TS-209 `express` session lifecycle** — acknowledgment required, ephemeral workspace backing,
  high-entropy tokens, 72h expiry, 25MB pre-buffer upload cap; fixed route shadowing of
  `get_session` dependency.
- **TS-216 `outcomes` prefill** — `GET /api/outcomes/opportunities/{id}?tender_ref=` returns
  one-click-confirm prefill from `marketdata.award_prefill`; manual path unchanged.
- **TS-294 `Finding.document_id`** — migration + risk/qualification writers stamp document scope;
  M1 quote integrity now document-scoped.
- **TS-295 `Finding.currency`** — ISO 4217 column alongside `amount_exposure`; M1 currency check
  enforced when exposure is set.

Migration: `b7e4a1c93f20`. Tests: 441 passed / 5 skipped.

### Next

- TS-210+ (express teaser/checkout) and TS-218 (correction loop).
- TS-197/198/199 (marketdata harvest + employer resolution + aggregates).
- TS-296 (`Finding.facts` + `Opportunity.contract_value_minor`).

### Done — 2026-07-31 (TS-195/208/215: Phase 16 module scaffolds batch)

Three smaller Phase 16 tasks landed together:

- **TS-195 `marketdata`** — ModuleSpec, registry capabilities
  (`employer_profile`, `comparable_awards`, `price_benchmark`), read routes that
  degrade to `insufficient_data` until harvest lands (TS-196+).
- **TS-215 `outcomes`** — `oc_bid_outcomes` + `oc_risk_materialization` tables
  (RLS), record/read API, finding materialization with `outcome.recorded` /
  `outcome.risk_materialized` events; soft-dep on `marketdata` for prefill stub.
- **TS-208 `express`** — `ex_sessions` / `ex_purchases` / `ex_documents` tables
  (RLS), scaffold session create/fetch routes backed by ephemeral workspace id.

Migration: `a3f1c8d92e10`. Tests: `test_marketdata.py`, `test_outcomes.py`,
`test_express.py` (435 passed total).

### Next

- TS-210 (express teaser) and TS-218 (correction loop).
- TS-197/198/199 (marketdata harvest + aggregates).

### Done — 2026-07-31 (TS-219: reproducibility chain on findings)

Strategy §C.7 accountability chain — every finding now pins the versions and hashes
that produced it so deterministic stages can be verified byte-identical on re-run.

- **`backend/app/core/provenance.py`** (new) — `document_set_hash`, `content_hash`,
  `prompt_hash`, `get_engine_version`, and `ProvenanceStamp` helper used by all producers.
- **`findings` schema** — migration `ce0cebf8a285` adds `rulepack_version`, `model_id`,
  `prompt_hash`, `document_hash`, `engine_version` to the shared `findings` table and
  `Finding` contract.
- **Producers stamped** — `risk` (per-pattern `prompt_hash` from the classifier),
  `boq`, `qualification`, and `standards` attach provenance at run time.
- **Tests** — `backend/tests/test_provenance.py` covers persistence, BOQ re-run
  determinism, and additive stamping.

### Next

- TS-215 (`outcomes` module scaffold) and TS-218 (correction loop).
- TS-195 (`marketdata` module scaffold) when Sprint 3 graph work starts.

### Done — 2026-07-31 (Fix: CI broken by two alembic heads after the PR #69 merge)

The merge of PR #69 combined two migration chains that both branched off `5617d7dc8440`
— `06867937ef52` (pricing-intel tables) and `0c2f0e860d39` (chat session opportunity
optional) — leaving two heads. `alembic upgrade head` failed with "Multiple head
revisions are present," breaking both the `backend` job's scratch-DB up/down check and
the `rls-postgres` job's `Migrate` step in CI (run `30646868682` on `dd846e6`).

- Added `backend/migrations/versions/f0d5a28efb7f_merge_pricing_intel_and_assistant_.py`
  via `alembic merge 06867937ef52 0c2f0e860d39` — a no-op merge revision, not a rewrite
  of either existing migration's `down_revision`, since both are already merged/pushed
  history.
- Verified: `alembic heads` reports a single head; `alembic upgrade head` /
  `downgrade base` both clean against a fresh SQLite scratch DB; full backend suite
  still 420 passed / 5 skipped.

### Done — 2026-07-31 (Merge: `claude/product-market-value-bh65yr` → base, TS-195/196 renumbered to TS-297/298)

Merged PR #69 (Phase 16 defensibility/domain-agnosticism/scale-validation work, TS-195–TS-296)
into the base branch. The two branches had independently continued the sequential task-ID
counter from the same point (last shared ID: TS-194), producing a real collision: the base
had assigned TS-195 (workspace-scoped AI Assistant) and TS-196 (CI changelog-check gate) to
two small tasks, while this branch had assigned TS-195–TS-296 to ~102 Phase 16–21 tasks with
extensive internal cross-referencing (tracker dependency graphs, spec `Task refs`, prose
ranges like "TS-195 – TS-233").

- Renumbered the base's two colliding IDs — TS-195 → **TS-297**, TS-196 → **TS-298** — rather
  than touching this branch's large, already-sequenced Phase 16–21 block, since that minimized
  churn (5 files vs. ~71) and preserved the feature-grouped numbering the tracker docs depend on.
- Updated every reference: `tasks/backlog.md` rows, `CHANGELOG.md` entry headings,
  `specs/modules/assistant.md` and `specs/902-changelog-check.md` `Task refs`, and the
  docstring in `scripts/tests/test_check_changelog.py`. The forward-looking "Next: TS-197"
  suggestion (extend the changelog check to enforce Next-section task IDs) is renumbered to
  **TS-299** to keep clear of this branch's real TS-197 (marketdata P0 adapters).
- Resolved textual conflicts in `CHANGELOG.md` and `tasks/backlog.md` (both append-only logs;
  kept both sides' entries). `.github/workflows/ci.yml`, `specs/README.md`, and the
  `assistant` module (models/router/service/tools, migration `0c2f0e860d39`) auto-merged
  cleanly with no conflicts.
- Verified post-merge: `scripts/task_tracker.py --validate` reports 299 unique task IDs, no
  duplicates; full backend suite 420 passed / 5 skipped; `ruff` and `mypy` clean across 193
  files; the new `scripts/tests/test_check_changelog.py` suite (6 cases) passes.

### Done — 2026-07-31 (TS-217: contradiction engine, extends `crossref`)

Strategy §C.5's fact-level contradiction engine: when the same canonical fact is stated
differently across a tender pack's own documents, name which one governs instead of leaving
the user to notice the disagreement themselves.

- **`backend/app/modules/crossref/facts.py`** (new) — deterministic, regex-only extraction
  of six canonical fact types straight from each clause's own stored text: bid validity
  (days), EMD (split into `emd_percent` and `emd_amount_minor` — a percentage-of-cost figure
  and a flat currency amount are not the same quantity and must never be compared), LD rate
  (rate + period, e.g. `"0.5%/week"`), DLP (months), retention (percent), and submission
  datetime (parsed via Python's `date()` constructor; an impossible calendar date like 31 Feb
  is silently skipped, never guessed at). No LLM anywhere in this path (`CLAUDE.md` §4).
- **`backend/app/modules/crossref/contradictions.py`** (new) — groups verified facts by type;
  a type where every instance agrees is not surfaced at all. Before grouping, every fact's
  `source_quote` is re-verified against its own clause's text — a defensive guard against
  extraction/storage corruption, proven by a test that injects a fabricated unverifiable fact
  via monkeypatch and confirms it cannot itself create or resolve a contradiction. When
  values disagree, a document-precedence order names the *governing* instance; both sides
  always keep their own citation. Two instances tied at the same precedence rank (e.g. two
  conflicting clauses within the same GCC) resolve to `governing: null` with an `"ambiguous"`
  reason rather than a guess.
- **Document precedence is rulepack-configurable and employer-family overridable (TS-217's
  explicit requirement).** `rulepacks/in-works/document_precedence.yaml` ships the unvalidated
  default `[addendum, scc, gcc, nit]` with empty `employer_family_overrides` — real
  employer-specific precedence is contractual fact, not something to invent ahead of seeing
  one (same posture as `rulepacks/in-works/rates/README.md`). `RulePackLoader
  .document_precedence(pack_id, employer_family)` resolves it; `rulepacks` is a soft
  dependency of `crossref` (added to its `soft_deps`), degrading to the hardcoded
  `DEFAULT_PRECEDENCE` fallback when the pack or module is absent — never a crash.
- **New endpoint:** `GET /api/crossref/opportunities/{id}/contradictions` — returns the
  precedence order used and, per contradiction, every instance (value, document, clause,
  page, quote) plus the governing one and why.
- **Tests:** `backend/tests/test_crossref_contradictions.py` (new, 17 cases — one extractor
  per fact type, agreement/disagreement/ambiguous-tie/precedence-override/verification-gate
  paths), 4 new `RulePackLoader.document_precedence` cases in `test_rulepacks.py`, 3 new
  API-level cases in `test_crossref.py` (including graceful degradation with `rulepacks`
  disabled).
- `specs/modules/crossref.md` updated with B5–B9 and acceptance criteria A4–A8; out-of-scope
  now names the two follow-ups this deliberately doesn't do yet: persisting contradictions
  into the shared Findings register (blocked on `Finding.document_id`/`Finding.facts`,
  TS-294/295/296) and any fact type beyond the six named in Strategy §C.5.
  `specs/modules/rulepacks.md` gains B11.

Suite: 420 passed, 5 skipped; ruff clean; mypy clean across 193 files.

**Next:** TS-219 (reproducibility chain on `findings`) and TS-215 (outcomes module scaffold)
— re-sequencing note: `phase16_tracker.md`'s own Blockers column lists TS-234 (north-star
metric) as depending on TS-215, so TS-215 needs to land before or alongside TS-234 rather
than after it as originally sequenced.

### Done — 2026-07-31 (TS-220–221: pack SDK + domain-ladder Rung 1)

Turns domain-agnosticism into distribution (Strategy §D.4) — the mechanism that lets a QS
consultancy author and verify a pack without touching TenderShield's own tests or CI, and
proves the engine actually generalizes by shipping four new trades as pure data.

- **`backend/app/packsdk/`** (new package, outside `app/modules/` alongside `evalcorpus`/
  `evalinvariants`/`evalrunner` — tooling for pack authors, not a product feature):
  - `validate.py` — reuses `RulePackLoader` for schema conformance (there is exactly one
    definition of "valid," not a looser third-party one) and adds lint rules production
    deliberately skips for the sake of graceful degradation: empty `source`, a
    `severity_rule` that isn't valid expression syntax, duplicate pattern/checklist ids
    across files (the loader's dict cache silently overwrites these rather than erroring),
    duplicate checklist item keys, a `pack.yaml` id mismatch, and an unregistered
    `price_impact.formula` (warning, not an error — a third party may ship its own).
  - `packtest.py` — a **deterministic** test harness over BOQ scope-gap / trade-checklist
    matching (pure Python, no LLM call): a pack author writes `<pack>/tests/scope_gaps/*.yaml`
    cases (spec text, BOQ rows, expected gap keys and expected non-gaps) and verifies them
    fully offline. Risk-pattern judgment is LLM-graded and cannot be verified this way — that
    is what the scale-evaluation harness is for.
  - `scripts/pack_validate.py`, `scripts/pack_test.py` — thin CLIs.
- **The acceptance gate proven directly, not asserted:** `evals/pack-sdk-example/` is a
  complete, self-contained, third-party-style pack — one risk pattern, one trade checklist,
  one deterministic test case — and both CLIs validate and test it cleanly on the first run.
  `rulepacks/in-works` also validates cleanly against its own validator.
- **`rulepacks/in-works/boq/trade_checklists/`** gains four Rung-1 trades (Strategy §D.2):
  `plumbing`, `fire_fighting`, `structural_steel`, `lifts` — one YAML each, zero code,
  sourced from CPWD General Specifications, NBC 2016 Parts 4/8/9, IS 800 and IS 14665. Total
  checklists: 3 → 7.
- **Rung 2 (supply-and-erection patterns, TS-222) deliberately not built.** Strategy §D.2
  gates it on a paying customer asking; building it now would be exactly the scope reflex
  Build Doc §12.6 warns against.
- **Tests:** `backend/tests/test_packsdk.py`, 15 cases — both directions per check (a
  well-formed pack passes, a broken one is caught with a specific message), plus the two real
  packs (`in-works`, `pack-sdk-example`) validating and testing clean.
- Two pre-existing tests (`test_rulepacks.py`, `test_boq.py`) asserted the old 3-checklist set
  as exhaustive; updated to the new 7 — an expected consequence of a real expansion, not a
  regression.
- `specs/modules/rulepacks.md` updated with B8–B10 (price impact, rate schedules, domain
  ladder — all three touched this pack in TS-202/204/221 without the spec being updated at
  the time) and the pack SDK section.

Suite: 398 passed, 5 skipped; ruff clean; mypy clean across 191 files.

**Next:** continuing the buildable-now list — TS-217/219/234 (contradiction engine,
reproducibility chain, north-star metric) next.

### Done — 2026-07-31 (TS-201–207: `pricing` module — risk-to-price, rate benchmark, cashflow)

The bridge from "here is your risk register" to "here is what it does to your bid" — the
highest-liability module in the product, and the first Phase 16 work outside the eval
harness. Deterministic arithmetic over verified facts, never LLM (`CLAUDE.md` §4).

- **Package is `app/modules/pricing/`**, not `pricing_intel`/`pricing-intel` as earlier
  specced: `app/main.py` enforces `route prefix == package name == ModuleSpec.name`, and
  neither survives that. `pricing` matches the spec's stated `/api/pricing/...` routes
  exactly.
- **`formulas.py`** — named, versioned, pure loading formulas (`escalation_unhedged`,
  `ld_exposure_cap`, `payment_delay_financing_cost`), each raising `MissingInputs` rather
  than guessing. `ld_exposure_cap` deliberately requires an explicit `cap_percent`: an
  uncapped LD clause correctly produces **no loading**, because bounding an unbounded
  exposure would require inventing the number the finding exists to flag.
- **`loading.py`** — `compute_loadings` filters to `review_status == "accepted"` findings
  *inside the engine itself*, not only by caller discipline, so acceptance criterion 8 holds
  regardless of caller.
- **`benchmark.py`** — two-band Schedule-of-Rates matching (code vs description), headline
  variance computed from code matches only, unmatched rows reported, never force-matched.
- **`cashflow.py`** — monthly working-capital model; every substituted default (even
  billing, 30-day payment assumption, 0% retention, ...) is recorded in `assumptions[]`,
  never silent.
- **Two known schema gaps found while implementing, filed rather than worked around:**
  neither `Finding` nor `Opportunity` persists the structured facts or contract value a
  loading needs, so the engine takes them as explicit caller-supplied inputs today (filed
  as **TS-296**, alongside the equivalent TS-294/295 gaps from `evalinvariants`); and
  `rulepacks/in-works/rates/` ships **intentionally empty** — a Schedule-of-Rates is
  authoritative regulatory data, and fabricating even a plausible-looking rate would violate
  the product's own "numbers never invented" invariant. Its README explains exactly what a
  real entry looks like and why none is checked in yet.
- **`app/modules/boq/service.py`** gained one method, `normalize_dataframe` — the
  normalization half of `check_dataframe` split out so `pricing` consumes normalized BOQ
  rows via the already-published `boq.engine` capability, no new registry entry, no
  cross-module import.
- Rulepack schema: `PriceImpact` on `RiskPattern`, `RateSchedule`/`RateScheduleItem`,
  `RulePack.rate_schedules` loaded from `rulepacks/<pack>/rates/<authority>/<year>.yaml`.
  Added worked-example `price_impact` blocks to `price_escalation_barred` and
  `liquidated_damages_uncapped` (the spec's own example pattern and one more).
- Migration `06867937ef52` for `pi_loadings`/`pi_rate_matches`/`pi_cashflow_runs` —
  hand-trimmed from autogenerate output, which also picked up unrelated pre-existing SQLite
  index drift on five other tables; that drift was left untouched (each module owns its own
  migrations, `CLAUDE.md` §2). Verified `upgrade head` / `downgrade base` clean from scratch.
- **Tests:** `backend/tests/test_pricing.py`, 31 cases — worked examples per formula,
  missing-input honesty, determinism, the two-band match split, the assumptions-block
  guarantee, a static AST scan proving the module imports no LLM client, and full
  end-to-end coverage of the review-export gate (`409 review_incomplete`) through the real
  router using the same NullClassifier absence-finding pattern as `test_export.py`.

Suite: 383 passed, 5 skipped; ruff clean; mypy clean across 188 files (fresh cache).

**Next:** continuing the buildable-now list — TS-220–222 (pack SDK + trade ladder) or
TS-217/219/234 (contradiction engine, reproducibility chain, north-star metric) next.

### Done — 2026-07-31 (TS-231: scorecard + regression diff)

Turns `results.jsonl` into the human-readable report the eval harness's whole premise
depends on.

- **`app/evalrunner/report.py`** (new):
  - `compute_metrics(run)` computes every metric the harness currently has data for: M1
    pass rate, quote-verbatim rate, citation-completeness rate (each derived **per-tender**
    from that tender's own `m1_summary`, not from aggregate violation counts — a pass rate
    needs to know how many *tenders* had a violation, not how many violations existed),
    crash rate (parse/OCR/timeout/unknown, explicitly excluding `invariant_violation` — an
    M1 failure is a graded outcome, not a crash), and findings/wall-clock/cost distributions.
  - **Metrics the harness cannot yet compute (M2/M3/M4/M5) are listed under "Not yet
    available," never approximated.** A fabricated number in the report of a system whose
    entire premise is "no invented numbers" would be the wrong kind of ironic.
  - `find_baseline(runs_root, current)` — the most recent other run on the same corpus root
    and shard; `None` (not an error) for the first run on a slice.
  - `diff_metrics` flags a >2pt drop on the three pass-rate metrics (Build Doc §11.5's bar)
    and a >1pt crash-rate increase; wall-clock/cost are reported for trend visibility but
    not gated, since the spec states an exact threshold only for pass-rate metrics.
- **`scripts/eval_report.py`** — thin CLI; exits 1 when any headline metric regressed.
- **Tests:** `backend/tests/test_evalreport.py`, 26 cases covering metric computation,
  baseline auto-detection (including ignoring a different corpus/shard and the `_cache`
  directory), regression thresholds in both directions, and that M2/M3/M5 metrics are
  structurally absent from `Metrics` rather than faked.
- **Verified against real run data** from the TS-230 CLI smoke test: the first run on a
  corpus+shard correctly reports no baseline; a second run against the same slice
  auto-detects the first and reports no regression.
- `specs/eval-at-scale.md` updated with the implemented interface.

Suite: 352 passed, 5 skipped; ruff clean; mypy clean across 179 files (fresh cache).

**Next:** TS-227 (M2 portal-metadata agreement) continues naturally from this reporting
work. CI wiring (TS-232) is sequenced after TS-227/TS-229 rather than now, so the gate is
wired once with all three modes instead of redone twice.

### Done — 2026-07-31 (TS-230: bulk evaluation runner — Phase 16 Sprint 0 complete)

The piece that turns M1 from "callable on one opportunity" into "runs unattended on
1,000+." Closes Sprint 0 (TS-223, TS-226, TS-230 all done).

- **`backend/app/evalrunner/`** (new package, outside `app/modules/` alongside its two
  siblings — see the spec note below on why this diverges from the section's original
  `app/modules/evalrunner/` placement):
  - `pipeline.py` — `run_tender(record, store, pack=..., classifier=...)` runs one corpus
    tender through the same pure functions the production pipeline uses (`extract_upload`,
    `extract_pages`, `segment_clauses`, `run_patterns`, `normalize`/`run_checks`), grades it
    with `run_m1`, and returns a `TenderResult`. Never raises — every failure is caught and
    tagged (`ocr_failed`/`parse_failed`/`timeout`/`llm_error`/`invariant_violation`/
    `unknown_error`), so a bad tender costs one result line, not the run.
  - `tasks.py` — the Celery task wrapping `run_tender`; eager fallback in `app/core/celery.py`
    means `.delay(...).get(...)` behaves identically in tests/CI and in a real deployment.
    `model_id="none"` (default) always uses `NullClassifier` — a bulk run never silently
    spends on a model unless one was explicitly requested.
  - `orchestrator.py` — `run_batch(...)`: sharding (deterministic `sha256(ocid) % n`),
    per-run resume (skip OCIDs already in `results.jsonl`), cross-run idempotency cache
    (`evals/runs/_cache/`), and a cost guard.
- **A real concurrency bug found and fixed while building the cost guard:** the first
  implementation submitted the whole corpus to the worker pool upfront, then checked the
  budget as results came back — which let a worker start the next tender before the main
  thread had processed the result that tripped the guard, silently defeating the guard
  under any concurrency above 1. Fixed with incremental, bounded dispatch (`_top_up`): work
  is fed one slot at a time as it frees up, so budget is always checked before the next
  dispatch. Caught by `test_run_batch_cost_guard_aborts_cleanly`.
- **A pre-existing CI defect found and fixed, unrelated to this task:** a fresh `mypy`
  invocation (no incremental cache) failed on `Library stubs not installed for "yaml"` in
  `rulepacks/loader.py`. This was masked all session by a stale local `.mypy_cache` and by
  a second, ambient global `mypy` install on PATH that happened to already have the stub;
  CI installs into a single fresh environment and would have hit this on every run. Fixed
  by adding `types-PyYAML` to the `dev` extra in `pyproject.toml`; verified clean with a
  cleared cache via the project's own `.venv/bin/mypy`.
- **Design decisions documented, not left implicit:**
  - No per-tender database session — tenant isolation is already exercised for real by
    `evalinvariants.db_adapter`'s own tests; re-proving it with SQLite on every one of
    1,000 tenders would cost real time for no new evidence.
  - BOQ checking is honest best-effort: the deterministic engine needs an exact canonical
    schema real-world spreadsheets essentially never have as-is (matching the product's
    actual current `boq/router.py` behavior); a non-matching sheet is reported
    `boq_status="not_applicable"`, never coerced into a fabricated result.
- **`scripts/bulk_eval.py`** — thin CLI: `--corpus`, `--run-id`, `--shard i/n`, `--limit`,
  `--force`, `--concurrency`, `--max-total-tokens`, `--max-wall-seconds`. Exits non-zero
  when the graded M1 pass rate is below 100%, so CI can gate on it directly.
- **Tests:** `backend/tests/test_evalrunner.py`, 24 cases — the per-tender pipeline against
  a real harvested corpus (not hand-rolled manifests), every failure classification, and
  the orchestrator's resumability, cross-run cache, sharding, and cost-guard behavior.
- **Verified end-to-end via the CLI**, not only pytest: 5 real harvested tenders processed;
  a second call with the same `--run-id` resumes and skips all 5; a fresh `--run-id`
  against the same corpus reuses all 5 from the cross-run cache; `--shard 0/2` correctly
  selects a disjoint 1-of-5 subset.
- `specs/eval-at-scale.md` updated with the implemented runner architecture and the
  `app/modules/evalrunner/` → `app/evalrunner/` placement decision.

Suite: 326 passed, 5 skipped; ruff clean; mypy clean across 178 files (verified fresh, no
cache) — the yaml-stub fix above.

**Next:** Sprint 0 is complete. TS-224's corpus schema, TS-226's M1 suite and TS-230's
runner are the whole spine of the eval harness — everything from here (TS-227 M2, TS-229
M4, TS-231 report/regression, TS-232 CI gates, TS-225 real network adapters) extends it
rather than needing new architecture. TS-231 (scorecard + regression diff) is the natural
next step: it is what turns `results.jsonl` into the human-readable report the spec's whole
premise depends on.

### Done — 2026-07-31 (TS-226: M1 structural invariant suite — Phase 16 Sprint 0)

The bulletproof test: ten correctness properties that must hold on any tender, needing
zero human labels. `specs/eval-at-scale.md` sets the bar at 100% pass; any violation
blocks release.

- **`backend/app/evalinvariants/`** (new package, outside `app/modules/` for the same
  reason as `evalcorpus` — offline evaluation infrastructure, not a product feature):
  - `bundle.py` — `PipelineBundle`: document pages, findings, generated artifacts, BOQ
    ground truth, an optional rerun for the determinism check, and run metadata (tokens,
    wall time, crash state). Independent of SQLAlchemy so checks are pure and testable
    with synthetic fixtures.
  - `checks.py` — one function per invariant: quote integrity, citation completeness, no
    invented numbers, BOQ arithmetic closure, determinism, currency integrity, tenant
    isolation, graceful degradation, budget, no crash. Each is **independent** of the
    machinery that produced a finding — `check_quote_integrity` re-verifies with a strict
    verbatim substring match against document text, rather than trusting the risk engine's
    own inline fuzzy (0.85-ratio) check, so it can catch a regression there.
  - `runner.py` — `run_m1(bundle) -> M1Result`; `.ok` is the binary pass/fail, `.summary()`
    is JSON-shaped for the report the bulk runner (TS-230) will produce.
  - `db_adapter.py` — `bundle_from_opportunity(session, workspace_id, opportunity_id)`
    builds a bundle from a live opportunity's persisted findings and document chunks,
    entirely workspace-scoped.
- **Verified against the real pipeline, not only synthetic fixtures:** one test runs the
  actual deterministic BOQ engine against `evals/in-works/sample_tender/boq.csv`; another
  runs the actual risk engine end-to-end with a stub classifier. Both pass M1 cleanly —
  the first evidence in this repo that the pipeline satisfies its own invariants.
- **Two real gaps found by writing the checks, not papered over:**
  - `Finding` has `source_page` but no `document_id`, so quote verification checks "does
    this page number, in *any* document attached to the opportunity, contain this quote" —
    correct for one primary document, weaker when two documents share a page number.
    Filed as **TS-294**.
  - `check_currency_integrity` can only assert `amount_exposure` is an integer;
    `Finding` has no `currency` field, so a full currency check isn't yet expressible.
    Filed as **TS-295**, needed before Phase 16 multi-jurisdiction findings can be trusted
    cross-currency (Strategy §E.2).
- **Tests:** `backend/tests/test_evalinvariants.py`, 52 cases — two per check (a legitimate
  case that must pass, proving no false positives on real pipeline shapes; a violating case
  that must fail, proving the check actually catches the defect), plus runner aggregation,
  the two real-pipeline integration tests, and DB-adapter tests including workspace scoping.
- `specs/eval-at-scale.md` updated with the implemented module layout and both discovered
  gaps; `tasks/backlog.md` gains TS-294/TS-295 under a new Phase 16 §16.J.

Suite: 302 passed, 5 skipped; ruff and mypy clean across 174 files.

**Next:** TS-230 (bulk runner — Celery fan-out, disposable workspace per tender,
checkpoint/resume, cost guard) is what turns this from "callable on one opportunity" into
"runs unattended on 1,000." TS-227 (M2 portal-metadata agreement) and TS-229 (M4
metamorphic checks) can proceed in parallel since they don't depend on the runner.

### Done — 2026-07-31 (TS-224: evaluation corpus schema + harvester — Phase 16 Sprint 1)

The foundation the whole scale-evaluation plan sits on: a country-agnostic corpus of
public tender records with full provenance.

- **`backend/app/evalcorpus/`** (new package, outside `app/modules/` — offline evaluation
  infrastructure, not a product feature; nothing in the request path imports it):
  - `models.py` — OCDS-shaped `CorpusTender`, `CorpusDocument`, `CorpusAward`, `Buyer`,
    `Provenance`. Normalizing to the Open Contracting Data Standard is what makes the
    corpus country-agnostic: adapters differ, the schema does not.
    - **Money in minor units** (`CLAUDE.md` §4): OCDS quotes major-unit decimals, so
      conversion happens once at the boundary with a per-currency exponent table
      (0 for JPY/KRW, 3 for KWD/BHD/OMR, 2 default). A missing amount maps to `None`,
      never `0` — "no value published" and "worth nothing" are different facts.
    - `document_set_hash` counts only *fetched* documents, so a partially harvested tender
      cannot masquerade as complete in the runner's cache key.
  - `adapters.py` — the `fetch_index` / `fetch_documents` / `fetch_awards` contract, plus
    `AdapterInfo` carrying the **legality review** (terms of use, official API, rate limit)
    so it travels with the code. `OcdsFileAdapter` is the reference implementation and the
    offline path for tests and CI — an OCP Data Registry bulk download is this adapter
    pointed at the unpacked archive.
  - `store.py` — content-addressed blobs keyed by `sha256` with two-level fan-out (the same
    CPWD GCC across a thousand tenders costs one copy) and JSONL manifests.
  - `harvest.py` — orchestration with polite rate limiting, resumability via known OCIDs,
    dedupe accounting, and per-record error isolation. A run that dies on tender 417 of
    1,000 is worth less than one that finishes and reports 3 failures.
- **`scripts/corpus_harvest.py`** — thin CLI: `--list-adapters`, `--source/--path`,
  `--limit`, `--no-documents`, `--no-awards`, `--no-resume`, `--stats`.
- **Defect found and fixed by the tests:** the harvester re-ingested its own manifest when
  the corpus was stored inside a scanned source directory, because a `CorpusTender` record
  carries an `ocid` and is otherwise shaped exactly like an OCDS release — inflating the
  corpus on every pass. Manifest lines now carry a marker that source adapters skip, with a
  dedicated regression test.
- **`.gitignore`:** `evals/corpus/` and `evals/runs/` — public records, but large and
  reproducible from source.
- **Tests:** `backend/tests/test_evalcorpus.py`, 35 cases covering currency conversion,
  OCDS mapping, unresolved-buyer handling, provenance, adapter contract and legality
  declaration, malformed-file tolerance, content addressing, dedupe, resumability, and the
  re-ingestion regression.
- `specs/eval-at-scale.md` updated with the implemented schema, storage model, adapter
  contract and package layout.

Verified end-to-end via the CLI: 5 tenders / 5 document references / **1 blob** (dedupe),
second run skips all 5 (resume), money stored as `100050` for `1000.50 INR`.

Suite: 250 passed, 5 skipped; ruff and mypy clean across 169 files.

**Next:** TS-226 (M1 structural invariant suite) — the 100%-pass correctness gate, then
TS-230 (bulk runner). TS-225 real network adapters (CPPP, state NIC, Etimad) need an egress
path that CPPP does not block.

### Done — 2026-07-30 (TS-223: per-review cost instrumentation — Phase 16 Sprint 0)

First implementation task of Phase 16. Answers the question the product cannot price
without: what does one completed tender review actually cost?

- **`backend/app/core/costmeter.py`** (new): review-scoped cost accounting.
  - `review_cost_scope(opportunity_id=…, rulepack_version=…)` meters everything inside it
    as one review; nesting attributes work to the inner scope rather than double-counting.
  - Cost drivers recorded: LLM tokens (prompt / completion / cached), OCR pages, worker
    seconds, storage bytes — with per-stage attribution.
  - **Money in minor units**, integer arithmetic, one rounding at the end (`CLAUDE.md` §4).
  - **No built-in price table.** `TS_LLM_PRICE_TABLE` is deployment configuration; an
    unpriced model has its tokens counted and is reported unpriced rather than costed at
    zero. Only fully-priced reviews feed the cost histogram, so p50/p95 cannot be
    understated by partial pricing.
  - **Metering never breaks a review** — malformed usage objects, missing prices and
    unparseable price tables are logged and swallowed.
- **`backend/app/core/llm.py`**: `MeteredClient` wraps every OpenRouter client, so usage is
  recorded at the single choke point and a future call site cannot forget to meter itself.
  `openrouter_client(stage)` labels calls; the three existing sites now pass
  `risk.classify`, `assistant.chat` and `analytics.plan`.
- **Retrieval-first guard:** `TS_MAX_TOKENS_PER_REVIEW` (default 400,000). Cost must scale
  with pattern count, not document length (Strategy §G.3); a change that starts sending
  whole documents to a model now surfaces as a warning plus
  `ts_review_token_ceiling_exceeded_total` rather than as a bill.
- **Wired in:** OCR page counts in `ingestion/ocr.py`; the async document pipeline in
  `ingestion/tasks.py` now runs inside a review scope and records worker seconds.
- **Metrics:** six counters and four histograms (`ts_review_cost_minor`,
  `ts_review_total_tokens`, `ts_review_wall_seconds`, `ts_worker_seconds`) — p50/p95 come
  from Grafana over the existing Prometheus endpoint.
- **Tests:** `backend/tests/test_costmeter.py`, 21 cases covering cost arithmetic, cached
  token pricing, unpriced-model honesty, nested scopes, scope teardown on exception, the
  metered client wrapper, metering-failure tolerance, and the token ceiling.
- `specs/modules/observability.md` updated with the cost-instrumentation interface,
  behaviour (C1–C7) and acceptance criteria (A9–A15).

Suite: 215 passed, 5 skipped; ruff and mypy clean across 164 files.

**Next:** TS-224 (corpus schema + `scripts/corpus_harvest.py` adapter interface), then
TS-226 (M1 structural invariant suite) — completing Sprint 0/1.

### Done — 2026-07-30 (TS-293: task tracker script + backlog integrity audit)

- **`scripts/task_tracker.py`** (new): parses `tasks/backlog.md`, validates it, and reports progress.
  - Validates unique IDs, the `todo | in-progress | blocked | done` status enum, 5-column row shape,
    paths referenced by *done* tasks existing on disk, and that every `TS-` id cited in
    `tasks/*tracker*.md` exists in the backlog.
  - Reports per-phase progress bars, incomplete/blocked/in-progress lists.
  - Modes: default summary, `--incomplete`, `--phase N`, `--json`, `--validate` (exit 1 on error).
  - Wired into CI as a new blocking `backlog` job.
- **Backlog integrity fixes surfaced by the new script:**
  - Two malformed rows (TS-193, TS-194 began with `||`, breaking table rendering) corrected.
  - Six tasks carried non-conforming statuses that read as complete but were not. Reclassified to
    the documented enum, with the caveat moved into the title:
    - TS-035, TS-036, TS-037, TS-079 → `blocked` (adapters and providers are written; verification
      needs live provider credentials — code presence confirmed in `notifications/adapters.py`,
      `billing/providers.py`, `auth/google.py`).
    - TS-163 → `in-progress` (backend and core frontend landed; settings UI outstanding).
    - TS-039 → `done`, with the unverified-ONNX-download caveat moved into the title.
  - Three stale path references on done tasks corrected: TS-081 and TS-189 point at `backend/tests/`,
    TS-176 at `frontend/e2e/`.
- **Verified position:** 294 tasks, no duplicate or missing IDs, 191 done, 103 incomplete
  (1 in-progress, 4 blocked, 98 todo).

### Done — 2026-07-30 (Roadmap Stage 1→5: reconciling the founding research with the build)

Planning only — no runtime code. Triggered by re-reading the founding research doc
(`TenderShield_AI_Architecture_and_Market_Research.pdf`, 20 Jul 2026) against the codebase.

- **`docs/TenderShield_Roadmap_Stage1_to_5.md`** (new master roadmap):
  - Position audit against the research doc's five-stage value ladder: stage 1 substantially
    complete, stage 2 partial, stages 3–5 not built. The entire 24.5k-line backend sits in the
    transactional half of the ladder; all recurring revenue is in stages 3–5.
  - The money ladder — per the research doc's own §10.1 price bands, stage 3 is worth roughly 12×
    stage 1 per customer and is structurally stickier (a contractor cannot switch mid-project).
  - Gap analysis: nine capability blocks specified in the founding research and never built —
    baseline→project controls, change/variation detection, claims workspace, control tower,
    integrations, subcontract control, payment control, site evidence, advisor edition.
  - Two missing concepts recovered: **evidence continuity** (the research doc's stated "most
    valuable product") and the **north-star metric, "verified contractor margin protected"**.
  - Restructured phase plan 16→21, each mapped to a stage and carrying an unlock gate taken from
    the research doc's own kill/continue criteria (§12.4).
  - Reconciliation appendix: the AI assistant appears nowhere in the founding capability
    architecture; the product was never civil-only (§3.3, §3.4, §8.2 always specified multi-segment,
    multi-jurisdiction packs); geography expansion requires a local specialist plus a paid design
    customer.
- **`tasks/backlog.md`:** TS-234 added to Phase 16 (north-star metric), plus Phases 17–21 —
  TS-235 – TS-292:
  - Phase 17 (stage 2): baseline completion — award comparison, risk watchlists, notice-rule
    register, approval matrix, cost codes, handover pack, adoption telemetry.
  - Phase 18 (stage 3, ★ recurring revenue): change & notice control — baseline diff, change-signal
    ingestion, variation inbox, site confirmation, deterministic notice-deadline engine, evidence
    chain of custody and completeness scoring, per-project billing.
  - Phase 19 (stage 4): claims & evidence workspace — chronology, deterministic quantum, delay
    register, draft generators, settlement tracking, chain-integrity test.
  - Phase 20 (stage 5): commercial control tower — exposure model, forecasting, portfolio trends,
    payment control, economics and customer-outcome metrics.
  - Phase 21: integrations, subcontract flow-down and pay-when-paid exposure, advisor edition.
- **`tasks/roadmap_tracker.md`** (new master tracker): stage↔phase↔revenue map, unlock-gate status,
  per-phase task tables with dependencies, evidence-chain completion tracker, metrics coverage, and
  a gate-override log so any decision to skip a gate is recorded rather than implicit.

**Next:** unchanged — Phase 16 Sprint 0 (TS-223 cost instrumentation, TS-224 corpus harvester,
TS-226 M1 invariants), now with TS-234 (north-star metric) added to the phase.

### Done — 2026-07-30 (Phase 16 planning: defensibility, domain-agnosticism, scale validation)

Requirements and planning only — no runtime code in this change.

- **`docs/TenderShield_Market_Strategy_2026.md`** (new, requirement source for Phase 16):
  - Part A — researched source base with citations: competitive landscape (Trimble/Document Crunch
    closing Q2 2026; Procore/Autodesk moves; crowded Indian L1-prediction segment), public
    procurement data (CPPP ~4.9 M award records, Etimad 283k with official API, TED eForms/SPARQL,
    OCDS across 30+ governments, CAG audit reports, MoSPI/PAIMANA overrun data), and EU AI Act
    status (Annex III deferred to Dec 2027; contractor-side tools likely out of scope — flagged
    `assumption:`).
  - Part B — defensibility thesis: four moat classes (proprietary data, deterministic computation,
    accountability, workflow position) and the eight verifiable claims they produce.
  - Part C — ranked value features with why/how/what-if: Employer Behaviour Graph, risk-to-price,
    cashflow, SOR benchmarking, contradiction engine, outcome capture, reproducibility chain,
    correction loop.
  - Part D — domain-agnostic architecture: agnostic engine / deep packs / per-vertical graph, plus a
    five-rung generalization ladder and the pack-SDK distribution play.
  - Part E — geography: India → Saudi → UAE, Europe deferred; the Indian-contractor-in-the-Gulf
    bridge; jurisdiction must be a property of the opportunity, not the workspace.
  - Part F — business model including the new **Express** pay-per-report lane and its resolution of
    the Build Doc §11.4 reviewer-gate conflict.
  - Part G — profitability: cost drivers to instrument before any pricing commitment; the
    retrieval-first cost property and how to guard it.
  - Part H — risks, what-ifs and kill conditions.
- **`specs/eval-at-scale.md`** (new): automated evaluation on 1,000+ real tenders. Five scoring modes
  — M1 structural invariants, M2 portal-metadata agreement, M3 outcome backtest, M4 metamorphic
  consistency (all label-free) and M5 a 50-tender human gold set. OCDS as the normalization target,
  per-source adapters with recorded legality review, Celery-based resumable sharded runner with a
  cost guard, and CI gating.
- **New module specs:** `specs/modules/marketdata.md`, `specs/modules/pricing-intel.md`,
  `specs/modules/express-report.md`, `specs/modules/outcomes.md`. Index updated in `specs/README.md`.
- **`tasks/backlog.md`:** Phase 16 added — TS-195 – TS-233 across seven groups, each task mapped to a
  moat class.
- **`tasks/phase16_tracker.md`** (new): sprint map with sequencing rationale, dependency graph with
  critical path, per-task acceptance gates, phase exit gates and kill conditions.

**Next:** TS-223 (cost-per-review instrumentation), TS-224 (corpus schema + harvester), TS-226 (M1
structural invariant suite) — Sprint 0/1, in that order. Measurement precedes corpus; corpus precedes
the graph; correctness at scale precedes the Express revenue lane.

### Done — 2026-07-31 (TS-298: CI changelog-check gate)

- Added `scripts/check_changelog.py`: fails when non-exempt ("code") files
  changed between two refs but `CHANGELOG.md` didn't gain any real content in
  the same range, enforcing `CLAUDE.md` §1.5 ("a push without a changelog
  entry is incomplete work") mechanically instead of by convention.
- Docs/spec/task-only changes (`docs/`, `specs/`, `tasks/`, `.github/`,
  `.cursor/`, `.devin/`, any `*.md`) are exempt; a `[skip-changelog]` marker in
  any commit message in range bypasses the check for merges/reverts/dep bumps.
- Added a `changelog` job to `.github/workflows/ci.yml`, gated on
  `pull_request` events, that runs the script's unit tests
  (`scripts/tests/test_check_changelog.py`) and then checks the PR's diff
  against its base branch.
- Added `specs/902-changelog-check.md` describing the behavior and acceptance
  criteria, indexed in `specs/README.md`.

### Next

- TS-299: consider extending the changelog check to also verify the `Next`
  section names concrete task IDs (currently only advisory via B5).

### Done — 2026-07-30 (TS-297: workspace-scoped AI Assistant)

- `ChatSession.opportunity_id` is now optional; the AI Assistant works across the
  whole workspace by default instead of requiring a tender dropdown.
- Updated `AssistantService.answer`, `answer_and_store`, `answer_stream`, and
  `admin_answer` so `opportunity_id` is optional.
- Assistant tools (`list_deadlines`, `filter_findings`, `missing_docs`) now aggregate
  across workspace opportunities when no `opportunity_id` is provided.
- Plan-dashboard intent picks the first workspace opportunity when none is supplied.
- Updated `POST /api/assistant/chat`, `/sessions`, `/sessions/{id}/chat`, `/stream`,
  and `/admin/chat` schemas to make `opportunity_id` optional.
- Removed the opportunity dropdown from `/assistant`; the page now sends workspace-level
  chat requests.
- Updated `specs/modules/assistant.md` with workspace-scope behavior and acceptance
  criteria; added migration `0c2f0e860d39`.

### Done — 2026-07-30 (TS-192: user-facing plan upgrade/downgrade)

- Added `GET /api/billing/plans` public catalog and `POST /api/billing/change-plan`
  so workspace admins can upgrade or downgrade their account plan.
- Downgrade to `free` takes effect immediately and appends a `plan_history` row.
- Upgrade/downgrade to `pro` or `scale` returns a provider checkout; the plan is
  activated only by the verified webhook (Doc §15.1 remains the billing truth).
- Refactored `POST /api/billing/checkout` into a shared `_create_checkout` helper
  used by both checkout and change-plan.
- Updated `/billing` UI with plan cards that show current plan, price, and context-aware
  "Upgrade" / "Downgrade" actions.
- Added backend tests for plan catalog, downgrade to free, paid checkout, and invalid/same-plan rejection.
- Updated `specs/modules/billing.md` with TS-192 behavior and acceptance criteria.

### Done — 2026-07-30 (TS-186/187/188: AI assistant scoping, Office MCP, and dynamic plan dashboard)

- **TS-186**: Scoped the AI assistant to the logged-in user's account/workspace.
  - Assistant system prompt now includes `user_id`, `workspace_id`, and `role` and
    refuses cross-tenant queries.
  - `AssistantService` re-binds the workspace context and defends in depth with a
    workspace membership check when the auth capability is available.
  - Added `POST /api/assistant/admin/chat` (super-admin only), audit-logged, which
    answers a specific `workspace_id`/`opportunity_id` without persisting a session.
  - Updated `specs/modules/assistant.md` with user-bound sessions, identity-in-prompt,
    and admin-mode acceptance criteria.
- **TS-187**: Added a standalone Microsoft Office MCP server for QS engineers.
  - `mcp-servers/office-mcp/` exposes tools to read `.docx`/`.xlsx`, append comments
    to Word, append rows to Excel, and create summary Word documents.
  - Added `specs/modules/mcp-office.md` and `docs/integrations/office-mcp.md`.
- **TS-188**: Built an AI-generated dynamic tender plan dashboard.
  - `POST /api/analytics/plan` accepts a natural-language query and returns structured
    JSON (KPI, table, chart, Mermaid diagram, or text sections).
  - `PlanDashboardAgent` grounds the response in workspace facts (findings, deadlines,
    documents) and validates section shapes, falling back to a safe text section.
  - New `/plan` page in the frontend renders the structured dashboard with `recharts`
    charts and `mermaid` diagrams.
  - Added `specs/modules/plan-dashboard.md`.

### Done — 2026-07-30 (TS-189: tests/audit-log for assistant scoping, admin chat, plan dashboard; alembic downgrade fix)

- **TS-189**: Added backend tests and audit-log verification.
  - `tests/test_assistant.py`: admin chat rejects non-super-admins, super-admin chat
    can query a specific workspace/opportunity, and the query is written to the audit log.
  - Workspace scoping: a second workspace's token cannot list or post to another
    workspace's assistant session.
  - `tests/test_analytics.py`: `POST /api/analytics/plan` returns a structured dashboard
    payload; cross-workspace access for an alien `opportunity_id` is rejected.
- Fixed `alembic downgrade base` for the billing/plan migrations (`d109c102dd39` and
  `c7dac720f0e6`) by recreating the expected SQLite index names after table renames,
  so CI `alembic upgrade head && alembic downgrade base` now passes.

### Done — 2026-07-30 (TS-190: Office MCP server ↔ TenderShield API integration)

- Added `TenderShieldClient` in `mcp-servers/office-mcp/tendershield_office_mcp/client.py`
  that calls `TENDERSHIELD_API_BASE` with a `TENDERSHIELD_API_TOKEN`.
- New MCP tools:
  - `tendershield_list_opportunities`, `tendershield_get_opportunity_summary`,
    `tendershield_get_findings`, `tendershield_plan_dashboard` (read-only lookups).
  - `tendershield_export_findings_to_excel` and `tendershield_create_summary_doc`
    (pull live findings/deadlines into Word/Excel outputs).
- Updated `specs/modules/mcp-office.md`, `docs/integrations/office-mcp.md`, and the
  `mcp-servers/office-mcp/README.md` with setup and tool descriptions.

### Done — 2026-07-30 (TS-191: plan dashboard templates, snapshots, PDF/PPTX export)

- Added `plan_snapshots` table and Alembic migration `319b6c25e064` to persist
  AI-generated dashboards per user/workspace/opportunity.
- New API endpoints under `/api/analytics/plan`:
  - `GET /templates` — predefined queries for risk severity, deadline timeline,
    BOQ defects, and bid readiness.
  - `GET/POST/DELETE /snapshots` — save, list, load, and delete dashboard snapshots.
  - `GET /snapshots/{id}/export?format=pdf|pptx` — export a snapshot as PDF or PowerPoint.
- `PlanDashboardExporter` renders the structured dashboard to PDF (ReportLab) and
  `.pptx` (python-pptx) with a slide per section.
- `/plan` UI now has a template picker, snapshot title/save form, saved snapshot
  list, and PDF/PPTX export buttons.
- Updated `specs/modules/plan-dashboard.md` and added `python-pptx` to backend
  dependencies.

### Done — 2026-07-30 (TS-193: assistant chat UI with collapsible dashboard panel; TS-194: snapshot export 404 fix + openrouter/free default)

- **TS-193**: Reframed the AI-generated plan dashboard as part of the assistant chat experience.
  - New `/assistant` page provides a dedicated chat UI for the selected opportunity.
  - Assistant responses can include `type: "dashboard"` with a structured `PlanDashboard` payload.
  - A collapsible dashboard panel on the right renders KPIs, tables, charts, and Mermaid diagrams inline.
  - Shared `frontend/components/plan-dashboard.tsx` renders dashboard sections for both `/plan` and `/assistant`.
  - Updated `specs/modules/assistant.md` and `frontend/app/layout.tsx` with the AI Assistant nav link.
- **TS-194**: Fixed plan snapshot export and clarified OpenRouter model/ API-key requirements.
  - Verified `GET /api/analytics/plan/snapshots/{id}/export?format=pdf` works when the correct snapshot id and a valid token are used; the earlier 404 was caused by a stale token and a typo in the test id.
  - Changed the default OpenRouter model from `openai/gpt-4o-mini` to `openrouter/free` in `backend/app/core/config.py` and `.env.*` files.
  - Improved `PlanDashboardAgent` fallback copy to explicitly ask for an OpenRouter API key so users know free models still require authentication.
  - Updated `specs/modules/plan-dashboard.md` with TS-193/194 task references.

### Next

No tracked `todo` tasks remain in `tasks/backlog.md`.

### Done — 2026-07-30 (TS-185: billing usage/payments/invoices belong to user account, not workspace)

- Moved `billing_provider` and `billing_settings` from `workspaces` to `users`.
- `UsageEvent`, `PaymentLog`, and `Invoice` now store `user_id` and optional
  `workspace_id` (workspace is for attribution only).
- `WebhookEvent` is now a global idempotency ledger keyed by `(provider, provider_event_id)`,
  no longer workspace-scoped.
- `BillingService` derives the account owner for usage counting, invoices, and
  payment history; `GET /api/billing/invoices` and `/api/billing/payments` return
  the current user's account-wide history.
- `GET/PUT /api/billing/settings` now read/write the user account's billing profile.
- `frontend/app/billing/settings/page.tsx` labels the account plan instead of the active workspace.
- Added Alembic migration `c7dac720f0e6` to migrate existing rows and drop workspace
  RLS policies on the affected billing tables.
- Updated `specs/modules/billing.md` to reflect account-level billing data.

### Done — 2026-07-30 (TS-184: plan belongs to user account, not workspace)

- Moved `plan` and `free_review_used` columns from `workspaces` to `users` so
  billing follows the account, not a workspace that can be deleted.
- Updated `BillingService` to resolve the workspace owner and read/update the
  user account's plan; `set_workspace_plan` still accepts a workspace ID but sets
  the owning user's plan.
- `PlanHistory` is now keyed by `user_id` instead of `workspace_id` and is no
  longer workspace-scoped/RLS-isolated (it is account-level history).
- `GET /api/billing/plan-history` returns the current user's account plan changes.
- Admin user detail page (`/admin/users/[id]`) now shows the user's current plan
  and each workspace's plan pill (inherited from the account).
- Added Alembic migration `d109c102dd39` to migrate existing `plan_history` rows
  and backfill `users.plan`/`free_review_used` from the first owned workspace.
- Updated `specs/modules/billing.md` to reflect account-level billing plan state.

### Done — 2026-07-30 (TS-183: billing/payment UI and admin/billing API mapping)

- Added `Coupon` and `PlanHistory` models, Alembic migration, and RLS policy for
  `plan_history`.
- New billing endpoints:
  - `GET /api/billing/payments`, `GET /api/billing/plan-history`
  - `GET /api/billing/coupons`, `POST /api/billing/coupons`,
    `DELETE /api/billing/coupons/{code}`
  - `POST /api/billing/checkout` now accepts `coupon_code` and applies the discount
    to the server-owned price; coupon is re-validated on Razorpay/Stripe webhooks.
- `BillingService.set_workspace_plan` records every plan change in `plan_history`;
  registered as `billing.set_workspace_plan` capability for auth/admin plan updates.
- Webhook plan changes (subscription charged/activated/halted/cancelled) write
  `plan_history` rows.
- Frontend: `/billing` page now has tabs for Overview, Invoices, Payments, and Plan
  History with a coupon input on the dashboard card; added `/admin/coupons` page.
- Updated `specs/modules/billing.md` with coupon, plan history, and payment history
  acceptance criteria.

### Done — 2026-07-30 (TS-182: persistent logs with Loki + Grafana)

- Write JSON access logs and application logs to rotating files via
  `configure_logging`.
- Ship those files to Loki with Promtail and add Loki to the docker-compose
  `observability` profile.
- Grafana is pre-provisioned with both Loki and Jaeger data sources for
  log search and trace search from the same UI.

### Done — 2026-07-30 (TS-181: access logger handler fix)

- Ensure `tendershield.access` logs are emitted even when Uvicorn's default
  logging config has no root handler.

### Done — 2026-07-30 (TS-180: request access logs and trace enrichment)

- Add per-request access logging with method, path, status, duration, user, and
  workspace (and optional request/response body logging behind a flag).
- Enrich OpenTelemetry spans with `user.id`, `workspace.id`, `user.role`, and
  path parameters such as `ticket.id` so Jaeger/Grafana can filter by user or
  support ticket.

### Done — 2026-07-30 (TS-179: testing skill observability demo notes)

- Add Jaeger/Grafana Docker network note, OTLP backend command, and anonymous
  Grafana access tip to `.agents/skills/testing-tendershield/SKILL.md`.

### Done — 2026-07-30 (TS-178: OpenTelemetry tracing and self-hosted observability)

- Add OpenTelemetry instrumentation to the FastAPI backend.
- Add Jaeger all-in-one and Grafana to `docker-compose.yml` for self-hosted tracing.
- Add `scripts/verify-traces.sh` to boot the stack, emit a request, and verify a
  trace is visible in Jaeger.
- Document observability setup and trace inspection in `docs/runbooks/observability.md`.

### Done — 2026-07-30 (TS-177: format analytics dashboard)

- Replace raw JSON `<pre>` blocks on `/analytics` with readable cards/tables for
  risk summary, deadline dashboard, and BOQ defect summary.

### Done — 2026-07-30 (TS-176: close remaining product needs)

- TS-146 verified as already implemented; backlog status corrected.
- Notification preferences API (`GET/PUT /api/notifications/preferences`) and UI
  (`/settings/notifications`) with `email_deadlines`, `sms_deadlines`, `email_digest`,
  `sms_alerts`, `marketing`, and quiet-hours fields.
- Account settings page now links to notification preferences and exposes
  account export and deletion.
- Admin console UI: dashboard KPIs (`/admin`), user search/suspend/delete
  (`/admin/users`, `/admin/users/[id]`), workspace plan change
  (`/admin/workspaces/[id]`), audit-log viewer (`/admin/audit-log`), and support
  ticket queue (`/admin/support`).
- Billing self-service UI (`/billing/settings`) for GSTIN/PAN/billing address/payment
  method and subscription cancellation.
- Support ticket UI: user list/detail/create (`/support/tickets`) and admin
  management (`/admin/support`).
- Analytics reports UI (`/analytics`) for risk summary, deadline dashboard,
  BOQ defect summary, and CSV/XLSX/PDF export.
- `docker-compose.yml` now includes Postgres, Redis, and MinIO for a complete
  local production-like stack; `.env.dev` has the matching S3/MinIO examples.
- Playwright E2E harness added (`frontend/playwright.config.ts`, `e2e/fixtures.ts`,
  `e2e/golden-path.spec.ts`) covering sign-up, verification, MFA login,
  workspace creation, opportunity creation, and document upload.
- Alerting and runbooks: `docs/runbooks/alerting.md`, `docs/runbooks/backup-restore.md`,
  and `observability/prometheus-alerts.yml`; notifications scheduler now exposes
  a `deadline_alert_tick_last_success_seconds` gauge.
- Real provider integrations (OpenRouter, SES/MSG91, Razorpay/Stripe) remain
  credential-gated and are wired but not activated without keys.

### Done — 2026-07-30 (TS-170: admin, billing self-service, support tickets, analytics, audit-log search)

- Admin user/workspace management: `User.suspended_at`/`suspended_by`, workspace `billing_settings`;
  new `/api/auth/admin/dashboard`, `/api/auth/admin/users/search`, `/api/auth/admin/users/{id}`
  (detail, suspend, unsuspend, delete), and `/api/auth/admin/workspaces/{id}/plan`.
- Billing self-service: `GET/PUT /api/billing/settings` for billing address/GSTIN/payment method,
  and `POST /api/billing/cancel` to downgrade a paid workspace to `free`.
- New `support` module: workspace-scoped `support_tickets`, `support_ticket_replies`,
  `support_attachments`; `POST /api/support/tickets`, `GET /api/support/tickets/{id}`,
  `POST /api/support/tickets/{id}/replies`, `POST /api/support/tickets/{id}/attachments`,
  plus super-admin ticket management under `/api/support/admin/tickets`.
- Analytics reports: `GET /api/analytics/risk-summary`, `deadline-dashboard`, `boq-defect-summary`,
  and `POST /api/analytics/reports/export` (`csv`/`xlsx`).
- Observability log search: super-admin `GET /api/auth/admin/audit-log` with workspace,
  action, object_type, actor, and date filters.
- Alembic migration `f94c5d977344` adds the new auth columns and support tables.
- Backend: `ruff`, `mypy`, `pytest` clean; `alembic upgrade head` passes.

### Done — 2026-07-29 (PR consolidation)

- Merged the two older audit-only branches (`devin/fourth-round-audit` and
  `claude/production-readiness-audit-ts130-1753815240`) into the consolidated
  branch using `merge -s ours` so their history is preserved but the current
  report/fixes remain authoritative.
- Closed PR #20 and PR #19 as superseded by PR #21.
- Renamed PR #21 to reflect it is the consolidated production-readiness audit + fixes PR.

### Done — 2026-07-29 (TS-097 follow-up: PostgreSQL RLS regressions + migration drift)

- `bind_workspace_context` now inlines the validated UUID string because `SET LOCAL`
  does not accept SQLAlchemy bind parameters.
- `rls_statements` uses `nullif(current_setting('app.workspace_id', true), '')::uuid`
  so an unset GUC evaluates to NULL (fail-closed) instead of raising an empty-string
  UUID cast error.
- Rewrote `tests/test_rls_postgres.py` as a self-contained PostgreSQL-only suite that
  creates/drops its own RLS sample table, backfills rows, and asserts cross-tenant
  read/write blocking and owner-level `FORCE` enforcement.
- Added `migrations/versions/3e8f87662b2f_*.py` to backfill `Invitation.token -> token_hash`
  and add `users.mfa_totp_pending_secret`, fixing the `alembic upgrade head` drift
  reported by the testing agent.
- Added `psycopg[binary]` to `dev` extras and updated the `rls-postgres` CI job to
  create a non-superuser `app`/`app_db` so `FORCE ROW LEVEL SECURITY` is actually tested.

### Done — 2026-07-29 (TS-163: account-centric auth re-architecture backend)

- `User` model now stores `org_name`, `city`, `dob`, `phone`, `mobile_verified`;
  `phone` and `password_hash` are non-nullable; OIDC columns (`google_sub`, `apple_id`)
  removed.
- Added `MobileVerification` table and Alembic migration `6cffa6139050`.
- `POST /api/auth/signup` now creates an account only (no default workspace) with
  org/firm name, email, mobile, city, DOB, password, and confirm-password fields;
  enforces password complexity; returns email and mobile verification tokens.
- `POST /api/auth/verify-email` and `POST /api/auth/verify-mobile` activate the account.
- `POST /api/auth/login` always issues an OTP challenge; tokens are only returned after
  the `/api/auth/mfa/challenge` step.
- Removed Google and Apple OIDC routes and service methods.
- Added `/api/auth/settings`, `/api/auth/settings/password`, and updated `/api/auth/me`.
- JWT claims and `Principal` now include `mobile_verified`; gated endpoints require both
  email and mobile verified (or superadmin).
- Added `tests/helpers.py` and updated all test suites for the new OTP-on-login flow.
- Backend: 146 tests passed, ruff clean.

### Done — 2026-07-30 (TS-163 follow-up: migration fixes)

- `e26e85245237` RLS policy loop now skips tables that do not yet exist, so a later
  migration can create and then secure `award_documents`.
- `5a5548916ff0` now applies workspace-isolation RLS immediately after creating the
  `award_documents` table.
- `6cffa6139050` uses `batch_alter_table` and backfills existing rows, making the
  `phone`/`password_hash` NOT NULL change and OIDC column drop safe on both PostgreSQL
  and SQLite.
- Verified `alembic upgrade head` and `alembic downgrade base` on SQLite.

### Done — 2026-07-30 (TS-163 re-analysis: account-first auth flow hardening)

- Re-analyzed open TODOs against the new account-centric auth flow; the auth-related
  open items (TS-103, TS-106, TS-107, TS-135, TS-161, TS-163 frontend) are now driven
  by account → workspace selection after login.
- `AuthService.login` now always issues an account-level `mfa_token` with no workspace
  selected; `mfa_challenge` returns an account-level access token.
- `AuthService.refresh` preserves the workspace bound to the refresh-token row instead
  of picking an arbitrary workspace; `refresh_tokens.workspace_id` column added.
- `bind_workspace_context` now also sets `app.user_id`; membership-table RLS policies
  (`workspace_members`, `project_members`) allow a user to read/write their own rows
  even in an account-level session, so `/api/auth/workspaces` create/list and switch work.
- `rls_statements` supports an optional `user_id_column` for membership tables.
- Updated `specs/modules/auth.md` (B2, B3, A25).
- Frontend updated for the new flow: `login/page.tsx` has account-only signup with
  org/firm name, email, mobile, city, DOB, password + confirm, email/mobile
  verification, OTP login, and workspace creation; `session.tsx` drives workspace
  selection; `api.ts` and `admin/page.tsx` align with backend response shapes.
- Fixed `6cffa6139050` to use dialect-aware `ALTER TABLE` on PostgreSQL (avoiding
  `DROP CONSTRAINT users_pkey` while FKs reference it) and keep batch-alter for SQLite.
- `tests/test_rls_postgres.py` now catches `(IntegrityError, ProgrammingError)` for
  RLS `WITH CHECK` violations (`InsufficientPrivilege` is a `ProgrammingError` in psycopg).

### Done — 2026-07-30 (TS-125: rulepack validation / beta-disclaimer flag)

- Added `disclaimer` to the shared `Finding` contract and `findings` table.
- Added `TS_BETA_UNVALIDATED` setting. Paying workspaces see only `validated`
  patterns by default; when the flag is enabled, unvalidated patterns are still
  surfaced with a clear beta disclaimer.
- `RiskService` sets `validated_only=True` for paying workspaces unless the beta
  flag is on; `run_patterns` tags findings from `confidence: unvalidated` patterns.
- Updated `specs/modules/rulepacks.md` B2 and `specs/modules/findings.md` B6.
- Added migration `857d8c12c3f6` for `findings.disclaimer`.

### Done — 2026-07-30 (TS-106: team-management UI and invitation revocation API)

- Added `/team` page: invite members, list members, change role, remove member,
  list pending invitations, revoke invitations.
- Linked `/team` from the header nav.
- Extended the typed API client with team/invitation endpoints.
- Added backend `AuthService` methods and REST endpoints:
  - `PUT /api/auth/workspaces/{id}/members/{user_id}` — change role,
  - `DELETE /api/auth/workspaces/{id}/members/{user_id}` — remove member,
  - `GET /api/auth/invitations` — list pending invitations,
  - `DELETE /api/auth/invitations/{id}` — revoke invitation.
- Enforced admin+ role, no self-management, and role-rank limits in team operations.
- Updated `specs/modules/auth.md` and `specs/frontend.md` with team behavior and acceptance criteria.

### Done — 2026-07-30 (TS-107: account & security settings UI)

- Added `/settings` page with profile (org/firm, city, phone, DOB) and security
  (change password, sign out) forms.
- Linked `/settings` from the header nav.
- Added `api.getSettings`, `api.updateSettings`, and `api.changePassword` to the
  typed API client; added `AccountSettings` type.
- Updated `specs/frontend.md` with `/settings` structure, behavior B9, and acceptance A8.

### Done — 2026-07-30 (TS-150 / TS-153 / TS-158: review audit scoping, LocalStorage async I/O, and review opportunity scoping)

- `GET /api/review/opportunities/{id}/audit` now only returns audit rows whose
  object is a finding belonging to that opportunity.
- `LocalStorage.write`, `read`, and `delete` now run filesystem calls via
  `asyncio.to_thread`, preventing synchronous I/O from blocking the event loop.
- `POST /api/review/findings/{finding_id}` now requires an `opportunity_id` and
  returns 404 if the finding does not belong to that opportunity.
- Updated `frontend/lib/api.ts` and `frontend/app/opportunities/[id]/page.tsx` to
  pass `opportunity_id` when reviewing a finding.
- Added `test_review.py::test_review_finding_scopes_by_opportunity` and updated
  all tests that call the review endpoint.
- Updated `specs/modules/review.md` and `specs/modules/core.md`.

### Done — 2026-07-30 (TS-113 / TS-135: virus scanning and frontend session provider)

- `core`: `validate_and_store` now streams uploads through a local clamd daemon when
  `TS_CLAMD_SOCKET` is configured. Detected files are quarantined to
  `TS_QUARANTINE_DIR` and rejected with `ValidationError`. When no scanner is
  configured the step is skipped with a warning (TS-113).
- `frontend`: `SessionProvider.applyTokens` always replaces the workspace list with
  the freshly loaded result, so deleting workspaces or switching contexts no longer
  leaves stale entries (TS-135).
- Updated `specs/modules/core.md`, `specs/frontend.md`, `tasks/backlog.md`, and tests.

### Done — 2026-07-30 (TS-111: deadline-alert deduplication and notification preferences)

- Added `notification_preferences` (account-level defaults: `email_deadlines=True`)
  and `deadline_alert_log` (workspace-scoped, RLS-enforced) tables.
- The daily deadline scheduler now buckets alerts at 7, 3, 1, and 0 days, checks
  per-user preferences, and records each `(user, deadline, bucket)` send to
  prevent duplicates.
- `WorkspaceAdmin.list_members` now returns `user_id` along with `email`.
- Updated `specs/modules/notifications.md`, `tasks/backlog.md`, and added
  `tests/test_notifications.py`.

### Done — 2026-07-30 (TS-112: shared prompt-injection guard for LLM call sites)

- Added `app.core.prompt_guard` with `looks_like_injection`, `sanitize_message`,
  and `delimit_untrusted` helpers used by all LLM call sites.
- `assistant/agent.py` now sanitizes user input and wraps both the user query and
  tool results in XML-style delimiters before calling Anthropic.
- `risk/classifier.py` skips classification when a rulepack pattern prompt
  matches common override/jailbreak patterns, and wraps all tender clause text
  in `<clauses>` delimiters.
- Added `tests/test_prompt_guard.py` with adversarial test fixtures.
- Updated `specs/modules/core.md`, `specs/modules/assistant.md`, `specs/modules/risk.md`,
  and `tasks/backlog.md`.

### Done — 2026-07-30 (TS-114: remove cross-module FK on findings.opportunity_id)

- `findings.models.FindingRow.opportunity_id` is now a plain `Uuid` column instead
  of a `ForeignKey` to `opportunities.id`.
- Added Alembic migration `3bfb4b682a86` to drop the existing FK on PostgreSQL.
- Added `tests/test_architecture.py::test_findings_opportunity_id_has_no_foreign_key`
  to prevent regressions.
- Updated `specs/modules/findings.md`.

### Done — 2026-07-30 (TS-116: complete audit-log events for auth, membership, role, billing, and export)

- Added `app.core.audit.log` helper that resolves the `review.service_factory`
  capability and writes append-only `audit_log` rows without cross-module imports.
- `AuthService` now records workspace creation, member add/role change/remove,
  invitation create/accept/revoke, project creation, project member add, and
  account settings/password updates (when a real workspace is selected).
- Billing routers log checkout and payment-received webhooks.
- Export and baseline routers log bid-review pack and handover downloads.
- Webhook handlers return `workspace_id` so the router can record the event.
- Added `tests/test_audit.py`.
- Updated `specs/modules/core.md` and `specs/modules/review.md`.

### Done — 2026-07-30 (TS-120: repository governance)

- Added `.github/CODEOWNERS` with the default owner (`@Wasim-Shaikh25`).
- Added `docs/governance.md` documenting the default branch, branch-protection
  rules, status-check requirements, `CODEOWNERS` conventions, and the backend/frontend
  venv install steps.
- Updated `README.md` repository map to link to `docs/governance.md`.

### Done — 2026-07-30 (TS-118: pagination and `/api/health/details` super-admin gate)

- Added `app.core.pagination.PaginationParams` with default page size 50 and max 1000.
- Added pagination query params to auth, billing, ingestion, findings, review, and
  baseline list endpoints; response headers include `X-Total-Count`, `X-Next-Offset`,
  `X-Prev-Offset`, and `X-Page-Limit`.
- `/api/health/details` now requires a valid super-admin token whenever the auth
  module is loaded; isolated module tests without auth still receive 200.
- Updated affected tests to mint a super-admin token for `/api/health/details` calls.
- Updated `specs/modules/core.md`.

### Done — 2026-07-30 (TS-159: minor-unit monetary amounts)

- `Finding.amount_exposure` changed from `Numeric(16,2)` (major-unit float) to
  `BigInteger` (minor units / paise) in model, contract, and database.
- `drafting` validators now parse `₹|Rs.|INR` amounts and store `amount_exposure`
  in paise, comparing within a 50-paise tolerance.
- Removed float conversions in baseline and drafting services; all internal money
  for findings exposure now follows the paise invariant.
- Added Alembic migration `f5c03761fb0c` to convert existing `amount_exposure`
  values from rupees to paise on both PostgreSQL and SQLite.
- Updated `specs/modules/findings.md` and `tasks/backlog.md`.

### Done — 2026-07-30 (TS-117: data export and account deletion (GDPR/DPDP))

- `AuthService.export_account_data` returns a portable JSON export of the caller's
  profile plus every workspace-scoped and user-owned auth row they own or are a
  member of, without cross-module imports.
- `AuthService.delete_account` verifies the current password, erases all
  workspace-scoped rows for every workspace the user belongs to, then deletes the
  user row (which cascades through the auth-owned membership/project/workspace
  tables).
- Added `POST /api/auth/export` and `DELETE /api/auth/account`.
- Added `specs/modules/auth.md` acceptance criteria A29 and A30 and tests in
  `tests/test_auth_module.py`.

### Done — 2026-07-30 (TS-119: accessibility linting + WCAG 2.1 AA assessment)

- Extended `.eslintrc.json` with `plugin:jsx-a11y/recommended` and fixed label
  associations in `app/settings/page.tsx`.
- Added `axe-core`, `jsdom`, and `scripts/axe-ci.mjs` / `scripts/axe-one.mjs` to
  audit every server-rendered route in `.next/server/app` against WCAG 2.1 AA.
- Added `npm run a11y` and a CI job that runs it after the build.
- Updated `specs/frontend.md` acceptance criteria.

### Done — 2026-07-30 (TS-164: replace Anthropic with OpenRouter)

- Added `app.core.llm.openrouter_client()` factory and `Settings` fields for
  `TS_OPENROUTER_API_KEY` / `OPENROUTER_API_KEY`, `TS_OPENROUTER_MODEL`,
  `openrouter_base_url`, `openrouter_site_url`, `openrouter_app_name`.
- Replaced `AnthropicAgent`/`AnthropicClassifier` with `OpenRouterAgent`/
  `OpenRouterClassifier` using the OpenAI-compatible OpenRouter endpoint.
- Updated `.env.*`, README, deployment docs, build doc, throwaway test script,
  and specs for assistant/risk.
- Added `openai` to backend dependencies.

### Done — 2026-07-30 (TS-165: MinIO storage examples)

- Added commented MinIO example config to `.env.prod` and `.env.example`.
- Updated `docs/deployment.md` with an Object storage section covering MinIO,
  AWS S3, Cloudflare R2, Tigris, and Backblaze B2.

### Done — 2026-07-30 (TS-167: expand end-to-end scenarios)

- Expanded `evals/e2e/scenarios.md` from 13 to 50 scenario groups covering
  every module and angle: auth/MFA/session, workspace/team/roles,
  opportunity/document/ingestion, risk/BOQ/review/baseline/handover,
  assistant, billing, notifications, admin, security, accessibility,
  performance/concurrency, data integrity, privacy/GDPR, integrations
  (OpenRouter, MinIO/S3, Redis/Celery, email/SMS, billing webhooks),
  observability, backup/restore, cross-browser, configuration guards,
  and fuzz/exploratory testing.
- Added a scenario coverage matrix mapping each scenario group to the
  end-to-end audit prompt sections.

### Done — 2026-07-30 (TS-169: account settings, admin, payments, tickets, analysis, observability scenarios)

- Added scenarios 56–66 covering account profile/security/delete, password change
  and forgot-password, super-admin login and dashboard, user search/suspend/delete,
  workspace and billing oversight, payment settings, support tickets, user-raised
  analysis/reports, observability/log inspection, and alerting/backup/restore runbooks.
- Updated the scenario coverage matrix.

### Done — 2026-07-30 (TS-168: assistant, document, OCR, Q&A fixtures and scenarios)

- Added `evals/e2e/fixtures/` with synthetic NIT, GCC, pre-bid Q&A, addendum,
  BOQ CSV/XLSX, combined tender pack DOCX/PDF, and standalone risk/Q&A PDFs.
- Added a trimmed, public-domain World Bank sample bidding document PDF
  (`sample_public_wb_tender.pdf`) for real-world OCR and clause-citation tests.
- Added `evals/e2e/fixtures/generate.py` to regenerate DOCX, PDF, and XLSX
  fixtures from the markdown/CSV sources.
- Added scenarios 51–55 for assistant knowledge outside risk (deadlines,
  costs, project info, sub-contracting, Q&A, addendum awareness), document
  upload/download format coverage, OCR handling, pre-bid Q&A/addendum tests,
  and assistant session continuity/metering.
- Updated the scenario coverage matrix and fixture reference.

### Done — 2026-07-30 (TS-166: end-to-end automation scenarios and audit prompt)

- Created `evals/e2e/scenarios.md` with user-journey, negative-case, security,
  and operational-readiness scenarios mapped to the audit prompt.
- Checked the end-to-end audit prompt into `evals/e2e/END_TO_END_PRODUCTION_AUDIT_PROMPT.md`
  so it can be run against evidence from these scenarios.
- Updated task backlog.

### Next

- No open tasks in this batch.

### Done — 2026-07-30 (TS-110 / TS-157 / TS-160: tus and spreadsheet page markers)

- `ingestion`: tus `OPTIONS` returns tus 1.0.0 capability headers and `204`; `POST`
  returns `201 Created` with a `Location` header; `PATCH`/`HEAD` include `Tus-Resumable`.
- `ingestion`: tus upload IDs are validated (32-char hex); file I/O in `POST`/`PATCH`/
  `HEAD`/finalise runs in `asyncio.to_thread` so it does not block the event loop.
- `ingestion`: hourly TTL sweeper removes abandoned tus chunk/state files.
- `ingestion`: XLSX rows and CSV lines now emit `[pN]` markers so downstream
  deadline/clause extraction can cite row-level provenance (TS-160).
- Updated `specs/modules/ingestion.md`, `tasks/backlog.md`, and tests.

### Done — 2026-07-30 (TS-133 / TS-134 / TS-140 / TS-145 / TS-146: ingestion, BOQ, assistant, auth)

- `ingestion`: `extract_upload` now runs in `asyncio.to_thread` so the async
  upload path does not block the event loop (TS-133).
- `ingestion`: `RegisterDocumentBody.sample_text` is capped at 1,000,000 characters
  (TS-147).
- `ingestion`: Celery `process_document` now classifies the document, segments
  clauses, extracts deadlines, updates `submission_due`, persists chunks, and
  applies OCR when `TS_OCR_ENABLED=true` (TS-148).
- `boq`: `POST .../run` rejects CSV payloads > 10,000,000 characters and the upload
  path reads at most `BOQ_MAX_UPLOAD_SIZE` bytes (TS-134).
- `boq`: DuckDB queries run against an explicitly registered DataFrame in a fresh
  in-memory connection instead of relying on caller scope (TS-140).
- `assistant`: `AnthropicAgent` now wraps user input in data-only delimiters,
  runs a lightweight prompt-injection classifier, rejects override attempts, and
  validates that cited pages exist in the tool context (TS-145).
- `auth`: `WorkspaceAdmin.list_all_workspaces()` added so the notifications
  scheduler can enumerate workspaces (TS-146).
- Updated `tasks/backlog.md` and module specs.

### Done — 2026-07-30 (TS-138 / TS-152 / TS-151 / TS-143 / TS-137 / TS-139 / TS-142 / TS-141: follow-up fixes)

- `comparison`: treat naive submission deadlines as UTC when computing `days_to_submission` (TS-138).
- `timeline`: convert all ICS `DTSTART` values to UTC before appending `Z` (TS-152).
- `drafting` + `baseline`: use atomic `INSERT ... RETURNING` with a scalar subquery
  for version numbering, removing the read-modify-write race (TS-151, TS-143).
- `risk`: robust Anthropic classifier output parsing with JSON-array extraction and
  Pydantic schema validation; fails closed on malformed responses (TS-137).
- `qualification`: missing eligibility criteria now roll up as `unknown` / `needs_review`
  with MEDIUM severity, not a hard `not_met` / `not_eligible` (TS-139).
- `ingestion`: `confirm_deadline` now verifies the deadline belongs to the URL's
  `opportunity_id` (TS-142).
- `crossref`: bound clause search with DB-level `limit` and clamp the result `limit`
  to 1–100 (TS-141).
- Added/updated module specs and `tasks/backlog.md`.

### Done — 2026-07-30 (TS-115 / TS-155 / TS-156: production guard, Stripe URLs, and webhook verifier)

- Extended the production startup guard to validate the JWT keypair, require
  `TS_REDIS_URL`, require a notification sender (SES or MSG91), enforce the
  payment-provider + webhook-secret pairing, and validate cookie `SameSite`/`Secure`
  policy.
- Added `TS_APP_URL` and made Stripe checkout `success_url`/`cancel_url` derive
  from it instead of hardcoded `example.com`.
- Narrowed `verify_stripe_signature` to catch only `SignatureVerificationError`
  and `ValueError`; SDK/runtime errors now propagate.
- Updated `specs/modules/core.md`, `specs/modules/billing.md`, and `tasks/backlog.md`.

### Done — 2026-07-30 (TS-154 / TS-144: CORS/allowed-hosts wildcard guard and filename sanitization)

- Production startup guard now rejects wildcard (`*`) in `TS_CORS_ORIGINS` and
  `TS_ALLOWED_HOSTS` even when hidden in a comma-separated list.
- Added `app.core.storage.sanitize_filename` and applied it to storage keys and the
  `/api/files/{key}` `Content-Disposition` header to prevent response-splitting.
- Updated `specs/modules/core.md`, `tests/test_main.py`, and `tasks/backlog.md`.

### Done — 2026-07-30 (TS-108: observability, health probes, and backup/rollback docs)

- Added `/api/health/live` (liveness) and `/api/health/ready` (readiness) endpoints.
- `/api/health/ready` probes DB, Redis, storage, and the Celery broker and returns 503 when
  any critical dependency is unreachable.
- Added `/api/health/metrics` with Prometheus-compatible request/latency metrics collected by
  `MetricsMiddleware`.
- Added optional Sentry integration via `TS_SENTRY_DSN`, loaded only when `sentry-sdk` is
  installed.
- Documented observability, backup/restore, rollback, and alerting in `docs/deployment.md`.
- Updated `specs/modules/health.md` and `tests/test_health.py`.

### Done — 2026-07-30 (TS-103: align `/auth/workspaces` response and generate TS client)

- `AuthService.list_workspaces` now returns `country` and `plan` alongside `workspace_id`,
  `name`, and `role`.
- Auth router endpoints now declare Pydantic `response_model` classes (tokens, workspaces,
  members, invitations, settings, MFA) so the OpenAPI schema is complete.
- Added `openapi-typescript` to the frontend and generated `frontend/lib/api-types.ts`.
- `frontend/lib/api.ts` now imports auth response types from `lib/api-types.ts`, removing
  hand-rolled mismatches for `/auth` endpoints.
- Added `npm run generate:api` to regenerate the typed client from a running backend.
- Updated `specs/frontend.md` and `specs/modules/auth.md`.

### Done — 2026-07-30 (TS-109: enforce plan seat limits)

- `AuthService` now enforces workspace seat caps in `add_workspace_member`,
  `create_invitation`, and `accept_invitation`.
- A pending invitation reserves a seat; acceptance swaps it for an active member seat.
- Billing module publishes `billing.seat_limits` from `plans.py` through the registry;
  auth falls back to a hard-coded map if billing is disabled.
- Fixed `accept_invitation` under account-level sessions by prefixing the dev/test token
  with `workspace_id:<random>` so RLS can be bound to the invitation's workspace
  before lookup.
- Updated `specs/modules/auth.md` and `specs/modules/billing.md`.

### Next

- TS-103 — regenerate the TypeScript API client from the updated OpenAPI schema and
  remove hand-rolled API response mismatches.
- TS-108 — Observability (metrics, health probes, backup/rollback docs).
- TS-133..TS-162 — remaining medium/low audit follow-ups.

### Done — 2026-07-29 (TS-132: 61-finding implementation tracker)

- Generated `tasks/audit_fix_tracker.md` mapping every `TS-*` finding to its requirement,
  recommended solution, and task ID.
- Added 30 implementation task rows (TS-133..TS-162) to `tasks/backlog.md` for findings
  that did not already have a fix task.
- Added `scripts/build_audit_tracker.py` to regenerate the tracker from
  `PRODUCTION_READINESS_AUDIT.md`.

### Done — 2026-07-29 (TS-096: Google OIDC role fix)

- `AuthService.google_login` now issues tokens with the user's actual workspace role
  (queried from `WorkspaceMember`) instead of the hardcoded `"owner"` literal.
- Added `specs/modules/auth.md` acceptance criterion A13 covering OIDC role binding.

### Done — 2026-07-29 (TS-095: workspace-scoped member addition)

- `POST /api/auth/workspaces/{workspace_id}/members` now verifies the caller's
  `principal.workspace_id` matches `{workspace_id}` (super-admins bypass), preventing
  any admin of one workspace from joining or adding members to another workspace.
- Added `specs/modules/auth.md` acceptance criterion A14 covering workspace binding.

### Done — 2026-07-29 (TS-123: resend-verification no longer leaks token)

- `POST /api/auth/resend-verification` now returns `{"status": "ok"}` and no longer
  echoes the raw verification token.
- Updated `tests/test_auth_module.py` `_login` helper to mark test users verified
  directly in the DB since the route no longer exposes the token.
- Added `specs/modules/auth.md` acceptance criterion A15.

### Done — 2026-07-29 (TS-122: switch_workspace persists rotated refresh token)

- `AuthService.switch_workspace` now commits after issuing the rotated refresh
  token, so the new `RefreshToken` row and the `used_at` mark on the old row are
  persisted.
- Added `specs/modules/auth.md` acceptance criterion A16.

### Done — 2026-07-29 (TS-100: Google account linking on existing email)

- `AuthService.google_login` now looks up an existing user by verified email and
  links the `google_sub` instead of crashing with an `IntegrityError`/500.
- Added `email_not_verified` error mapping and `specs/modules/auth.md` A17.

### Done — 2026-07-29 (TS-099: cross-tenant member list isolation)

- `list_workspace_members` and `list_project_members` now require the caller to
  be a member of the target workspace (or super-admin) before returning emails/roles.
- Added `specs/modules/auth.md` acceptance criterion A18.

### Done — 2026-07-29 (TS-124: Dockerfile runtime extras)

- `backend/Dockerfile` now installs all runtime extras (`storage`, `redis`,
  `celery`, `billing`, `scheduler`, `ocr`, `auth`) plus `uvicorn`, instead of
  only `dev`/`storage`/`redis`.
- Created `specs/deployment.md` covering production image requirements.

### Done — 2026-07-29 (TS-129: invitation project_id verification)

- `create_invitation` now rejects a `project_id` that does not belong to the
  invitation's workspace.
- `accept_invitation` also verifies project/workspace consistency before adding
  a `ProjectMember`.
- Added `specs/modules/auth.md` acceptance criterion A19.

### Done — 2026-07-29 (TS-098: server-owned billing prices + webhook validation)

- `POST /api/billing/checkout` no longer trusts the client `amount_minor`; it
  uses the server price table in `plans.py` and rejects mismatches.
- `process_razorpay_webhook` and `process_stripe_webhook` validate the paid
  amount against the server price table before activating a plan or crediting
  a paygo review.
- Added `SUBSCRIPTION_PRICES` currency/plan table and `PAYGO_PRICE_INR_PAISE`.
- Added `specs/modules/billing.md` B11 and A5.

### Done — 2026-07-29 (TS-136 / TS-149: valid Anthropic model identifiers)

- Replaced the invalid `claude-sonnet-5` default with `claude-3-5-sonnet-20241022`
  in both `AnthropicClassifier` and `AnthropicAgent`.
- Added `specs/modules/risk.md` A6 and `specs/modules/assistant.md` A3.

### Done — 2026-07-29 (TS-162: severity evaluator missing-fact safety)

- `severity.evaluate_severity` now raises on missing facts instead of silently
  defaulting to `0`/`False`; the top-level `try/except` falls back to the safe
  `default` severity.
- Updated `tests/test_risk.py` to expect fallback behavior.
- Added `specs/modules/risk.md` A7.

### Done — 2026-07-29 (TS-104: rate limiting hardening)

- `RedisRateLimitStorage` now uses wall-clock `time.time()` scores (comparable
  across workers), atomic add-only-under-limit Lua scripts, and unique members
  per attempt.
- `RateLimitDep` prefers the rightmost `X-Forwarded-For` entry and falls back to
  the transport peer.
- Added `specs/modules/core.md` B7/A10.

### Done — 2026-07-29 (TS-105: webhook atomicity)

- `process_razorpay_webhook` and `process_stripe_webhook` now claim the
  `WebhookEvent` idempotency marker via a savepoint, apply the billing effect
  with `commit=False`, and commit everything in one transaction.
- `WorkspaceAdmin.set_plan` and `BillingService` helpers accept `commit=False` for
  callers that manage the transaction boundary.
- Added `specs/modules/billing.md` B12/A6.

### Done — 2026-07-29 (TS-126: hash invitation tokens at rest)

- `Invitation.token` renamed to `token_hash`; raw tokens are generated with
  `secrets.token_urlsafe` and stored as SHA-256.
- `accept_invitation` hashes the supplied token before lookup.
- Added `specs/modules/auth.md` B17/A20.

### Done — 2026-07-29 (TS-127: verify TOTP before completing enrollment)

- Added `User.mfa_totp_pending_secret` and changed `mfa_method` default to empty.
- `mfa_enroll` for TOTP stores the secret pending and returns the provisioning URI.
- `mfa_verify` confirms the first TOTP code, then commits `mfa_method="totp"` and
  moves the secret to `mfa_totp_secret`.
- Added `specs/modules/auth.md` B8/A21.

### Done — 2026-07-29 (TS-101 / TS-102: upload size cap + SSE hardening)

- `POST /api/ingestion/opportunities/{id}/upload` now reads at most
  `MAX_UPLOAD_SIZES[suffix] + 1` bytes and returns 413 before buffering the full
  oversized file.
- SSE document-processing stream now uses an async generator with `await`
  disconnect checks, `asyncio.sleep(0.5)` polling, and a 600-second hard timeout.
- Updated `specs/modules/ingestion.md` B7, B11, A4, A7.

### Done — 2026-07-29 (TS-094: end-to-end production readiness audit)

- **TS-094** — Full end-to-end production readiness audit of trunk
  (`claude/dev-workflow-modules-58dpqw`, commit `d651d00`). **Audit only — no source
  files were changed.** `PRODUCTION_READINESS_AUDIT.md` was rewritten and now supersedes
  the previous report, whose `F26`–`F41` findings are retired (four no longer reproduce:
  `.env.*` templates exist, tus `PATCH` and the SSE endpoint are authenticated, and S3
  calls no longer block the event loop).
  - **Recommendation: NO-GO** — 24 findings (4 Critical, 7 High, 9 Medium, 4 Low),
    9 release-blocking.
  - **Four exploits reproduced end-to-end** against the running app via `TestClient`:
    - Any verified user can add themselves as `owner` to **any** workspace by UUID —
      `add_workspace_member` applies the caller's own token role to a path-supplied
      workspace with no membership check (full cross-tenant takeover).
    - `POST /api/auth/google` mints `role="owner"` for every user because the role is a
      hardcoded string literal; a `viewer` was escalated to `owner`.
    - `GET /auth/workspaces/{id}/members` and `GET /auth/projects/{id}/members` return
      foreign tenants' member emails and roles.
    - Google sign-in with an email that already has a password account raises an
      unhandled `IntegrityError` (HTTP 500) — no account linking.
  - **Row-level security is structurally inoperative**: `ENABLE` without `FORCE` (the app
    role owns the tables, so policies are bypassed), `USING` without `WITH CHECK`,
    `current_setting()` without the missing-OK argument, and `workspace_members` /
    `project_members` carry no policy at all. Not verified against PostgreSQL — none was
    available — and no test in the suite exercises RLS, since all 145 tests run on SQLite.
  - **Billing accepts a client-supplied price**: `checkout.amount_minor` flows to the
    provider unchecked, and the webhook activates a plan without ever comparing the amount
    paid to the plan price — a ₹1 payment activates the ₹14,999/month plan with a
    genuinely valid signature. Plan seat limits are defined but never read anywhere.
  - Also confirmed: unbounded in-memory upload buffering before the size check; an SSE
    progress loop that busy-spins a threadpool worker with no sleep, disconnect check, or
    timeout; a Redis rate limiter keyed on `time.monotonic()` (meaningless across
    processes) with no proxy-header handling; non-atomic, racy webhook idempotency; and a
    `/auth/workspaces` response shape the frontend client cannot consume.
  - **Verified as working** (reported as defenses, not assumptions): path traversal in
    `/api/files` blocked across three variants; workspace switching correctly enforces
    membership; no real secrets in any committed `.env.*` file; SQL injection surface clean;
    the three artifact validators genuinely enforce the no-invented-quotes/clauses/numbers
    invariants; domain services filter on `workspace_id` consistently.
  - Baseline recorded: `ruff` clean, `mypy` clean (143 files), 145 backend tests passing,
    frontend lint/typecheck/build clean, `npm audit` 0 vulnerabilities.
  - Product gaps identified: no team-management UI, no account/security settings UI, no
    member removal or invitation revocation, no data export/deletion, and an audit log
    covering only finding decisions.

### Done — 2026-07-29 (TS-121: second-round production readiness audit)

- **TS-121** — Second-round end-to-end re-audit of trunk (`d651d00`) per
  `END_TO_END_PRODUCTION_AUDIT_PROMPT.md`. **Audit only — no source files were changed.**
  `PRODUCTION_READINESS_AUDIT.md` updated with:
  - Re-verification that all first-round `TS-*` findings still reproduce.
  - Six new findings: `TS-A06` (workspace switch refresh token not committed),
    `TS-A07` (`resend-verification` leaks raw token), `TS-O04` (Dockerfile missing
    runtime extras), `TS-A08` (invitation token stored plaintext), `TS-A09` (TOTP
    enrollment lacks verification), and `TS-P02` (rulepacks still unvalidated; paying
    workspaces receive zero findings).
  - Updated counts: **30 findings (5 Critical, 10 High, 11 Medium, 4 Low), 13 release-blocking**.
  - Updated remediation plan and final recommendation remains **NO-GO**.
  - Baseline recorded: `ruff` clean, `mypy` clean (143 files), 145 backend tests passing,
    frontend lint/typecheck/build clean, `npm audit` 0 vulnerabilities, `pip-audit` 0.

### Done — 2026-07-29 (TS-130: fifth-round production readiness audit rerun)

- **TS-130** — Fifth-round end-to-end re-audit of trunk (`claude/dev-workflow-modules-58dpqw`) per
  `END_TO_END_PRODUCTION_AUDIT_PROMPT.md`. **Audit only — no source files were changed.**
  `PRODUCTION_READINESS_AUDIT.md` updated with:
  - All prior `TS-*` findings re-verified and still present.
  - Eight new findings: `TS-N02` (notifications scheduler calls missing `WorkspaceAdmin` method),
    `TS-I08` (async `process_document` does not classify/segment or use OCR),
    `TS-I07` (`register_document` accepts unbounded `sample_text` with synchronous processing),
    `TS-R02` (risk classifier default Anthropic model name is invalid),
    `TS-A14` (assistant agent default Anthropic model name is invalid),
    `TS-A15` (`review` audit trail ignores `opportunity_id` and `AuditLog` lacks the column),
    `TS-B06` (`Artifact.version` read-modify-write race), and
    `TS-D03` (timeline ICS export appends `Z` to naive/local datetimes).
  - Updated counts: **51 findings (5 Critical, 15 High, 27 Medium, 4 Low), 18 release-blocking**.
  - Updated remediation plan and final recommendation remains **NO-GO**.
  - Baseline recorded: `ruff` clean, `mypy` clean (143 files), 145 backend tests passing,
    frontend lint/typecheck/build clean, `npm audit` 0 vulnerabilities, `pip-audit` 0.

### Done — 2026-07-29 (TS-131: sixth-round production readiness audit rerun)

- **TS-131** — Sixth-round end-to-end re-audit of trunk (`claude/dev-workflow-modules-58dpqw`) per
  `END_TO_END_PRODUCTION_AUDIT_PROMPT.md`. **Audit only — no source files were changed.**
  `PRODUCTION_READINESS_AUDIT.md` updated with:
  - All prior `TS-*` findings re-verified and still present.
  - Six new findings: `TS-S04` (`LocalStorage` async methods run synchronous file I/O),
    `TS-O05` (production guard allows a comma-separated wildcard in `CORS`/`allowed_hosts`),
    `TS-B07` (Stripe checkout hardcodes `example.com` redirect URLs),
    `TS-B08` (Stripe webhook verifier swallows all exceptions),
    `TS-I09` (tus endpoints perform synchronous file I/O and `OPTIONS` is non-compliant),
    and `TS-A16` (`review_finding` does not scope by `opportunity_id`).
  - Updated counts: **57 findings (5 Critical, 15 High, 33 Medium, 4 Low), 18 release-blocking**.
  - Updated remediation plan and final recommendation remains **NO-GO**.
  - Baseline recorded: `ruff` clean, `mypy` clean (143 files), 145 backend tests passing,
    frontend lint/typecheck/build clean, `npm audit` 0 vulnerabilities, `pip-audit` 0.

### Done — 2026-07-29 (TS-132: seventh-round production readiness audit rerun)

- **TS-132** — Seventh-round end-to-end re-audit of trunk (`claude/dev-workflow-modules-58dpqw`) per
  `END_TO_END_PRODUCTION_AUDIT_PROMPT.md`. **Audit only — no source files were changed.**
  `PRODUCTION_READINESS_AUDIT.md` updated with:
  - All prior `TS-*` findings re-verified and still present.
  - Four new findings: `TS-C01` (monetary amounts represented as `float` / `Numeric(16,2)` major units),
    `TS-I10` (XLSX/CSV ingestion loses page provenance), `TS-A17` (email/password login selects an
    arbitrary workspace for multi-workspace users), and `TS-R03` (severity evaluator silently defaults
    missing facts to `0`).
  - Updated counts: **61 findings (5 Critical, 15 High, 37 Medium, 4 Low), 18 release-blocking**.
  - Updated remediation plan and final recommendation remains **NO-GO**.
  - Baseline recorded: `ruff` clean, `mypy` clean (143 files), 145 backend tests passing,
    frontend lint/typecheck/build clean, `npm audit` 0 vulnerabilities, `pip-audit` 0.

### Next

Fix in order — the four blockers first (`TS-095` cross-workspace member add, `TS-096`
Google role escalation, `TS-098` billing price validation, then `TS-097` RLS, which
carries the highest regression risk and needs PostgreSQL in CI plus a staging soak).
Then the High findings `TS-099`–`TS-105`, and the launch-required product gaps `TS-106`
(team management) and `TS-107` (account settings). The second-round audit adds the
following to the launch-critical list: `TS-122` (workspace switch refresh persistence),
`TS-123` (resend-verification token leak), `TS-124` (Dockerfile runtime extras), `TS-125`
(rulepack validation / beta flag), `TS-126` (hash invitation tokens), and `TS-127` (TOTP
verification before enrollment). Every fix needs a regression test; `TS-097` cannot be
marked done until RLS is verified against a real PostgreSQL instance using a non-owner
application role. Six product questions (§3.6 of the report) need answers before `TS-097`,
`TS-100`, `TS-098`, `TS-109`, and `TS-111` can be finalised.

### Done — 2026-07-29 (older requirements completed: TS-033..TS-037, TS-043..TS-045, TS-079)

- **TS-033** — Minimal tus 1.0 resumable upload server at `/api/ingestion/tus`:
  creation (`POST /`), chunked upload (`PATCH /{id}`), and offset query (`HEAD /{id}`).
  Completed uploads are validated, stored, and processed (sync or async via Celery).
- **TS-034** — Celery + Redis async page-streamed processing:
  - Added `app.core.celery` with `make_celery_app`; falls back to eager execution when
    `TS_REDIS_URL` is unset.
  - Added `ingestion.tasks.process_document` which loads the stored file, extracts text,
    persists `doc_chunks`, and extracts deadlines while publishing `PROGRESS` state.
  - Added SSE stream endpoint `/api/ingestion/opportunities/{id}/documents/{id}/stream?task_id=...`.
  - `POST /api/ingestion/opportunities/{id}/upload?async=1` stores the file, creates a
    pending document, and enqueues processing.
- **TS-035 / TS-079** — Real email/SMS sender adapters for MFA and OTP:
  - `Msg91Sender` and `SesSender` are already in `notifications.adapters` and degrade to
    console logging without credentials.
  - `AuthService` now sends `email`/`sms` one-time codes during login/MFA enrolment using
    the configured `notifications.sender`.
- **TS-036** — Google OIDC login and phone OTP:
  - Added `POST /api/auth/google` with `google.auth` verification against Google's JWKS.
  - New `GoogleClient` in `app.modules.auth.google` and `google_*` settings in `app.core.config`.
  - Phone OTP is supported through `mfa_enroll` with `method=sms` and the MSG91 sender.
- **TS-037** — Live Razorpay + Stripe provider integration:
  - `RazorpayProvider` and `StripeProvider` create real orders/sessions when keys are set;
  otherwise deterministic mock handles are returned.
  - Added `POST /api/billing/webhooks/stripe` with signature verification and idempotent
    `checkout.session.completed` processing (records usage, creates invoices, sets plan).
  - Added `stripe_webhook_secret` to `Settings`.
- **TS-043** — Deadline-countdown alerts driven by the notice register:
  - `notifications.module` registers a daily scheduler job that scans every workspace for
    unconfirmed deadlines within the next 7 days and emails workspace members.
  - `WorkspaceAdmin.list_members` added to support recipient lookup.
- **TS-044** — Award-document ingestion for award baseline:
  - Added `AwardDocument` model + migration and `POST /api/baseline/opportunities/{id}/award-document`.
  - `BaselineService.freeze(source="award")` now pulls from the latest award letter text and
    includes an `award_text_preview` in the snapshot.
- **TS-045** — Handover-pack file export (DOCX/PDF/XLSX):
  - Added `render_handover_pack` to `export/render.py`.
  - Added `ExportService.export_handover` and `GET /api/baseline/opportunities/{id}/handover/export?format=...`.
  - Exports include the sealed hash, key obligations, notice register, gaps, and deadlines.

### Done — 2026-07-29 (TS-128: third-round production readiness audit rerun)

- **TS-128** — Third-round end-to-end re-audit of trunk (`d651d00`) per
  `END_TO_END_PRODUCTION_AUDIT_PROMPT.md`, run from scratch on a fresh branch.
  **Audit only — no source files were changed.** `PRODUCTION_READINESS_AUDIT.md` updated with:
  - All prior `TS-*` findings re-verified and still present.
  - One new finding: `TS-A10` (`create_invitation` / `accept_invitation` accepts an
    arbitrary `project_id` and adds the invitee as a member of a project in a foreign
    workspace, granting cross-tenant project read access).
  - Updated counts: **31 findings (5 Critical, 11 High, 11 Medium, 4 Low), 14 release-blocking**.
  - Updated remediation plan and final recommendation remains **NO-GO**.
  - Baseline recorded: `ruff` clean, `mypy` clean (143 files), 145 backend tests passing,
    frontend lint/typecheck/build clean, `npm audit` 0 vulnerabilities, `pip-audit` 0.

### Next

- Add `TS-129` to the launch-critical fix list: `create_invitation` and
  `accept_invitation` must verify that `project_id` belongs to the invitation's
  workspace before persisting the `ProjectMember` row.
- Fix in order — the four blockers first (`TS-095` cross-workspace member add, `TS-096`
  Google role escalation, `TS-098` billing price validation, then `TS-097` RLS), followed
  by High findings `TS-099`–`TS-105` and `TS-A10` (TS-129), and the launch-required
  product gaps `TS-106` (team management) and `TS-107` (account settings).

### Done — 2026-07-29 (production readiness audit fixes: TS-083..TS-084)

- **TS-083** — Production security hardening:
  - `Settings` now uses `SecretStr` for all secrets and adds `TS_ENV`, `TS_ALLOWED_HOSTS`,
    `TS_CORS_ORIGINS` enforcement, `TS_STORAGE_TYPE`/`s3_*`, and `TS_REDIS_URL`.
  - `create_app` validates production settings: no default Razorpay webhook secret,
    explicit CORS/allowed-hosts, and configured JWT keys.
  - Added security headers middleware (CSP, HSTS in prod, X-Frame-Options, etc.).
  - Added `HTTPSRedirectMiddleware` and `TrustedHostMiddleware` in production.
  - Split health endpoint: `GET /api/health` is public and minimal; `GET /api/health/details`
    exposes module/capability metadata and is gated by auth (super-admin in production,
    authenticated in non-production, public when auth is disabled).
  - Updated affected tests to use `/api/health/details`.
- **TS-084** — Auth session/MFA hardening:
  - Refresh tokens are now returned as `httpOnly`, `Secure` (prod), `SameSite=Lax`
    cookies named `refresh_token`; `/api/auth/refresh` and `/logout` read them from
    cookies. The JSON response no longer contains `refresh_token`.
  - Added `/api/auth/mfa/challenge`; when `User.mfa_totp_secret` is set, `/login` returns
    `mfa_required` and a short-lived `mfa_token` instead of final tokens.
  - Added `/api/auth/workspaces/{id}/switch` to rotate refresh and reissue access for the
    selected workspace.
  - Added password policy: ≥8 chars, uppercase, lowercase, digit, symbol, and a blocklist
    of trivial passwords.
  - Added account lockout: 5 failed login attempts within 15 minutes lock the account for
    15 minutes, stored in new `users.failed_login_attempts` and `users.locked_until` columns.
  - Migration `64f9e4b70eda` adds the lockout columns.
  - Updated test suite to use strong passwords and cookie-based refresh flow.

### Done — 2026-07-29 (production readiness audit fixes: TS-086..TS-087)

- **TS-086** — File upload/storage hardening:
  - Added `app.core.storage` with MIME/magic/size validation, extension blocklist,
    and per-file-type limits. BOQ uploads are capped at 10 MB.
  - Added `LocalStorage` (default dev) and `S3Storage` (credential-gated) adapters;
    `TS_STORAGE_TYPE=s3` activates S3 with fallback to local on failure.
  - Added stub virus-scan hook (`_scan_stub`) so a real scanner/ClamAV integration can
    be swapped in later.
  - Wired `validate_and_store` into `ingestion` and `boq` upload routes.
- **TS-087** — Risk/export quality:
  - `RiskService.run_opportunity` now passes `validated_only=True` to rule-packs when
    the workspace is on a paid plan (`pro`, `enterprise`, `paygo`, `team`).
  - `ExportService.export` pulls the last reviewer from the audit log and includes
    `reviewed_by_email` and `reviewed_at` in the pack stamp.
  - Added tamper-evident SHA-256 integrity hash to the export stamp.
  - Replaced `datetime.utcnow()` in `comparison/service.py` with timezone-safe logic.

### Done — 2026-07-29 (production readiness audit fixes: TS-089..TS-090)

- **TS-089** — Deployment/DevEx:
  - Added `.env.local`, `.env.dev`, and `.env.prod` templates covering all `TS_*`
    settings (database, CORS, allowed hosts, auth keys, storage/S3, billing, Redis, OCR/LLM).
  - Updated `.env.example` to match the new settings.
  - `docker-compose.yml` now uses `.env.local`, mounts `backend_storage`, and sets
    `TS_STORAGE_DIR` to `/app/storage`.
  - `backend/Dockerfile` installs `storage` + `redis` extras.
- **TS-090** — CI/tooling:
  - Backend CI now runs `ruff`, `mypy`, `pip-audit`, `pytest`, and Alembic up/down checks.
  - Frontend CI now runs `npm run lint`, `npm run typecheck`, `npm audit`, and `npm run build`.
  - Added `mypy` config to `pyproject.toml` (permissive baseline to avoid existing noise).
  - Added ESLint config and `lint` / `typecheck` scripts to `frontend/package.json`.
  - Resolved `postcss`/`sharp`/`brace-expansion` npm audit warnings via `overrides`.

### Done — 2026-07-29 (production readiness audit fixes: TS-091)

- **TS-091** — Notification/payment adapter skeletons:
  - Added `app.modules.notifications.adapters` with `SesSender` and `Msg91Sender`
    that fall back to console logging when credentials are absent.
  - Added `app.modules.billing.providers` with `RazorpayProvider` and `StripeProvider`
    that return mock handles without live keys.
  - Added `app.core.scheduler` (APScheduler optional) and wired it into `create_app`
    lifespan; `notifications` registers a daily digest stub job.
  - Added provider/notification settings to `app.core.config`.
  - Added `billing` and `scheduler` optional extras to `pyproject.toml`.

### Done — 2026-07-29 (production readiness audit fixes: TS-085, TS-088, TS-092)

- **TS-085** — Workspace switcher:
  - `SessionProvider` now fetches `/auth/workspaces` and exposes `switchWorkspace`.
  - Header includes a workspace dropdown when the user belongs to multiple workspaces.
- **TS-088** — Frontend cleanup:
  - Removed hardcoded `SAMPLE` tender and `SAMPLE_BOQ` from the opportunity workbench.
  - Replaced the sample tender button with a real file upload (`<input type="file">`) wired to
    `/ingestion/opportunities/{id}/upload`.
  - Replaced the sample BOQ button with a CSV textarea.
  - Removed the unverified "Hosted in India" claim from the landing page.
  - Added `/billing` page (plan/usage, invoices, checkout) and `/admin` link.
  - `api.ts` now sends `credentials: "include"` so httpOnly cookies travel with every request.
- **TS-092** — Admin console and analytics UI:
  - Added `/admin` superadmin page listing users and workspaces, with a superadmin toggle.
  - Added per-opportunity **Audit** tab on the workbench using `/review/opportunities/{id}/audit`.
  - Added `/analytics` dashboard showing opportunity risk counts, BOQ defects, and export readiness.

### Done — 2026-07-29 (production readiness audit quick wins: TS-093)

- **TS-093** — Implemented quick-win fixes from `PRODUCTION_READINESS_AUDIT.md` F26–F42:
  - Added `.env.local`, `.env.dev`, and `.env.prod` templates with no secrets and updated `.gitignore`.
  - Aligned frontend upload `accept` list with backend MIME/extension allow-list.
  - Made billing checkout currency-aware by `Workspace.country` (`IN` → `inr`, `AE`/`SA`/`QA`/`GB` → local currencies) and defaulted to `IN`.
  - Protected `GET /api/rulepacks` and `/api/rulepacks/{id}/patterns` with `require("viewer")`.
  - Authenticated the Celery SSE stream endpoint (`/api/ingestion/opportunities/{id}/documents/{id}/stream`) and scoped the document lookup.
  - Added `GET /api/files/{key:path}` download route enforcing workspace prefix isolation.
  - Made S3 initialization raise `StorageError` in production instead of silently falling back to local storage.
  - Added a Redis distributed lock around the deadline-alert scheduler tick (`notifications.module`).
  - Added email verification flow: `EmailVerification` model + migration, `POST /api/auth/verify-email`, `POST /api/auth/resend-verification`, `email_verified` claim in access/MFA tokens, and gated billing checkout + member invitations on `email_verified` (or super-admin).
  - Hardened tus `PATCH`/`HEAD` with auth, workspace scoping, and per-extension upload-size caps; enabled virus-scan stub path for BOQ uploads.
  - Moved S3 `put_object`/`get_object`/`delete_object`/`generate_presigned_url` calls to `asyncio.to_thread` to avoid blocking the event loop.
  - Added migration `df4721874c4d_add_email_verifications`.

### Next

- TS-094 — Replace `StorageError` in production with a real ClamAV/cloud virus-scan hook.
- TS-095 — End-to-end browser validation of signup, email verification, file upload, and payment flows.
- TS-096 — Rulepack validation by a QS/contracts expert against real tender sets (F27 remains open).

### Done — 2026-07-26 (real web validation + invitation fix: TS-080..TS-081)

- **TS-080** — Ran end-to-end browser validation against the local frontend + backend:
  - UI signup (`http://localhost:3000/login`) created a user, default workspace, and
    navigated to `/opportunities`.
  - Real `fetch` calls from the browser verified workspace CRUD, project CRUD,
    project-member listing, and super-admin 403 rejection.
- **TS-081** — Fixed `POST /api/auth/invitations/{token}/accept` raising
  `TypeError: can't compare offset-naive and offset-aware datetimes` on SQLite.
  `accept_invitation` now normalizes a naive `expires_at` to UTC before comparing.
  Added `test_invitation_flow` to `tests/test_auth_module.py`.

### Done — 2026-07-26 (password reset: TS-082)

- **TS-082** — Added forgot-password and reset-password flow:
  - New `password_resets` table with 15-minute single-use tokens stored as SHA-256 hashes.
  - `POST /api/auth/forgot-password` returns `ok` even for unknown emails to prevent
    enumeration; returns the raw token in dev/test until real email delivery is wired.
  - `POST /api/auth/reset-password` validates the token, enforces an 8-character minimum,
    hashes the new password with argon2id, and marks the token used.
  - Frontend: `/forgot-password` and `/reset-password?token=...` pages, plus a link
    from `/login`.
  - Added regression tests for reset, reuse, and expired-token rejection.

### Done — 2026-07-26 (workspace/project tenant refactor + super admin: TS-074..TS-078)

- **TS-074** — Spec for the workspace/project tenant refactor + super admin:
  `specs/workspace-and-admin-refactor.md`.
- **TS-075** — New auth data model: removed `org`/`org_members`, added `User`,
  `Workspace`/`WorkspaceMember`, `Project`/`ProjectMember`, `Invitation`, global
  `is_superadmin` flag, and `mfa_method`/`mfa_phone` on `User`.
- **TS-076** — Renamed `org_id` → `workspace_id` across all modules, RLS helpers,
  and `core.db`; regenerated the migration chain as
  `migrations/versions/e26e85245237_workspace_tenant.py` with workspace-scoped
  RLS policies for PostgreSQL.
- **TS-077** — Workspace/project CRUD, sharing/invites, MFA method selection, and
  super-admin endpoints:
  - `POST/GET /api/auth/workspaces`
  - `POST/GET /api/auth/workspaces/{id}/members`
  - `POST/GET /api/auth/workspaces/{id}/projects`
  - `POST/GET /api/auth/projects/{id}/members`
  - `POST /api/auth/invitations` + `POST /api/auth/invitations/{token}/accept`
  - `POST /api/auth/mfa/enroll` + `POST /api/auth/mfa/verify`
  - `GET/POST /api/auth/admin/*` super-admin routes.
- **TS-078** — Updated `tests/test_auth_module.py` and frontend `api.ts` / `session.tsx`
  / `app/login/page.tsx` for `workspace_id`; verified `ruff`, `pytest`, `npm run build`,
  and `alembic upgrade head && downgrade base` all pass.
- Updated `README.md`, `docs/deployment.md`, `specs/modules/auth.md`, and
  `tasks/backlog.md` to reflect the new workspace/super-admin model.

### Done — 2026-07-26 (spec audit follow-up: Sprints 0–2)

- **TS-058..TS-070** — Spec-audit follow-up task IDs and `tasks/spec_audit_tracker.md` created.
- **TS-062** — `analytics` and `comparison` now publish `*.service_factory` capabilities
  via `module.py`, and their routers consume the factory when available.
- **TS-063** — Fixed route wording in `specs/modules/timeline.md` and `specs/modules/crossref.md`
  to match the implemented router paths.
- **TS-058..TS-061** — Added missing module specs:
  - `specs/modules/findings.md` (shared findings store and contract).
  - `specs/modules/export.md` (Bid Review Pack export with review gate).
  - `specs/modules/health.md` (health/capabilities endpoint).
  - `specs/modules/notifications.md` (deadline-digest sender abstraction).
- **TS-059 (code)** — `export` now publishes `export.service_factory` and the router
  consumes it, matching the pluggable pattern.
- **TS-064..TS-066** — Aligned `ingestion`, `risk`, and `drafting` public-interface
  specs with the capabilities and routes actually implemented.
- **TS-067** — Added tests for `export`, `health`, and `notifications`:
  - `test_export.py` covers review-gated XLSX export and bad-format handling.
  - `test_health.py` covers the `/api/health` module/capability report.
  - `test_notifications.py` covers deadline alert thresholds and `ConsoleSender`.

### Done — 2026-07-26 (Sprint 4 complete + TS-071)

- **TS-068** — Implemented `ingestion.doc_chunks` table + migration and the
  `ingestion.doc_text` capability (`DocTextService`), plus `GET /api/ingestion/documents/{id}/text`.
- **TS-070** — Added `invoices` table + migration, `GET /api/billing/invoices`, and the
  `billing.record_usage` capability; Razorpay `order.paid`/`subscription.charged` now generate a paid invoice.
- **TS-069** — Implemented assistant chat sessions (`chat_sessions` + `chat_messages`),
  history endpoints, and SSE `/api/assistant/sessions/{id}/stream`.
- **TS-071** — Implemented Sign in with Apple backend skeleton: `users.apple_id`,
  `GET /api/auth/apple/authorize`, `POST /api/auth/apple/callback`, client-secret
  generation, and id_token verification. Disabled until Apple Developer credentials
  are configured (`TS_APPLE_*`).
- Added integration tests for billing, ingestion doc chunks, assistant sessions, and
  Apple sign-in.

### Done — 2026-07-26 (Devin rules: TS-073)

- **TS-073** — Created `.devin/rules/*.mdc` and `DEVIN.md` so Devin follows the same
  mandatory workflow, architecture, and spec conventions as Cursor/Claude. Updated
  `CLAUDE.md` and `.cursor/rules/00-workflow.mdc` to reference the Devin rules.

### Done — 2026-07-26 (deployment helpers: TS-072)

- **TS-072** — Added `.env.local`, `.env.dev`, `.env.prod`, `scripts/run.sh`, and
  `docs/deployment.md` with local / Docker / prod setup instructions.

### Next

- TS-079 — Wire real email/SMS delivery for `email`/`sms` MFA methods, OTP codes, and
  password-reset links (replace dev-only token return).
- TS-036 — Complete Google OIDC login (`/api/auth/google/callback`) and live
  messaging-provider credentials.
- Configure Apple Developer credentials and test end-to-end Sign in with Apple.

### Done — 2026-07-26 (session 23 continued: TS-057)

- **TS-057** — Internal Accuracy Dashboard:
  - New `analytics` module with `GET /api/analytics/accuracy` (admin/owner only).
  - Aggregates review outcomes from the shared findings table and produces
    per-pattern and per-source precision proxies, false-positive counts, and
    a most-rejected patterns list.
  - Recall and true false negatives are reported as `null` because they require
    an external golden-label set; the shape is ready for that feed.
  - Added `FindingStore.list_for_org` to support org-wide analytics without
    direct table imports.
  - `specs/modules/analytics.md` and `tests/test_analytics.py` added.

### Next

- Phase 1 accuracy gate: validate the Bid Readiness score and weights against a
  real tender set and QS sign-off; no Phase-2 expansion until ≥70% QS acceptance.
- Golden-label import for true precision/recall in `analytics` (TS-057 follow-up).

### Done — 2026-07-26 (session 23 continued: TS-050)

- **TS-050** — Tender Comparison:
  - New `comparison` module with `GET /api/comparison/opportunities` returning a
    portfolio ranking table.
  - Aggregates per-opportunity counts (risk by severity, qualification gaps,
    BOQ defects, standard violations), earliest submission deadline, and the
    latest `bid_decision` score/recommendation from `drafting`.
  - Deterministic priority ranking: `proceed` > `proceed_with_conditions` >
    `do_not_proceed` > none, then bid score desc, critical risk asc,
    days-to-submission asc.
  - `specs/modules/comparison.md` and `tests/test_comparison.py` added.

### Done — 2026-07-26 (session 23 continued: TS-053 + TS-051)

- **TS-053** — Clause Cross-Reference:
  - New `crossref` module with `CrossRefService` and routes
    `GET /api/crossref/opportunities/{id}?q=...&limit=...`.
  - Token-level search across every clause in an opportunity, ranked by overlap,
    with provenance (document kind/filename, clause ref, heading, page, 300-char preview).
  - `specs/modules/crossref.md` and `tests/test_crossref.py` added.

- **TS-051** — Clause Change Detection:
  - `POST /api/crossref/opportunities/{id}/diff?document_id=...` compares two
    versions of a document and returns `added`, `removed`, and `changed` clauses.
  - Uses explicit `supersedes` chains when provided; falls back to the two most
    recent uploads of the same document kind.
  - Clause matching is deterministic: keyed by `clause_ref`, with text similarity
    on normalised clauses.
  - Wired into the ingestion clause store; no hard cross-module imports.

### Done — 2026-07-26 (session 23 continued: TS-048 + TS-049 + TS-052 + TS-054 + TS-055 + TS-056)

- **TS-052** — Tender Timeline:
  - New `timeline` module with `TimelineService` and routes
    `/api/timeline/opportunities/{id}/timeline` and `.ics` export.
  - Expanded `ingestion.deadlines` keywords to extract tender publication,
    technical/financial opening, EMD validity, BG submission, contract signing.
  - Timeline normalizes raw kinds to a canonical milestone vocabulary, includes a
    `tender_published` synthetic fallback, and sorts dated events.
  - `specs/modules/timeline.md` and `tests/test_timeline.py` added.

- **TS-049** — Qualification Compliance Matrix:
  - New `qualification` module with `QualificationService` and routes
    `GET/POST /api/qualification/opportunities/{id}`.
  - Deterministic extraction of 8 eligibility criteria (minimum turnover,
    similar project experience, equipment, engineer, certifications, EMD,
    bid security, experience years) with source quote + page.
  - Writes `qualification_gap` findings to the shared findings store; missing
    criteria are `not_met` (severity `high`), found criteria are `unknown`
    (severity `medium`) pending org evidence.
  - `specs/modules/qualification.md` and `tests/test_qualification.py` added.

- **TS-048** — Bid / No-Bid Recommendation:
  - Extended `drafting` to generate a `bid_decision` artifact from accepted
    findings only.
  - Deterministic score (0–100) with transparent weights over `risk_clause`,
    `qualification_gap`, `boq_defect`, and `standard_violation` findings.
  - Weights default to a documented table and can be overridden through the
    rule-pack playbook (`default_contractor.bid_decision_weights`).
  - Output: score, strengths, concerns, recommendation
    (`proceed` / `proceed_with_conditions` / `do_not_proceed`), and conditions.
  - Gated by review: no `proposed` or `needs_clarification` findings allowed.
  - Updated `specs/modules/drafting.md` and `tests/test_drafting.py`.

- **TS-056** — Organization Standards Enforcement:
  - Extended `standards` with `OrgCommercialStandard` (org-scoped, RLS) for
    per-org policy thresholds.
  - New routes:
    `GET/PUT/DELETE /api/standards/commercial/{key}` and
    `POST /api/standards/opportunities/{id}/check`.
  - `check_violations` extracts numbers from accepted findings (percent, days,
    amount) and returns violations; the endpoint persists `standard_violation`
    findings through the shared findings store.
  - `drafting` `bid_decision` consumes `standards.commercial_service_factory`
    and includes standard violations in score/concerns.
  - Updated `specs/modules/standards.md` and added `tests/test_standards.py`.

- **TS-054** — Risk Explainability:
  - `Finding` contract and `findings` table now carry an `explanation` JSON field.
  - `RiskPattern` schema accepts `industry_reason`; all five `in-works` India
    patterns updated with real, domain-appropriate reasons.
  - `risk.engine.run_pattern` builds an explanation object for every finding
    (`matched_pattern`, `evidence_quote`, `industry_reason`, `suggested_review`,
    `absence` flag).
  - `risk` and `review` API responses now include `explanation`.
  - Tests updated: `test_risk.py` asserts explanation shape.

- **TS-055** — Structured Review Outcomes:
  - `ReviewStatus` expanded: `accepted`, `edited`, `rejected`, `false_positive`,
    `needs_clarification`.
  - `findings` table and contract gain `review_reason`.
  - Review endpoint accepts `decision` + `review_reason`; audit logs both.
  - Export gate now blocks on `proposed` **and** `needs_clarification`.
  - Tests added for `false_positive`/`needs_clarification` and gate behavior.

- Migration `0012_review_explain.py` adds `review_reason` and `explanation`
  columns to `findings`; Alembic up/down verified.
- `specs/modules/risk.md` and `specs/modules/review.md` updated in the same change.
- `tasks/backlog.md` / `tasks/phase15_tracker.md`: TS-052, TS-054, TS-055 marked `done`.

### Done — 2026-07-26 (session 23: Phase 1.5 bid-decision extensions planning)

- Product requirements and roadmap for **Phase 1.5 — Bid-Decision Extensions**
  (`docs/TenderShield_Phase15_Extensions.md`). Maps the 10 requested
  capabilities to the existing modular architecture, defines domain/market
  rationale, priority, sprint sequencing, acceptance criteria, and module mapping.
- Task backlog updated with sequential IDs **TS-048…TS-057** for Bid / No-Bid
  Recommendation, Qualification Matrix, Tender Comparison, Clause Change
  Detection, Tender Timeline, Clause Cross-Reference, Risk Explainability,
  Structured Review Outcomes, Organization Standards Enforcement, and Internal
  Accuracy Dashboard (`tasks/backlog.md`).
- Progress tracker created (`tasks/phase15_tracker.md`) with sprint themes,
  acceptance gates, and blockers; Bid Decision Intelligence is the capstone
  feature with Sprint 0–2 inputs (explainability, review outcomes,
  qualification, timeline, org standards) sequenced first.

### Done — 2026-07-24 (session 22: org-custom standards + researched notice figures)

- **TS-047** — the third standards layer: a firm can publish **its own** notice
  regimes that either **prevail** over or run **side by side** with the
  universal + regional rule-pack standards (Doc §10 custom playbooks).
  - New pluggable `standards` module (backend): `org_notice_standards` table
    (org-scoped + RLS, one row/org), `GET/PUT/DELETE /api/standards/notice`
    (read = viewer, write = admin), boundary validation (bad mode → 400,
    duplicate keys → 409). Publishes `standards.org_notice_provider`.
  - `baseline` now merges three layers — universal → regional → org — when
    building the notice register + gaps. `prevail` overrides matching regimes
    (keeping base fields the org omits); `side_by_side` appends. Org regimes are
    tagged `origin="org"`; an expected org regime absent from a contract becomes
    a gap. Migration `0011`.
  - Frontend: `/standards` editor (mode toggle + editable regime rows), nav link,
    and a "your standard" badge on org-origin gaps in the Handover tab.
- **Researched, cited notice figures** (you asked me to do the QS research):
  the universal/India packs now carry real, sourced windows — **FIDIC 2017
  cl.20.2** (28-day notice / 84-day detailed claim), **NEC4 cl.61.3** (8-week /
  56-day compensation-event bar), **MSMED Act 2006 s.15** (45-day statutory
  payment cap), plus **CPWD cl.10CC** escalation and the hindrance-register EOT
  practice — with a `references.md`. All remain `confidence: unvalidated` pending
  a QS sign-off (Doc §14).
- Verified live (UI): the register shows the MSMED 45-day and CPWD 10CC figures
  from the India overlay, and a firm's own "Site handover" regime flowing through
  as an org-badged gap.
- 113 backend tests passing (7 new), ruff clean, frontend builds clean.

### Done — 2026-07-24 (session 21: layered contract-standards — universal-first, flexible)

- **TS-046** — the flexibility spine the geographic roadmap rides on: **layered
  notice standards** as versioned data (`rulepacks/in-works/notice_standards/`).
  - `base.yaml` (scope `universal`) defines the contract-form-agnostic notice
    regimes (claim, variation, EOT, payment, defect, termination, dispute) with
    typical windows, `expected` flags and keywords; `india.yaml` (scope `IN`) is
    an **overlay** that tightens the claim window (28→15d), retimes EOT to the
    hindrance-register practice, and adds the India-only escalation/star-rate
    regime.
  - `RulePackLoader.notice_standard(pack_id, region)` merges universal + regional:
    a regional category overrides the base **only in the fields it explicitly
    sets** (`exclude_unset`, so an omitted `expected` keeps the base value —
    this was a real bug, fixed), region-only categories append. **Adding a new
    market or an unexpected clause type is now a YAML file, not a code change** —
    the exact seam the future GCC (FIDIC) / UK (NEC/JCT) packs plug into.
  - The `baseline` notice register is now **standards-aware**: each extracted
    window is classified into a semantic category, and every *expected* regime
    with no window in the contract is flagged as a **gap** (the notice analogue
    of risk absence detection) — deterministic, no LLM. Region + gaps are frozen
    into the sealed snapshot and shown in the handover pack. Degrades to
    extraction-only when `rulepacks` is disabled.
  - Frontend Handover tab: "standard: universal + IN" badge, semantic categories,
    and an amber "expected notice regimes not found" panel.
  - Verified live (UI): a claims-only contract correctly flags Variation, EOT
    (hindrance-register, 15d), Payment, Termination and Price-escalation (30d) as
    gaps — the India overlay visibly in effect.
- 108 backend tests passing (3 new), ruff clean, frontend builds clean.

### Done — 2026-07-24 (session 20: Phase-2 baseline lock — end to end)

- **TS-041** — new pluggable `baseline` module (backend), the first Phase-2
  feature. At award it freezes the reviewed commercial state into an immutable,
  hash-sealed snapshot so tender knowledge survives handover (Doc §0.1 P2):
  - **Hash-sealed freeze** — SHA-256 over the canonical snapshot (accepted/edited
    findings with verbatim provenance + confirmed deadlines + opportunity meta).
    Append-only versions; `verify` recomputes the hash and reports tamper
    (the doc's "baseline freeze (hashes)" requirement).
  - **Freeze gate** — sealing is blocked until the `review` gate is satisfied
    (Doc §11.4), reusing the professional-liability spine; refused when `review`
    is disabled.
  - **Deterministic notice-rule register** — regex over the accepted findings
    **and the segmented contract clauses** extracts contractual notice windows
    ("within 14 days", "28 days' notice"), normalised to days, with page
    citations. No LLM (Doc §4) — populates from real contract text even with no
    API key. These seed the Phase-3 time-bar countdowns.
  - **Award-vs-tender delta** — diffs the latest tender seal against the latest
    award seal (added / dropped / changed findings). Deterministic.
  - **Commercial handover pack** — sealed hash, critical/high obligations, notice
    register and confirmed-deadline calendar from the latest baseline.
  - Cross-module only via capabilities (`findings`/`review`/`ingestion`); the app
    boots and Phase-1 flows pass with `baseline` disabled. Migration `0010`,
    org-scoped + RLS on PostgreSQL. 8 new tests (freeze gate, seal, verify,
    compare, handover, live-clause notice extraction).
- **TS-042** — frontend **Handover** tab on the opportunity workbench: freeze
  tender/award baselines (gated on review), sealed-baseline list with hashes,
  notice-rule register with citations, award-vs-tender delta, and the handover
  pack. Typed `baseline` client methods added.
- Verified end to end against a live server + browser: freeze refused before
  review (403), sealed v1 (64-char hash), `verify` intact, notice register
  extracting the 14-day and 28-day windows from clause text with p3 provenance,
  and the rendered Handover tab.
- 106 backend tests passing; ruff clean; frontend builds clean.
- **Phasing note:** the doc gates P2 behind the Phase-1 accuracy gate (§10);
  this ships as a config-flagged, fully decoupled module so it does not disturb
  Phase-1. The accuracy gate (5 real tenders + QS review) remains the real gate
  before P2 is *promoted*.

### Done — 2026-07-24 (session 19: in-app Help page + honest QS-lifecycle scope)

- **TS-040** — new static Help page at `/help` (`frontend/app/help/page.tsx`),
  linked from the header nav:
  - an 8-step **how-to-use** walkthrough (create workspace → open opportunity →
    upload full pack → confirm deadline wall → run risk review → run BOQ
    assurance → review/accept findings → generate & export);
  - the **rules it never breaks** (numbers from code not AI, every finding cited
    & quote-verified, human approves before export, data isolated per workspace);
  - an honest **QS-lifecycle coverage table** — states plainly that TenderShield
    owns the **pre-bid slice** (risk review, deadline extraction, BOQ arithmetic
    assurance, scope-gap detection, bid-decision artifacts) and deliberately does
    **not** do estimating, drawing take-off, BOQ authoring, interim valuations, or
    variations/claims/final account;
  - a not-legal / not-QS-certification **disclaimer** (Doc §11.4) reinforcing that
    findings are prompts for a qualified human, which is why the accept/reject
    step exists.
- **Scope framing corrected (same session):** the coverage table no longer
  flattens roadmap items into "not covered." It now uses three buckets —
  **Covered now** (Phase-1 pre-bid slice), **On the roadmap** (baseline lock,
  change/variation inbox + notice drafts, contractual time-bar engine incl.
  FIDIC 20.1 / NEC CE, cross-tender outcome graph — all from Doc §0.1/§1.2), and
  **Not ours** (takeoff, BIM/clash, live pricing, CPM, legal opinions — Doc §0.2).
  Added a "where it goes beyond typical QS tools" section (reads the contract,
  tracks the clock, playbook deviation, cross-tender learning, inspectable
  provenance, deterministic numbers). The AI assistant is not advertised since
  it is hidden from users.
- Spec `specs/frontend.md` updated (structure, B8, A2) to record the Help page,
  the hidden assistant, and human-label/typography decisions from session 18.
- Frontend builds clean; `/help` prerenders as static content.

### Done — 2026-07-24 (session 18: UI polish — hide assistant, human labels, fonts)

- **AI assistant hidden from users:** the Assistant tab, chat state, and handler
  removed from the opportunity workbench — user-facing tabs are now Overview /
  Risks / BOQ / Artifacts. (The backend module still exists; disable it fully by
  omitting `assistant` from `TS_ENABLED_MODULES`.)
- **No raw identifiers on screen:** new `lib/labels.ts` maps every internal code
  to a proper label — categories (`grand_total` → "Grand-total mismatch",
  `blank_rate` → "Blank rate", `ld` → "Liquidated damages", …), review status,
  deadline kinds, artifact kinds, opportunity status, doc kinds. Board + detail
  render through it; the BOQ tab label shows "BOQ" (not "Boq").
- **Proper typography:** app-wide Inter → system-UI font stack in Tailwind +
  legibility/feature settings in globals (drop in `next/font` Inter for an exact
  self-hosted face when building with network).

Frontend builds clean; backend unaffected (98 tests still passing).

### Done — 2026-07-23 (session 17: no-AWS scanned-table path)

- **TS-039** — the hard scanned-table BOQ case, **without AWS**: `RapidTableProvider`
  (rapid-table SLANet ONNX + RapidOCR, offline) reconstructs a table from a
  scanned/image BOQ page; a dependency-free HTML→rows parser + `scanned_boq_csv`
  maps it to canonical CSV; wired as the BOQ-upload fallback (`ingestion.scanned_boq_csv`,
  only when `TS_OCR_ENABLED`). The HTML→CSV conversion is unit-tested; the model
  downloads once on first use (blocked in this sandbox, so the recognition step is
  not sandbox-verified — works on a normal machine).
- **AWS is no longer required anywhere.** Textract removed as a dependency;
  TS-033 is now just tus resumable upload. Docs corrected. 99 tests passing.

### Done — 2026-07-23 (session 16: OCR + PDF table reading — no cloud)

- **TS-038** — real OCR + table extraction without AWS:
  - **pdfplumber** reads BOQ tables straight out of digital PDFs; new
    `POST /api/boq/opportunities/{id}/upload` accepts PDF/XLSX/CSV, detects the
    BOQ table, maps headers to canonical columns, and runs the deterministic
    checks. Tested end-to-end (duplicate + arithmetic caught from a PDF table).
  - pluggable **`OcrProvider`**: `RapidOcrProvider` (RapidOCR — ONNX, bundled
    models, **fully offline**; PyMuPDF rasterizes pages) reads scanned/image
    PDFs; `NullOcrProvider` default. Verified live: a text-free image PDF OCR'd
    back to its exact text.
  - **honest degradation** (Doc §12.4): a scanned PDF with no text layer is
    flagged `ocr_status="needs_ocr"` when OCR is off, instead of silently
    ingesting blank/garbage text. Enable with `TS_OCR_ENABLED=true` +
    `pip install -e ".[ocr]"`.
  - `file_to_boq_csv` + `ingestion.ocr` published as capabilities so BOQ reads
    tables without importing ingestion. OCR test skips where the `ocr` extra
    isn't installed (CI stays light).

Test suite: 98 passing, ruff clean; architecture test green.

### Done — 2026-07-23 (session 15: production hardening — implementable-now slice)

Built the parts of the hardening list that need no live credentials:

- **TS-026** — real multipart upload + text extraction: `extract.py` (PDF via
  pypdf, XLSX via openpyxl, CSV/text), `LocalStorage` (per-org, sha256), and
  `POST …/upload` that feeds the existing classify/segment/deadline pipeline.
  Tested end-to-end with a generated PDF (classified NIT, deadline extracted).
- **TS-030** — PDF export (reportlab): completes DOCX/PDF/XLSX; gated + stamped;
  `?format=pdf` returns a real `%PDF-`.
- **TS-029** — GST invoice computation (`gst.py`): CGST/SGST intra-state vs IGST
  inter-state (SAC 998313), sequential gap-free numbering. Pure + tested.
- **TS-028** — TOTP MFA (`mfa.py`, pyotp): enroll (secret + otpauth URI) +
  verify; `users.mfa_totp_secret` column (migration `0009`); `/auth/mfa/enroll`
  + `/verify`. Enforcement-at-login is a follow-up.
- **TS-027** — `notifications` module: pluggable `Sender` (ConsoleSender dev
  backend) + pure deadline-digest logic (alert windows 7/3/1/0 days). SES/MSG91
  adapters plug in behind the same interface (TS-035).
- **TS-031** — deploy scaffolding: `docker-compose.yml` (Postgres + backend +
  frontend), backend/frontend `Dockerfile`s, `.env.example`.
- **TS-032** — frontend CI job (npm ci + build) added to GitHub Actions.

Still needs live accounts (interfaces are built; see backlog TS-033…TS-037):
Textract OCR, tus resumable, Celery/Redis, SES/MSG91 send, Google OIDC/phone
OTP, Stripe. Migrations 0001→0009. **95 tests passing, ruff clean.**

### Handoff snapshot (for local takeover)

**All Phase-1 backlog tasks (TS-001…TS-025) are `done`.** 11 feature modules;
migrations 0001–0008; **88 backend tests passing, ruff clean; frontend builds
clean.** Full local run steps, env vars, and the end-to-end click-path are in
`README.md`. What remains is production infra (OCR/uploads/Postgres/payments/
alerts) and the non-code domain-accuracy gate (real tenders + QS + an
`ANTHROPIC_API_KEY`) — see "What's left" in `README.md` and below.

### Done — 2026-07-23 (session 14: assistant — the last module)

- **TS-024** — `assistant` module (Doc §8), grounded + tool-first:
  - pure `tools.py` (list_deadlines, filter_findings, missing_docs,
    rulepack_lookup) reading only the org's own data via capabilities.
  - `AssistantService` routes recognized intents (deadlines / findings by
    severity / missing docs) to **deterministic, cited answers that work with
    no API key**; off-topic questions are **refused** (grounded-only).
  - free-form questions use an injected `AnthropicAgent` only when
    `ANTHROPIC_API_KEY` is set, answering strictly from tool results.
  - `POST /api/assistant/chat`; frontend **Assistant tab** (ask box + grounded
    replies). Tests cover the deadline/findings/missing-doc intents + refusal.
- README rewritten as a local-takeover guide (run steps, env vars, click-path).

Test suite: 88 passing, ruff clean; frontend builds clean.

### Done — 2026-07-23 (session 13: BOQ write-through + BOQ workbench)

- **BOQ write-through** — `BoqRunner` parses an uploaded workbook (CSV), runs
  the deterministic engine + scope-gap checklists (spec text pulled from the
  opportunity's clauses via ingestion), and **persists defects to the shared
  findings register** (`producer='boq'`) via the findings store capability.
  `POST /api/boq/opportunities/{id}/run`.
- BOQ defects now flow through the same pipeline as risk findings: they count
  toward the review gate and appear in the exported Bid Review Pack.
- **Frontend BOQ tab**: "Load sample BOQ & check" runs the engine and lists the
  defects (arith / grand-total / duplicate / blank-rate, all "deterministic
  check"). Risks vs BOQ findings are split by `producer` in the UI.
- **TS-013a complete** — all per-module models + migrations (0001–0008) done;
  risk + BOQ persist findings; review/drafting/export/billing wired.

Test suite: 84 passing, ruff clean; frontend builds clean. Verified live.

### Done — 2026-07-23 (session 12: billing + export renderer)

- **TS-022** — `billing` module (Doc §7, §15):
  - pure `plans.py` (free→exhausted, paygo requires-payment, pro/scale quotas;
    money in paise) + `webhook.py` (HMAC-SHA256, constant-time) — unit-tested.
  - `usage_events`, `payment_log` (append-only ledger), `webhook_events`
    (idempotency) + migration `0008`.
  - **webhook is the only truth**: it logs receipt *before* trusting, verifies
    signature, is idempotent by event id, and only then activates a plan /
    credits a paid review; a tampered signature → 400 + a `failed` ledger row.
  - free-tier metering (`authorize-review` → free_first_review, then 402
    `free_exhausted`); reads/updates org plan via a new `auth.orgs_factory`
    capability (billing never imports auth).
- **TS-023** — `export` module: Bid Review Pack renderer (Doc §1.1(8), §11.4):
  - pure `render.py` → **XLSX** (openpyxl) + **DOCX** (python-docx), each
    carrying the "Prepared with TenderShield · reviewed … · pack …" stamp.
  - **export gate enforced**: blocked (403 `review_incomplete`) until
    `review.gate` opens; consumes review/findings/drafting/ingestion/rulepacks
    via capabilities only.
  - frontend Artifacts tab: Export .docx / .xlsx buttons (authenticated blob
    download), enabled only when the gate is open.
  - PDF (WeasyPrint) deferred — heavy system deps.

Test suite: 83 passing, ruff clean; frontend builds clean. 0001→0008 verified.

### Done — 2026-07-23 (session 11: drafting — artifacts + the three validators)

- **TS-020** — `drafting` module (Doc §6.5), the anti-hallucination spine:
  - **three validators** (pure, `validators.py`): reject invented quotes,
    uncited clauses, and invented numbers against a `FactTable` built only from
    accepted findings. Unit-tested for each failure mode + the passing case.
  - deterministic `generator.py`: assembles the **clarification letter** and
    **assumptions & exclusions register** from accepted findings (facts injected,
    structure built) — validators pass by construction, no LLM key needed; an
    LLM polish pass would be subject to the same validators.
  - `Artifact` model + migration `0007` (org-scoped, RLS; versioned,
    `UNIQUE(opportunity, kind, version)`); 0001→0007 verified up+down.
  - `DraftingService.generate` pulls accepted findings via the findings store
    capability, validates, and writes a NEW version (never mutates); refuses
    with `no_accepted_findings` until review has accepted something.
  - endpoints: generate / list / get; **frontend Artifacts tab** — generate
    (disabled until the export gate opens) and read the versioned letter/register.

Test suite: 74 passing, ruff clean; frontend builds clean.

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

The Phase-1 feature engine is complete end-to-end (upload → classify →
deadlines → clauses → risk register → BOQ checks → review → clarification
letter/assumptions → gated DOCX/XLSX/PDF export → billing), the `assistant`
module is built (hidden from the UI by product choice), and the first Phase-2
feature — **baseline lock** (TS-041/042) — now ships end to end. Next:

- **Phase-2 continuation (natural follow-ons to baseline lock):**
  - **TS-043** — notice-deadline countdowns + alerts driven by the notice-rule
    register (the register now exists; wire it to the deadline/notification
    path). Doc §0.1 (P3), §10.
  - **TS-044** — award-document ingestion: parse the negotiated contract/award
    letter so the award baseline is sealed from real award text (today it seals
    the reviewed state). Doc §0.1 (P2/P3).
  - **TS-045** — handover-pack file export (DOCX/PDF) reusing the export
    renderer (today the pack is structured JSON in the UI).
- **The real gate (not code):** domain-accuracy validation — 5 real tenders +
  gold answers + a QS review (Doc §18.3/§19.2) — is the gate that *promotes*
  Phase 2 out of "built-ahead". Set `ANTHROPIC_API_KEY` to turn on the LLM
  classifier + the Week-2 accuracy harness. Founder still needs to collect the
  5 real tenders + gold answers — code can't substitute for these.
- **Production hardening (infra, not logic):** tus resumable upload, Celery/Redis
  streaming, Postgres/RDS deploy, email/WhatsApp send adapters, phone-OTP/Google
  OIDC, live Razorpay/Stripe keys — all logic-ready behind existing interfaces
  (TS-033/034/035/036/037), pending external creds.
- Frontend follow-ups: PDF.js source-page view, a frontend lint/build step in CI.
