# TenderShield AI — Rules for AI Assistants (Devin)

TenderShield is contractor commercial intelligence: ingest a tender pack (NIT/RFP,
GCC/SCC, specs, BOQ, addenda), surface risk clauses / deadline traps / BOQ defects
with exact citations, and generate bid-decision artifacts. Source of truth for all
product decisions: `docs/TenderShield_Full_Build_Doc.md`.

These rules are **mandatory** for every AI-assisted change in this repo. The same
rules exist for Cursor in `.cursor/rules/` and for Claude in `CLAUDE.md`. Keep the
three in sync when editing any of them.

---

## 1. The workflow loop (ALWAYS, in this order)

Every piece of work follows **Requirement → Task → Spec → Implement → Commit → Changelog**:

1. **Task first.** Before writing any code, create/locate a task in `tasks/backlog.md`.
   Every task has an ID (`TS-###`), a phase, a requirement reference (doc section, e.g.
   `Build Doc §5`), acceptance criteria, and a status
   (`todo | in-progress | blocked | done`). No code without a task ID.
2. **Spec before implementation.** Any new module or behavior change needs a spec in
   `specs/` (see §3 below). If a spec exists, update it *in the same change* when
   behavior diverges. Code that contradicts its spec is a bug in one of the two — fix
   the mismatch, never leave it.
3. **Implement in small, verifiable increments.** Run tests/linters before committing.
4. **Commit per logical step** with a clear message:
   `<type>(<scope>): <summary>` — types: `feat|fix|docs|spec|chore|test|refactor`;
   scope = module or area (e.g. `feat(boq): unit normalization map`). Reference the
   task ID in the body (`Task: TS-012`).
5. **Changelog every session.** Update `CHANGELOG.md` (`[Unreleased]` section) in the
   same push: what was **Done** and what is **Next**. The Next list must name concrete
   task IDs. A push without a changelog entry is incomplete work.
6. **Close the loop.** Mark the task status in `tasks/backlog.md` in the same commit
   that completes it.

## 2. Module architecture — pluggable, no hard dependencies

The backend is a **modular monolith** where every feature area is a self-contained,
pluggable module. This is non-negotiable:

- Modules live in `backend/app/modules/<name>/` and expose exactly one entry point:
  a `module` object (`ModuleSpec`) in `module.py` declaring `name`, `version`,
  `router`, optional `soft_deps`, and lifecycle hooks (`setup`, `shutdown`).
- **A module may import ONLY from `app.core.*` and its own package. Never from
  `app.modules.<other>`.** Cross-module interaction happens exclusively via:
  - the **service registry** (`app.core.registry`) — capabilities published/consumed
    by string name, resolved at runtime, with graceful absence handling; or
  - the **event bus** (`app.core.events`) — publish/subscribe on named events.
- `soft_deps` are advisory: a module must degrade gracefully (feature off, warning
  logged) when a dependency module is disabled — never crash at import or startup.
- Modules are enabled/disabled by configuration (`TS_ENABLED_MODULES`); the app must
  boot with any subset enabled.
- Shared data contracts (Pydantic models, enums) live in `app/core/contracts/` —
  never in one module imported by another.
- Each module owns its DB tables, migrations, and tests. Foreign keys may reference
  core tables (orgs/users) but not another module's tables directly; use IDs + events.

## 3. Specs (`specs/` folder)

- One spec per module: `specs/modules/<name>.md`. Product-level specs in `specs/`.
- Follow the template in `specs/README.md`: Purpose, Requirement refs, Public
  interface (capabilities published, events emitted/consumed, API routes), Data owned,
  Behavior, Acceptance criteria, Out of scope.
- Specs cite the build doc section they derive from. Anything invented beyond the doc
  is marked `assumption:` explicitly.

## 4. Product-critical invariants (from the build doc — never violate)

- **Numbers never come from the LLM.** BOQ arithmetic, date arithmetic, severity
  scoring are deterministic code (Build Doc §6.4, §6.2, §6.3).
- **Every extracted fact carries provenance** (`source_page`, verbatim
  `source_quote` ≤200 chars) and passes quote verification before display.
- **Validators are the spine:** no invented quotes, no uncited clauses, no invented
  numbers in generated artifacts (§6.5).
- **RLS / org isolation on every org-scoped table.** Cross-tenant leakage is
  company-ending (§3.2).
- **Webhook is the only billing truth** — client redirects never activate anything (§15).
- Tender text is **untrusted input** — prompt-injection defenses apply everywhere
  document text meets an LLM (§11.3).
- Money in **minor units** (paise), never float.

## 5. Conventions

- Backend: Python 3.11+, FastAPI, SQLAlchemy 2, Pydantic v2, pytest; `ruff` clean.
- Frontend (later phases): Next.js 15 + TypeScript + Tailwind, per Build Doc §9.
- Rule-packs are versioned data (`rulepacks/`), not prompt text; every pattern carries
  `source:` and `confidence: unvalidated|validated` (§14).
- Scope discipline: only Phase 0/1 features get built until their exit gates pass
  (Build Doc §10, §12.6). Do not build ahead of the phase plan.

## 6. Devin-specific notes

- Prefer the built-in `todo_write` tool for multi-step tasks and keep the user-visible
  checklist accurate.
- Use `message_user` for important updates and the final wrap-up; plain assistant text is
  not visible to the user.
- Create a PR for any code change unless the user explicitly says otherwise; fetch the
  PR template first and keep descriptions high-signal.
- Run `ruff check .` and `pytest -q` in `backend/`, and `npm run build` in `frontend/`,
  before pushing.
