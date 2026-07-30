---
name: TenderShield end-to-end smoke test
description: |
  How to boot, authenticate, and exercise the TenderShield golden-path UI
  (sign-up, opportunity creation, file upload, risk review, BOQ check) and
  how to recognize the pre-existing workspace-list / workspace-switch bugs.
---

# TenderShield end-to-end smoke-test skill

## Devin Secrets Needed

- None for local dev. The repo ships `.env.local` with SQLite and no cloud secrets.
- Optional: `TS_OPENROUTER_API_KEY` (or `OPENROUTER_API_KEY`) if you want LLM risk findings; without it the
  engine uses `NullClassifier` and returns zero risk findings.

## Quick start

1. Repo: `/home/ubuntu/repos/tender-shield`.
2. Backend venv: `backend/.venv` (also a root `.venv` exists; `scripts/run.sh local`
   uses `backend/.venv`).
3. Start servers:
   ```bash
   cd /home/ubuntu/repos/tender-shield
   ./scripts/run.sh local
   ```
   Or manually:
   ```bash
   cd /home/ubuntu/repos/tender-shield/backend
   . .venv/bin/activate
   source ../.env.local
   alembic upgrade head
   uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000
   ```
   and in another shell:
   ```bash
   cd /home/ubuntu/repos/tender-shield/frontend
   npm run dev
   ```
4. Health: `curl http://localhost:8000/api/health` → `{"status":"ok"}`.
5. App: `http://localhost:3000`.

## Test data

- Password policy: `TestPass123!` meets the default dev policy (upper, lower,
  digit, special, ≥8 chars).
- Use unique emails like `smoke-<timestamp>@example.com`.
- Sample tender: generate a text/PDF from `evals/in-works/sample_tender/conditions.md`.
  The backend accepts `.pdf`, `.docx`, `.xlsx`, `.xls`, `.csv`, `.png`, `.jpg`,
  `.jpeg`, `.tiff`, `.tif`, `.zip`. For UI testing with only text available,
  a `.csv` file containing the planted tender text will be classified as `nit`.
- BOQ CSV: `evals/in-works/sample_tender/boq.csv` produces exactly 10 deterministic
  findings (4 defects + 5 scope gaps, duplicate + arith + blank_rate + grand_total).

## Known pre-existing failure modes

1. **TS-F01 / workspace-list contract mismatch** (`PRODUCTION_READINESS_AUDIT.md`).
   `GET /api/auth/workspaces` returns a raw JSON list with `workspace_id`; the
   frontend `SessionProvider` expects `{workspaces:[{id, name, plan, ...}]}`. On an
   unpatched build, sign-up/login crashes the header with:
   `Cannot read properties of undefined (reading 'find')` at
   `components/session.tsx`. This is **not** a PR regression.
2. **TS-A06 / workspace-switch refresh-token commit bug**. After a successful
   `POST /api/auth/workspaces/{id}/switch`, the new refresh token is returned as
   a cookie but **never committed** in `auth/service.py`. The next
   `POST /api/auth/refresh` returns `401 {"detail":"invalid_refresh"}` and the
   user is signed out. This is **not** a PR regression.
3. **No OpenRouter key** means risk review returns `count:0, findings:[]`.
   Deterministic BOQ checks still work.
4. **Environment variables must be exported.** Use `set -a` before `source .env.local`
   so `TS_*` vars are visible to the server process:
   ```bash
   cd /home/ubuntu/repos/tender-shield/backend
   . .venv/bin/activate
   set -a && source ../.env.local && set +a
   ```
5. **Migration/model drift can break sign-up.** If `alembic upgrade head` ever
   lags the SQLAlchemy models, sign-up will 500 with `no such column`. Regenerate
   migrations (`alembic revision --autogenerate`) or, for a quick smoke test,
   recreate tables from the models:
   ```bash
   python - <<'PY'
   from app.main import create_app
   from app.core.config import Settings
   from app.core.db import Base
   url = "sqlite://///tmp/tendershield_smoke.db"
   app = create_app(Settings(database_url=url))
   engine = app.state.ctx.registry.require("db.engine")
   Base.metadata.create_all(engine)
   PY
   TS_DATABASE_URL=sqlite://///tmp/tendershield_smoke.db uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
   ```

## Backend / Postgres RLS test notes

- The Postgres-only RLS tests are in `backend/tests/test_rls_postgres.py`.
- To run them you need a Postgres container and `psycopg[binary]` (not `psycopg-binary`):
  ```bash
  docker run --name pgts -e POSTGRES_USER=tendershield -e POSTGRES_PASSWORD=tendershield -e POSTGRES_DB=tendershield -p 5432:5432 -d postgres:16-alpine
  . .venv/bin/activate
  .venv/bin/pip install "psycopg[binary]"
  export TS_DATABASE_URL=postgresql+psycopg://tendershield:tendershield@localhost:5432/tendershield
  pytest tests/test_rls_postgres.py -q
  ```
- PostgreSQL does not allow parameter placeholders in `SET LOCAL`. If you see:
  `syntax error at or near "$1"` on `SET LOCAL app.workspace_id = $1`, the RLS
  binding must inline the workspace UUID literal or use `set_config()`.
- Running the integration tests as a superuser bypasses RLS. Use a dedicated,
  non-superuser database role to exercise `FORCE ROW LEVEL SECURITY`.
- `current_setting('app.workspace_id', true)` returns an empty string (not `NULL`)
  when the GUC is unset, so casting it directly to `uuid` can raise
  `invalid input syntax for type uuid: ""`. Use `nullif(..., '')::uuid` to fail closed.

## UI testing tips

- The dev server uses `next dev` and can be confused by a stale `.next` folder
  after `npm run build`. If you see `Cannot find module './xxx.js'`, stop the
  dev server, `rm -rf frontend/.next`, and restart `npm run dev`.
- The login/sign-up form is a React controlled form. Native mouse typing can be
  unreliable through the screen automation layer; if it fails, use the browser
  console with `Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,
  'value').set` and dispatch an `input` event.
- To test file upload with only text content, set `input.files` via a
  `DataTransfer` containing a `.csv` Blob and dispatch `change`.
- Workspace creation has no UI; create a second workspace via
  `POST /api/auth/workspaces` (owner token required) to exercise the header
  switcher.

## Regression shell probe

```bash
API=http://localhost:8000/api
CURL="curl -s -c cookies.txt -b cookies.txt"
# sign up, login, create opportunity, upload, run risk, run boq
```

Expected local baseline:
- `ruff check .` clean
- `mypy app` clean
- `pytest -q` 147 passed, 4 skipped
- `npm run lint`, `npm run typecheck`, `npm run build` clean
