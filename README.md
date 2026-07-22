# TenderShield AI

Contractor commercial intelligence — ingest a tender pack (NIT/RFP, GCC/SCC, specs,
BOQ, addenda), surface risk clauses, deadline traps, BOQ defects and scope gaps with
exact citations, and generate bid-decision artifacts (risk register, clarification
letter, assumptions & exclusions register, deadline calendar, Bid Review Pack).

> **Status:** Phase 0 — bootstrap. See `tasks/backlog.md` for live state and
> `CHANGELOG.md` for what's done / what's next.

## Repository map

| Path | What it is |
|---|---|
| `docs/TenderShield_Full_Build_Doc.md` | The requirement source of truth (build blueprint v1.0) |
| `specs/` | Generated specifications — product-level + one per module |
| `tasks/backlog.md` | Task backlog derived from requirements (`TS-###` IDs) |
| `CHANGELOG.md` | What's done and what's next, updated every session |
| `CLAUDE.md`, `.cursor/rules/` | Mandatory workflow + architecture rules for AI assistants |
| `backend/` | FastAPI modular monolith — pluggable modules, no hard cross-module deps |
| `rulepacks/` | Versioned contract rule-packs (data + tests, not prompts) |

## Development workflow (mandatory)

**Requirement → Task → Spec → Implement → Commit → Changelog.**
Details in `CLAUDE.md` §1. No code without a task ID; no push without a changelog entry.

## Backend quickstart

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest                      # run tests
uvicorn app.main:create_app --factory --reload
```

Modules are toggled with `TS_ENABLED_MODULES` (comma-separated); the app boots with
any subset enabled. See `specs/modules/core.md` for the plugin contract.
