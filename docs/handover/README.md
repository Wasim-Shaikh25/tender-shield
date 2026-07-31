# TenderShield — Implementation handover pack

Detailed, code-level build notes for the **92 incomplete tasks** in `tasks/backlog.md`, written to
be handed to an AI coding agent (Cursor Composer) or a new engineer.

**Position at time of writing:** 209 / 301 tasks done (69%). Branch `main` @ `36fe55b`, CI green,
backend suite 420 passed / 5 skipped, `ruff` + `mypy` clean across 193 files.

> Regenerate these figures with `python3 scripts/task_tracker.py` rather than trusting this line —
> it goes stale the moment a task flips.

---

## Read in this order

| Doc | Covers | Tasks |
|---|---|---|
| **[00-conventions.md](00-conventions.md)** | **Start here.** Module framework, registry, events, routers, models/RLS, migrations, tests, quality gates, workflow loop | — |
| [01-schema-unblockers.md](01-schema-unblockers.md) | `findings` schema gaps + reproducibility chain | TS-294, TS-295, TS-296, TS-219 |
| [02-marketdata.md](02-marketdata.md) | Employer Behaviour Graph (new module) | TS-195 → TS-200 |
| [03-eval-at-scale.md](03-eval-at-scale.md) | Corpus adapters, M2/M3/M4 scoring, CI gates, gold set | TS-225, TS-227, TS-228, TS-229, TS-232, TS-233 |
| [04-outcomes-and-loop.md](04-outcomes-and-loop.md) | Outcome capture, correction loop, north-star metric | TS-215, TS-216, TS-218, TS-234 |
| [05-express-lane.md](05-express-lane.md) | Pay-per-report visitor funnel (new module) | TS-208 → TS-214 |
| [06-blocked-inprogress-and-future.md](06-blocked-inprogress-and-future.md) | Blocked, in-progress, gated, and Phases 17–21 | TS-163, TS-035/036/037/079, TS-222, TS-235 → TS-292 |

**00-conventions.md is not optional.** Every other doc assumes it. Code that ignores it fails
`tests/test_architecture.py`, `ruff`, `mypy`, or the `backlog`/`changelog` CI jobs.

---

## Suggested build order

Dependency-driven, from `tasks/phase16_tracker.md`:

```
1. TS-294/295/296/219   schema unblockers      → unblocks pricing, eval, accountability
2. TS-225               corpus adapters        → unblocks everything data-driven
3. TS-227/229/232       M2, M4, CI gates       → Sprint 2 exit: correctness at scale
4. TS-195..200          marketdata graph       → needs a corpus first
5. TS-215/216/234       outcomes + north-star  → TS-215 before/with TS-234
6. TS-218               correction loop        → needs outcomes
7. TS-228/233           backtest + gold set    → TS-233 runs in parallel from the start
8. TS-208..214          Express lane           → GATED on step 3 completing
```

Two sequencing rules the tracker is explicit about, both worth obeying:

- **Corpus before graph.** Building `marketdata` aggregates before there is a corpus produces code
  with nothing to run against.
- **Correctness before revenue.** The Express lane sells to strangers with no reviewer. Shipping it
  before M1 passes on 1,000 real tenders is the highest-liability sequencing error available.

TS-233 (50-tender human gold set) is **calendar-bound, not engineering-bound** — start it now and
let it run alongside everything else. It is the long pole for the Phase 16 exit gate.

---

## What "done" means for any task here

1. Task row in `tasks/backlog.md` flipped to `done` **in the completing commit**.
2. Spec written or updated in the **same change** (`specs/modules/<name>.md`).
3. `ruff check .` and `mypy app` clean; `pytest -q` green (≥420 passing).
4. `python3 scripts/task_tracker.py --validate` → `Validation: clean ✓`.
5. `CHANGELOG.md` `[Unreleased]` updated with Done + Next naming task IDs — enforced by the
   `changelog` CI job.
6. Commit message `<type>(<scope>): <summary>` with `Task: TS-###` in the body.

---

## Standing product invariants (never trade these away)

- **Numbers never come from the LLM** — BOQ arithmetic, date arithmetic, severity scoring, money.
- **Every extracted fact carries provenance** — `source_page` + verbatim `source_quote` ≤200 chars,
  quote-verified before display.
- **Money in minor units** with an explicit currency. Integer arithmetic, one rounding at the end.
- **RLS on every org-scoped table.** Cross-tenant leakage is company-ending.
  (`marketdata`'s `md_*` tables are the one deliberate exception — shared reference data, zero
  customer data, pinned by test.)
- **Webhook is the only billing truth.** Client redirects activate nothing.
- **Tender text is untrusted input** — prompt-injection defences wherever document text meets an LLM.
- **Every module degrades gracefully** when any other is disabled — never crash at import or startup.
- **Rulepacks are never auto-mutated.** The correction loop proposes; a human approves.

## Kill conditions (Strategy §H — stop and escalate, do not work around)

- Critical-clause recall < 75% on the gold set after two tuning rounds.
- **Any invented quote reaching a customer** → halt the Express lane immediately.
- Fully-loaded p95 cost > 25% of the lowest Express tier.
- Saudi/UAE work starting before the India accuracy gate is green.

---

## Source-of-truth map

| Question | File |
|---|---|
| What are the tasks? | `tasks/backlog.md` (+ `scripts/task_tracker.py`) |
| Phase 16 sequencing, gates, blockers | `tasks/phase16_tracker.md` |
| Phases 17–21 and the stage ladder | `docs/TenderShield_Roadmap_Stage1_to_5.md`, `tasks/roadmap_tracker.md` |
| Product requirements | `docs/TenderShield_Full_Build_Doc.md` |
| Market/defensibility requirements | `docs/TenderShield_Market_Strategy_2026.md` |
| Per-module behaviour + acceptance | `specs/modules/<name>.md` |
| Eval harness design | `specs/eval-at-scale.md` |
| AI-assistant rules (binding) | `CLAUDE.md` (mirrored in `.cursor/rules/`, `.devin/rules/`) |
