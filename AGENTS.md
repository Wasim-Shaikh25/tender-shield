# TenderShield AI — Agent Notes

Product and workflow rules live in `CLAUDE.md` and `.cursor/rules/`. This file adds
**Cursor Cloud** runtime notes for agents booting the dev environment.

## Cursor Cloud specific instructions

### Stack overview

| Service | Port | Start command |
|---|---|---|
| Backend API (FastAPI) | 8000 | `cd backend && source ../.env.local && .venv/bin/uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000` |
| Frontend (Next.js) | 3000 | `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000/api npm run dev` |

**Shortcut:** `./scripts/run.sh local` starts both (backend in background, frontend in
foreground). Requires `backend/.venv` and `frontend/node_modules` to exist first.

Local dev uses **SQLite** (`.env.local`) — no Postgres, Redis, or cloud secrets required.

### System prerequisites

Ubuntu images need `python3.12-venv` before creating the backend venv:

```bash
sudo apt-get install -y python3.12-venv python3.12-dev
```

Node **22** and Python **3.11+** (3.12 works) are expected.

### First-time / manual dependency install

See `README.md` for full steps. CI-equivalent install:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,storage,redis,billing,scheduler,celery,auth]"
.venv/bin/alembic upgrade head

cd ../frontend
npm ci
```

### Lint / test / build

| Area | Commands (from repo root) |
|---|---|
| Backend lint | `cd backend && .venv/bin/ruff check .` |
| Backend types | `cd backend && .venv/bin/mypy app` (CI uses Python 3.11; on 3.12 mypy may error on numpy stubs — tests still pass) |
| Backend tests | `cd backend && .venv/bin/pytest -q` (expect ~145 passed) |
| Frontend lint | `cd frontend && npm run lint` |
| Frontend types | `cd frontend && npm run typecheck` |
| Frontend build | `cd frontend && npm run build` |

### Migrations

Run before starting the backend on a fresh DB:

```bash
cd backend && set -a && source ../.env.local && set +a && .venv/bin/alembic upgrade head
```

### Smoke testing

- **API golden path** (no UI): sign up → create opportunity → upload document → BOQ run.
  Sample data in `evals/in-works/sample_tender/`. Skill:
  `.agents/skills/testing-tendershield/SKILL.md`.
- **Health:** `curl http://localhost:8000/api/health` → `{"status":"ok",...}`.
- **Known UI bug (TS-F01):** `GET /api/auth/workspaces` response shape mismatches the
  frontend `SessionProvider`; sign-up/login may crash the header with
  `Cannot read properties of undefined (reading 'find')`. This is pre-existing — use
  the API curl flow to verify backend behavior.

### Optional services (not needed for local golden path)

- **Postgres:** `docker compose --env-file .env.dev up --build` (port 5432).
- **Redis / Celery:** only when `TS_REDIS_URL` is set; otherwise in-memory / eager mode.
- **LLM risk findings:** set `ANTHROPIC_API_KEY` in `.env.local` (no `TS_` prefix).
- **OCR:** `pip install -e ".[ocr]"` then `TS_OCR_ENABLED=true`.

### tmux tip

Long-running servers should use tmux (`tmux -f /exec-daemon/tmux.portal.conf`). Example
session names: `tendershield-backend`, `tendershield-frontend`.

### Stale Next.js dev cache

If `next dev` fails with `Cannot find module './xxx.js'`, stop the server, `rm -rf
frontend/.next`, and restart.
