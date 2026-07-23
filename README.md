# TenderShield AI

Contractor commercial intelligence — ingest a tender pack (NIT/RFP, GCC/SCC, specs,
BOQ, addenda), surface risk clauses, deadline traps, BOQ defects and scope gaps with
exact citations, and generate bid-decision artifacts (risk register, clarification
letter, assumptions & exclusions register, deadline calendar, Bid Review Pack).

> **Status:** Phase-1 MVP — the feature engine is functionally complete end-to-end
> (see the flow below). Not yet production-hardened (real OCR/uploads, Postgres deploy,
> live payments) and **not yet domain-validated** (needs real tenders + a QS review,
> Doc §18.3). See `CHANGELOG.md` for what's done / what's next and `tasks/backlog.md`
> for task-level state.

## End-to-end flow (all working, through the UI)

`upload → classify → deadline wall → clause segmentation → risk register`
`(deterministic severity, quote-verified) + BOQ checks → human review/accept →`
`clarification letter & assumptions register (3 validators) → gated DOCX/XLSX export`
`→ freemium metering + Razorpay webhook.`

Every number is deterministic code (never the LLM), every extracted fact is
quote-verified, and nothing exports until a human reviews it.

## Repository map

| Path | What it is |
|---|---|
| `docs/TenderShield_Full_Build_Doc.md` | The requirement source of truth (build blueprint v1.0) |
| `specs/` | Specifications — product-level + one per module |
| `tasks/backlog.md` | Task backlog derived from requirements (`TS-###` IDs) |
| `CHANGELOG.md` | What's done and what's next, updated every session |
| `CLAUDE.md`, `.cursor/rules/` | Mandatory workflow + architecture rules for AI assistants |
| `backend/` | FastAPI modular monolith — pluggable modules, no hard cross-module deps |
| `frontend/` | Next.js 15 + TypeScript + Tailwind app |
| `rulepacks/` | Versioned contract rule-packs (data + tests, not prompts) |
| `evals/` | Golden-set scaffold + the synthetic sample tender (`evals/in-works/sample_tender/`) |

## Modules (`backend/app/modules/`)

`core*` (framework) · `auth` · `ingestion` (opportunities/documents/clauses/deadlines)
· `rulepacks` · `risk` · `boq` · `findings` (shared register) · `review` · `drafting`
· `export` · `billing` · `assistant`. Each is toggled via `TS_ENABLED_MODULES` and
talks to others only through the service registry + event bus (`specs/modules/core.md`).

## Local development

### 1. Backend

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# create the schema (SQLite by default; see env vars below)
alembic upgrade head

# run tests + lint
pytest -q
ruff check .

# serve the API (loads all modules)
uvicorn app.main:create_app --factory --reload --port 8000
```

Health check + loaded modules: `GET http://localhost:8000/api/health`.

**Backend env vars** (prefix `TS_`; all have dev defaults):

| Var | Default | Purpose |
|---|---|---|
| `TS_DATABASE_URL` | `sqlite:///./tendershield.db` | DB URL. Use PostgreSQL in real deploys — **RLS org-isolation is Postgres-only**; on SQLite the app relies on explicit `org_id` scoping. |
| `TS_ENABLED_MODULES` | *(empty = all)* | Comma-separated subset to enable. |
| `TS_JWT_PRIVATE_KEY` / `TS_JWT_PUBLIC_KEY` | *(ephemeral)* | RS256 PEM keypair. If unset an ephemeral one is generated (dev only). |
| `TS_CORS_ORIGINS` | `*` | Allowed SPA origins. |
| `TS_RAZORPAY_WEBHOOK_SECRET` | `dev-razorpay-secret` | Verifies the billing webhook (the only billing truth). |
| `ANTHROPIC_API_KEY` | *(unset)* | Env (no `TS_` prefix). When set, the risk engine's LLM classifier and the assistant's free-form answers activate; unset = deterministic paths only. |

### 2. Frontend

```bash
cd frontend
npm install
# point at the API (defaults to http://localhost:8000/api)
export NEXT_PUBLIC_API_URL=http://localhost:8000/api
npm run dev          # http://localhost:3000
```

`npm run build` type-checks and compiles.

### 3. Try it end-to-end

Sign up → create an opportunity → open it → **Upload sample tender** (extracts
deadlines + segments clauses) → **Run risk review** → **BOQ tab → Load sample BOQ &
check** → **Risks tab: Accept** each finding → **Artifacts tab: Generate** the
clarification letter → **Export .docx/.xlsx** (unlocked once review is complete).
The **Assistant tab** answers grounded questions ("list the deadlines").

A ready-made synthetic tender with a known answer key lives in
`evals/in-works/sample_tender/` (the frontend's sample buttons use the same data).

## Migrations

Alembic auto-discovers each module's `models.py`. Current chain: `0001`–`0008`.

```bash
cd backend
alembic upgrade head          # apply
alembic downgrade base        # roll back (CI runs both on a scratch DB)
alembic revision -m "…"       # new migration (hand-written; keep it portable)
```

## Development workflow (mandatory)

**Requirement → Task → Spec → Implement → Commit → Changelog.**
Details in `CLAUDE.md` §1. No code without a task ID; no push without a changelog entry.

## What's left

- **Assistant free-form answers + LLM judgment** need `ANTHROPIC_API_KEY` (deterministic
  paths work without it).
- **Production hardening (infra, not logic):** resumable upload (tus/S3), OCR (Textract),
  Celery streaming, Postgres/RDS deploy, email/WhatsApp alerts, OTP/Google/MFA, Stripe +
  GST invoices, PDF export, frontend lint/build in CI.
- **The real gate (not code):** domain-accuracy validation — 5 real tenders + gold answers
  + a QS review (Doc §18.3/§19.2). Run `scripts/phase0_accuracy_test.py` with a key.
