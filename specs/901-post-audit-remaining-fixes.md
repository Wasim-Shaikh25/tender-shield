# Post-Audit Remaining Fixes — Spec

**Status:** agreed  
**Requirement refs:** `PRODUCTION_READINESS_AUDIT.md` findings F26–F42 (new numbering); `docs/TenderShield_Full_Build_Doc.md` §3.2, §5, §7, §11.1, §11.2, §11.6, §11.7, §14, §15.  
**Task refs:** TS-093.

## Purpose

This spec captures the second batch of production-readiness hardening identified in the re-audit after TS-083–TS-092. It closes DevEx gaps, removes unsafe integration fallbacks, and plugs the remaining auth/DoS/file-access holes before real data or credentials are introduced.

## Public interface

No new modules are created. Existing interfaces are extended/hardened:

- **Core** (`app/core/config.py`, `app/core/storage.py`, `app/main.py`):
  - `Settings.is_prod()` and `is_dev()` helpers.
  - `get_storage()` raises `StorageError` in production when S3 was requested but failed to initialise.
  - `LocalStorage.url`/`validate_and_store` produce a retrievable local path; new `GET /api/files/{key}` route streams stored files.
- **Auth** (`app/modules/auth/*`):
  - Sign-up creates an `email_verification` token; `POST /api/auth/verify-email` flips `User.email_verified`.
  - `forgot_password` and `create_invitation` stop returning raw tokens over HTTP; dev/test fallbacks are logged, not sent to the client.
- **Ingestion** (`app/modules/ingestion/tus.py`, `app/modules/ingestion/router.py`):
  - `tus` PATCH/HEAD require an `estimator` principal and validate workspace/size.
  - `GET /api/ingestion/opportunities/{id}/documents/{doc_id}/stream` requires `viewer` and the task belongs to the caller's workspace.
- **Rulepacks** (`app/modules/rulepacks/router.py`):
  - `GET /api/rulepacks` and `GET /api/rulepacks/{id}/patterns` require `viewer`.
- **Billing** (`app/modules/billing/router.py`, `app/modules/billing/providers.py`):
  - `checkout` uses `Workspace.country` to determine currency and default provider.
  - Provider adapters raise `BillingError` in production when keys are absent.
- **Notifications** (`app/modules/notifications/module.py`, `app/core/scheduler.py`):
  - Deadline-alert scheduler uses a Redis-backed `apscheduler` lock or Celery Beat when `TS_REDIS_URL` is configured; otherwise logs a warning in multi-instance dev.
- **Frontend** (`frontend/app/opportunities/[id]/page.tsx`):
  - Tender upload `accept` list matches `ALLOWED_UPLOAD_EXTENSIONS`.

## Data owned

No new tables except for email verification:

- `email_verifications` (id, user_id, token_hash, expires_at, used_at, created_at).
- `users.email_verified` already exists and will be enforced by new flows.

Other data is unchanged.

## Behavior

### DevEx (F26)

- **B1 — Environment templates ship with the repo:** `.env.local`, `.env.dev`, and `.env.prod` exist as committed templates with no secrets (placeholder comments for keys). `.gitignore` ignores real `.env*` files but allows `.env.example` and the committed templates.
- **B2 — `scripts/run.sh local` works on a fresh clone:** after installing dependencies, the script sources `.env.local` and starts the backend/frontend stack.

### Upload / storage security (F29, F30, F40)

- **B3 — tus is fully authenticated and bounded:** `tus_create`, `tus_patch`, `tus_status` require an `estimator` principal. `tus_patch` verifies the upload's `workspace_id` matches the principal's workspace and rejects chunks that would exceed the file-type size cap.
- **B4 — Local file URLs are retrievable:** `GET /api/files/{workspace}/{digest}-{filename}` (or similar workspace-scoped key) streams the file with the stored `Content-Type` and `Content-Disposition: attachment`. RLS/workspace binding is enforced by checking the workspace prefix in the key.
- **B5 — Virus scan stays a stub but is consistently invoked:** `validate_and_store` always calls `_scan_stub`; `boq/router.py` does not pass `scan=False`. A follow-up task (TS-094) will replace `_scan_stub` with a real scanner.

### Integration fallbacks (F28, F38)

- **B6 — Production refuses mock integrations:** When `TS_ENV=prod`:
  - `get_storage` raises if `TS_STORAGE_TYPE=s3` and S3 init fails.
  - `RazorpayProvider`/`StripeProvider` raise `BillingError` if keys are absent.
  - `forgot_password` and `create_invitation` require a non-console sender; otherwise they raise `AuthError("email_not_configured")`.
- **B7 — Dev/test keeps logging fallbacks:** When `TS_ENV=dev`, console fallbacks are logged at INFO and `forgot_password` returns `{"ok": true}` (no token). `create_invitation` never returns the token; it is emailed or, if console, logged.

### Rulepacks & SSE auth (F39, F41)

- **B8 — Rulepack catalog requires authentication:** `/api/rulepacks` and `/api/rulepacks/{id}/patterns` require a `viewer` token. The existing `validated_only` query param remains.
- **B9 — SSE stream requires authentication:** `document_stream` requires `viewer` and validates the task belongs to the opportunity/workspace before streaming.

### Billing currency (F31)

- **B10 — Currency derived from workspace country:**
  - `IN` → `inr` (Razorpay default).
  - `AE`, `SA`, `QA` → `aed` (Stripe).
  - `GB` → `gbp` (Stripe).
  - Unknown defaults to `inr` and logs a warning.

### Scheduler multi-instance safety (F37)

- **B11 — Deadline alerts use a distributed lock:** When `TS_REDIS_URL` is set, APScheduler uses `RedisJobStore` + `apscheduler-redis-lock` (or equivalent) so only one container runs the alert job. Without Redis, the scheduler logs a warning and still runs in-process for single-container dev.

### Email verification (F34)

- **B12 — Email verification on sign-up:** Sign-up sets `email_verified=false` and creates a verification token. `POST /api/auth/verify-email` with the token sets `email_verified=true`.
- **B13 — Sensitive actions gated:** Billing checkout and workspace member invitation require `email_verified=true` (or `is_superadmin`).

## Acceptance criteria

- A1. `find . -maxdepth 2 -name '.env*' -type f` shows `.env.local`, `.env.dev`, `.env.prod`, and `.env.example`.
- A2. On a fresh clone with dependencies installed, `./scripts/run.sh local` starts without error.
- A3. `GET /api/rulepacks` without an `Authorization` header returns `401`.
- A4. `PATCH /api/ingestion/tus/{upload_id}` without a valid estimator token returns `401` or `403`.
- A5. Uploading through the opportunity workbench with a `.doc` file is rejected client-side before the request reaches the backend.
- A6. A UK workspace checkout produces a Stripe session in `gbp`.
- A7. `GET /api/files/{key}` for an uploaded local file returns the original bytes and correct `Content-Type`.
- A8. `forgot_password` in `TS_ENV=prod` with no email provider configured returns `503` and never exposes a token.
- A9. `pytest` suite passes after changes.
- A10. `ruff`, `mypy app`, `npm run lint`, `npm run typecheck`, and `npm run build` are clean.

## Out of scope

- Replacing the virus-scan stub with a real ClamAV/cloud scanner (TS-094).
- Rulepack validation with a QS/real tenders (F27) — this is data validation, not code.
- Full E2E / accessibility / load testing (TS-095).
- Production operations: IaC, backups, monitoring (TS-096).

## Assumptions

- Redis is available for distributed scheduling in production; in-memory scheduling is acceptable only for single-container dev.
- `Workspace.country` is set correctly at workspace creation; the checkout router has access to the principal's workspace object.
- The dev/test environment remains allowed to log tokens to the console, but production must refuse.
