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

## New UI routes (PR #54 and later)

- **Navigation:** Use `window.next.router.push('/path')` for normal transitions. `AuthGate` now protects all pages at the layout level, so a hard reload (`window.location.href = '/settings'`) will briefly show "Loading session…" and then render the protected page instead of redirecting to `/login`.
- **MFA / verification codes:** In dev, `POST /api/auth/signup` returns `email_verification_token` and `mobile_verification_token`, and `POST /api/auth/login` returns `mfa_code` in the JSON body. These values are NOT printed to the backend log. For a manual walkthrough, read the code from the network response (or temporarily pre-fill the UI input for testing and revert).
- **Cancel subscription:** The billing settings page calls `window.confirm("Cancel subscription? ...")`. Override `window.confirm = () => true` in the browser console to test the flow without a system dialog. On a `free` plan the backend returns `already_free`; change the workspace plan to `pro` first (via `/admin/workspaces/{id}`) to see a successful cancel.
- **Document upload:** The tender upload button hides a real `<input type="file">`. The system file dialog cannot be automated, so seed the document and run BOQ via the API, then refresh the opportunity detail page to verify the tabs populate.
- **Analytics export:** Fixed in PR #54 — `api.exportReport` now appends `?format=csv&filter=all` (or `xlsx`). CSV and XLSX downloads succeed in the UI; PDF still correctly fails because the backend only supports `csv` and `xlsx`.
- **Admin user search:** Fixed in commit `7a2cb80` — user list/search works and user detail now includes the `workspaces` list. Note: the UI currently duplicates the same workspace twice in the Workspaces list for single-workspace users (minor rendering issue, not a blocker).
- **Login workspace flow:** Fixed in commit `79ee819` — `SessionProvider` now keeps the access token in a `useRef` (`tokenRef`), so `switchWorkspace` and `createWorkspace` can be called immediately after `signIn` and the returning-user login correctly binds to the first workspace. Returning users now see the workspace name in the header and workspace-scoped pages work without a manual switch.

## Observability demo (Jaeger + Grafana)

To record a demo of the OpenTelemetry/Jaeger/Grafana stack:

1. Start a shared Docker bridge network so Grafana's provisioned `http://jaeger:16686` URL resolves:
   ```bash
   docker network create ts-obs
   docker run -d --name jaeger-demo --rm --network ts-obs --network-alias jaeger \
     -p 16686:16686 -p 4317:4317 -p 4318:4318 \
     -e COLLECTOR_OTLP_ENABLED=true jaegertracing/all-in-one:latest
   ```
2. Start the backend with OTLP enabled:
   ```bash
   cd /home/ubuntu/repos/tender-shield/backend
   . .venv/bin/activate
   set -a && source ../.env.local && set +a
   TS_OTEL_ENABLED=true \
     TS_OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces \
     uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
   ```
3. Generate traces by calling `/api/health`, `/api/health/ready`, `/api/health/metrics`, and `/api/health/details`.
4. Open `http://localhost:16686/search?service=tendershield-backend`.
5. Start Grafana on the same network (anonymous access avoids the login-form typing issue):
   ```bash
   docker run -d --name grafana-demo --rm --network ts-obs -p 3100:3000 \
     -e GF_AUTH_ANONYMOUS_ENABLED=true -e GF_AUTH_ANONYMOUS_ORG_ROLE=Admin \
     -v /home/ubuntu/repos/tender-shield/observability/grafana/provisioning:/etc/grafana/provisioning:ro \
     grafana/grafana:latest
   ```
6. Open `http://localhost:3100/connections/datasources`, click **Jaeger**, and click **Test**.

### Known gotchas

- The pre-provisioned Grafana datasource points to `http://jaeger:16686`. Without a shared Docker network, the raw `docker run` commands will not resolve `jaeger` from the Grafana container.
- Grafana's default `admin`/`admin` login form is a React controlled component; native typing through the screen automation layer may not update the form state. Use anonymous auth for a demo, or set the password via `GF_SECURITY_ADMIN_PASSWORD` and use the browser console to dispatch input events.
- FastAPI is the only instrumented component in the current branch, so expect each trace to contain the request span plus a few ASGI `http send` children, not nested SQLAlchemy/Redis spans.

## Access-log UI demo

To demonstrate the `tendershield.access` logger from the UI:

1. The logger has **no handler by default** under the stock Uvicorn logging config, so
   `TS_ACCESS_LOG_ENABLED=true` alone produces no console output. Add a temporary
   `--log-config` that declares a `tendershield.access` handler, e.g.:
   ```yaml
   version: 1
   disable_existing_loggers: false
   formatters:
     default:
       (): uvicorn.logging.DefaultFormatter
       fmt: "%(levelprefix)s %(message)s"
   handlers:
     default:
       class: logging.StreamHandler
       formatter: default
       stream: ext://sys.stderr
   loggers:
     tendershield.access:
       handlers: [default]
       level: INFO
       propagate: false
   root:
     level: INFO
     handlers: [default]
   ```
2. Authenticate via the UI (log in with dev `mfa_code`, or pre-fill the OTP input
   temporarily and revert), then navigate to `/support/tickets`, `/analytics`, and
   `/settings` to generate `GET`/`POST`/`PUT` requests.
3. Keep a terminal tailing the backend log open; expect lines like:
   ```
   INFO:     GET /api/support/tickets 200 26.35ms user=<uuid> workspace=<uuid> role=owner request_id=...
   INFO:     PUT /api/auth/settings 200 10.34ms user=<uuid> workspace=<uuid> role=owner request_id=...
   ```

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
- `pytest -q` 184 passed, 4 skipped
- `npm run lint`, `npm run typecheck`, `npm run build` clean
