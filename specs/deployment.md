# Deployment — Spec

**Status:** draft  
**Requirement refs:** Doc §4, §11.1, §16  
**Task refs:** TS-124, TS-O04

## Purpose

Defines the runtime packaging for the TenderShield backend so the container image
contains all optional runtime dependencies required in production.

## Public interface

- `backend/Dockerfile` — container image build definition.

## Behavior

- **B1:** The production image installs `uvicorn` and the runtime extras
  `storage`, `redis`, `celery`, `billing`, `scheduler`, `ocr`, and `auth` from
  `pyproject.toml` so Celery workers, payment webhooks, scheduled digests,
  scanned-table OCR, and OIDC login are all importable at runtime.
- **B2:** Migrations run before the application starts (`alembic upgrade head`).

## Acceptance criteria

- A1: `docker build backend/` succeeds and the resulting image can import every
  optional-dependency module used by the backend.
- A2: The image does not rely on the `dev` extra for runtime serving.
