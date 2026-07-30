# Deployment & Environment Setup

TenderShield ships with three environment files and one local run script.

## Environment files

| File | Purpose |
|---|---|
| `.env.local` | Local development: SQLite, dev Razorpay secret, `localhost:3000` CORS. |
| `.env.dev` | Staging / development: Postgres, real secrets, dev domains. |
| `.env.prod` | Production: Postgres, real secrets, prod domains. |

All backend variables use the `TS_` prefix. Copy the appropriate file to `.env` or source it directly.

## Local development

1. Install dependencies:
   ```bash
   cd backend
   python -m venv .venv && . .venv/bin/activate
   pip install -e ".[dev]"
   cd ../frontend
   npm install
   ```

2. Run everything:
   ```bash
   ./scripts/run.sh local
   ```

   This sources `.env.local`, runs Alembic migrations, starts the API on `http://localhost:8000`, and starts the Next.js dev server on `http://localhost:3000`.

3. Health check: `GET http://localhost:8000/api/health`

## Docker

Build and run manually:

```bash
docker build -t tendershield-backend ./backend
docker run -p 8000:8000 --env-file .env.local tendershield-backend

docker build -t tendershield-frontend ./frontend --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000/api
docker run -p 3000:3000 tendershield-frontend
```

Or use docker compose with the relevant env file:

```bash
docker compose --env-file .env.dev up --build
docker compose --env-file .env.prod up --build
```

## Required secrets for real deploys

Before going live, set real values for:

- `TS_DATABASE_URL` — PostgreSQL 16+ (RLS workspace-isolation is Postgres-only).
- `TS_JWT_PRIVATE_KEY` / `TS_JWT_PUBLIC_KEY` — RS256 PEM keypair; rotate quarterly.
- `TS_RAZORPAY_WEBHOOK_SECRET` — the only source of billing truth.
- `TS_APPLE_*` — to enable Sign in with Apple.
- `ANTHROPIC_API_KEY` — to enable LLM risk classification and assistant free-form answers.
- `NEXT_PUBLIC_API_URL` — public API base URL, consumed at build time by the frontend.

## Observability

TenderShield exposes the following health and metrics endpoints under `/api/health`:

| Endpoint | Purpose | Auth |
|---|---|---|
| `GET /api/health` | Minimal public health status | none |
| `GET /api/health/live` | Kubernetes liveness probe | none |
| `GET /api/health/ready` | Readiness probe; checks DB, Redis, storage, and Celery broker | none |
| `GET /api/health/metrics` | Prometheus exposition text (RED metrics per process) | none |
| `GET /api/health/details` | Modules, capabilities, and dependency statuses | super-admin |

Set `TS_SENTRY_DSN` (and optionally `TS_SENTRY_ENVIRONMENT` and `TS_SENTRY_TRACES_SAMPLE_RATE`)
to enable Sentry error tracking. The `sentry-sdk` package must be installed (`pip install -e ".[observability]"`).

## Backup and rollback

**PostgreSQL**
- Enable point-in-time recovery (PITR) using WAL archiving and managed backups. Target RPO ≤ 1 h, RTO ≤ 30 min.
- Test restores to a separate environment quarterly.

**Object storage**
- S3 buckets and S3-compatible stores must have versioning enabled.
- Define lifecycle rules to transition old objects to cheaper storage after 90 days.

**Application rollback**
- Deployments are containerised; keep the previous image tag in the registry.
- Rollback procedure: revert the image tag, run `alembic downgrade -1` for database migrations that were introduced in the failed release, and restart pods.
- Do not run `alembic downgrade` on a release that has already processed new user data; instead restore from the PITR backup.

**Monitoring alerts**
- Alert on 5xx rate > 1 % over 5 min, webhook signature verification failures, Celery queue depth > 100, and failed logins per account.

Do not commit `.env` files. The committed `.env.local`/`.env.dev`/`.env.prod` contain example values only.
