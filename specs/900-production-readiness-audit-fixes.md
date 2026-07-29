# Production Readiness Audit Fixes — Spec

**Status:** in progress  
**Requirement refs:** `PRODUCTION_READINESS_AUDIT.md` findings F01–F25; `docs/TenderShield_Full_Build_Doc.md` §3.1, §5, §11.1, §11.2, §11.6, §11.7, §15.  
**Task refs:** TS-083, TS-084, TS-085, TS-086, TS-087, TS-088, TS-089, TS-090, TS-091, TS-092.

## Purpose

This spec captures the cross-cutting hardening and product-completeness work required to move TenderShield from a controlled internal demo to a production-deployable service. It updates the existing module specs in the same change, and is the source of truth for the implementation in `devin/audit-fixes`.

## Public interface

No new top-level capabilities are created by this spec; it extends and hardens the interfaces of existing modules:

- **Core** (`app/core/config.py`, `app/main.py`, `app/core/ratelimit.py`, `app/core/storage.py`):
  - `Settings` gains `env`, `allowed_hosts`, `storage_type`, `s3_*`, `redis_url`, and uses `SecretStr` for all secrets.
  - `create_app` runs `_validate_prod_settings` and mounts security / CORS / rate-limit middleware.
  - `RateLimiter` capability (`core.ratelimit`) used by public routes.
  - `Storage` protocol extended with `S3Storage`.
- **Auth** (`app/modules/auth/*`):
  - Login returns refresh token in an `httpOnly` `Secure` cookie (`refresh_token`) and a short-lived access token in the JSON body.
  - `/api/auth/refresh` reads `refresh_token` cookie, rotates it, and returns a new access token.
  - `/api/auth/logout` clears the refresh cookie and revokes the token family.
  - `/api/auth/mfa/challenge` enforces TOTP after password verification when MFA is enrolled.
  - `/api/auth/workspaces` returns all workspaces for the user; `/api/auth/workspaces/switch` issues tokens for a selected workspace.
  - Password policy: min 8, upper/lower/digit/symbol; account lockout after 5 failures.
  - `is_superadmin` flag guards `/api/health/details`.
- **Ingestion / BOQ** (`app/modules/ingestion/*`, `app/modules/boq/*`):
  - File validation: size cap, magic-byte/MIME, allowed extension set, virus-scan stub.
  - S3 storage adapter behind `Storage` protocol; LocalStorage for dev/tests.
  - BOQ upload size cap matches ingestion.
- **Risk / Export** (`app/modules/risk/service.py`, `app/modules/export/*`):
  - Risk pattern selection respects `validated_only` for paying / internal plans.
  - Bid Review Pack export includes reviewer name/date and a tamper-evident hash.
- **Billing** (`app/modules/billing/*`):
  - `BillingProvider` protocol with `RazorpayProvider` and `StripeProvider` stubs.
  - `/api/billing/checkout` creates a real provider order/session when keys are configured; deterministic notes fallback remains for dev/tests without keys.
- **Notifications** (`app/modules/notifications/*`):
  - `Sender` protocol implementations: `ConsoleSender`, `SESSender`, `MSG91Sender`.
  - `NotificationScheduler` scans deadlines and notice rules; requires Redis/cron for production.
- **Frontend** (`frontend/*`):
  - Store access token in memory; refresh token in `httpOnly` cookie via `credentials: "include"`.
  - Workspace switcher in nav.
  - Remove hardcoded `SAMPLE` data from `/opportunities/[id]`.
  - New routes: `/billing`, `/admin/users`, `/admin/workspaces`, `/admin/audit-log`.

## Data owned

No new tables except where noted by module specs. Existing tables affected:

- `users.mfa_verified` / `mfa_enrolled_at` used to gate MFA at login.
- `refresh_tokens` continues to store hashed tokens and family IDs; cookie transport replaces JSON body.
- `password_resets` / `invitations` keep existing schema; delivery adapters send real messages when configured.

## Behavior

### Security / core (TS-083)

- **B1 — No unsafe production defaults:** `create_app` raises `RuntimeError` in `TS_ENV=prod` when `TS_RAZORPAY_WEBHOOK_SECRET`, `TS_JWT_PRIVATE_KEY`, `TS_JWT_PUBLIC_KEY`, `TS_CORS_ORIGINS` or `TS_ALLOWED_HOSTS` are missing or wildcarded.
- **B2 — Security headers:** every HTTP response carries `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, `Content-Security-Policy`, and HSTS in production.
- **B3 — CORS:** `allow_methods` and `allow_headers` are explicit; `allow_credentials=True` only when origins are not `*`.
- **B4 — HTTPS / trusted host:** `HTTPSRedirectMiddleware` and `TrustedHostMiddleware` are active in production.
- **B5 — Rate limiting:** public routes (`/auth/login`, `/auth/signup`, `/auth/forgot-password`, `/auth/reset-password`, `/billing/webhooks/*`) are rate-limited per client IP. In-memory storage is used when `TS_REDIS_URL` is unset; Redis when configured.
- **B6 — Health split:** `GET /api/health` is public and returns only `status` and `version`; `GET /api/health/details` requires a super-admin token and returns module/capability metadata.

### Auth / session (TS-084, TS-085)

- **B7 — Refresh in httpOnly cookie:** Login returns `access_token` and `workspace_id` in JSON; `refresh_token` is set as `httpOnly`, `Secure` (prod), `SameSite=Lax` cookie. The frontend stores the access token in memory and refreshes it silently before expiry.
- **B8 — Workspace selection:** Login and refresh return the user's first workspace by default; a new `GET /api/auth/workspaces` endpoint lists memberships, and `POST /api/auth/workspaces/{id}/switch` issues tokens bound to the chosen workspace.
- **B9 — MFA enforcement:** When `User.mfa_enrolled_at` is set, password verification alone returns `mfa_required`; the client must post `/api/auth/mfa/challenge` with a TOTP code to receive tokens.
- **B10 — Password policy:** passwords must be ≥ 8 characters and contain uppercase, lowercase, digit, and symbol. Common/weak passwords are rejected.
- **B11 — Account lockout:** 5 failed login attempts within 15 minutes lock the account for 15 minutes.
- **B12 — Superadmin flag on health details:** `current_principal.is_superadmin` is checked explicitly for `/api/health/details`; the route is unavailable if auth is disabled.

### File upload / storage (TS-086)

- **B13 — Upload validation:** `MAX_UPLOAD_BYTES` is enforced per route (2 GB for ingestion, 100 MB for BOQ). Files are rejected if the magic/MIME type is not in the allowed set (`application/pdf`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `text/csv`, `image/*` for OCR-only). Unknown extensions are not decoded as text.
- **B14 — Virus stub:** a `VirusScanner` protocol is added; `ClamAvScanner` is the default when `TS_CLAMAV_HOST` is set, otherwise `NoOpScanner` logs a warning and returns clean.
- **B15 — S3 adapter:** when `TS_STORAGE_TYPE=s3`, files are stored under `{workspace_id}/{opportunity_id}/{filename}` with SSE-S3; presigned GET URLs are returned. Local dev and tests continue to use `LocalStorage`.
- **B16 — BOQ size cap:** BOQ uploads use the same validation pipeline as ingestion documents.

### Risk / export (TS-087)

- **B17 — Validated-only patterns for paid users:** `RiskService.run_opportunity` passes `validated_only=True` to `RulePackLoader.list_patterns` when the workspace is on `free`/`internal`?  Actually: when the workspace is on a paid/internal plan, only `validated` patterns are used; free/internal/demo workspaces may fall back to `unvalidated` patterns with a clear disclaimer.
- **B18 — Export reviewer stamp:** `ExportService.export` reads the latest `AuditLog`/`FindingRow.reviewed_by` user and includes `reviewed_by_name`, `reviewed_by_email`, and `reviewed_at` in the pack meta. A SHA-256 of the rendered bytes is appended to the pack.

### Billing / notifications (TS-091)

- **B19 — Provider order creation:** `BillingService.checkout` calls `BillingProvider.create_order` if Razorpay/Stripe keys are configured; otherwise it returns the deterministic notes object suitable for manual activation in dev.
- **B20 — Webhook secret guard:** `verify_signature` returns `False` when no secret is configured, so a production misconfiguration cannot be exploited.
- **B21 — Notification adapters:** `Sender.send` is called by `NotificationsService`. `ConsoleSender` remains default for dev/tests; `SESSender`/`MSG91Sender` activate when credentials are configured. A scheduler stub runs deadline scans; real cron/Redis is required for production.

### Frontend (TS-088, TS-092)

- **B22 — No demo data in production pages:** `SAMPLE` and `SAMPLE_BOQ` constants are removed from `/opportunities/[id]`; sample loading is moved to a dedicated `/demo` route or gated by `NEXT_PUBLIC_DEMO_MODE`.
- **B23 — Billing/admin routes:** Next.js pages are added for plan selection, invoice list, user/workspace admin, and audit-log viewer. They consume the existing backend endpoints.
- **B24 — Landing copy:** unverified claims such as "Hosted in India (ap-south-1)" are removed or made conditional on `NEXT_PUBLIC_HOSTING_REGION`.

### CI / tooling (TS-090)

- **B25 — Lint/type gates:** CI runs `mypy --strict app`, `ruff check .`, `pytest`, ESLint (`next lint` once configured), `npm run build`, and `npm audit --audit-level=high`/`pip-audit`.
- **B26 — Dependency scanning:** `pip-audit` and `npm audit` block high/critical findings.

### Deployment (TS-089)

- **B27 — Env templates:** `.env.local`, `.env.dev`, `.env.prod` templates are committed with placeholders. `scripts/run.sh` and `docker-compose.yml` reference `.env.local` for local development.
- **B28 — Changelog discipline:** every push updates `CHANGELOG.md` `[Unreleased]`.

## Acceptance criteria

- A1: `TS_ENV=prod` with default `TS_RAZORPAY_WEBHOOK_SECRET` raises on startup.
- A2: `GET /api/health` returns `{"status":"ok","version":"0.1.0"}` without auth.
- A3: `GET /api/health/details` without superadmin returns 403.
- A4: Response headers from any route include `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Content-Security-Policy`.
- A5: CORS preflight from an origin not in `TS_CORS_ORIGINS` is rejected in production.
- A6: 6 rapid `/auth/login` attempts from the same IP return 429.
- A7: Login with an enrolled MFA user returns `mfa_required`; correct TOTP returns tokens.
- A8: A refresh token cookie is `httpOnly` and `Secure` in production.
- A9: Calling `/auth/logout` clears the refresh cookie and revokes the family.
- A10: `GET /auth/workspaces` lists all workspaces for the authenticated user.
- A11: `POST /auth/workspaces/{id}/switch` returns tokens scoped to the chosen workspace.
- A12: A weak password (`password`) is rejected at signup and reset.
- A13: 5 failed logins lock the account for 15 minutes.
- A14: Uploading a 3 GB file to `/boq/upload` returns 413.
- A15: Uploading a `.exe` renamed to `.pdf` returns 415/422.
- A16: `TS_STORAGE_TYPE=s3` with `moto` stores files under a workspace prefix.
- A17: Free/internal workspaces may use unvalidated risk patterns; paid workspaces only use validated patterns.
- A18: Bid Review Pack export contains the reviewer name, date, and a tamper hash.
- A19: `/billing/checkout` with Razorpay keys configured calls the mock Razorpay orders endpoint.
- A20: Notification scheduler with `ConsoleSender` writes a deadline alert to the console outbox.
- A21: Frontend access token is not stored in `localStorage`; refresh uses `credentials: "include"`.
- A22: `/opportunities/[id]` does not render "Load sample" buttons unless `NEXT_PUBLIC_DEMO_MODE=true`.
- A23: `/admin` renders a workspace list for super-admins.
- A24: `next lint` and `tsc --noEmit` pass in CI.
- A25: `.env.local` template exists and `scripts/run.sh local` boots the stack.

## Out of scope

- Live payment capture (requires real Razorpay/Stripe accounts and webhooks).
- Live email/SMS delivery (requires SES/MSG91 credentials and domain verification).
- Apple/Google OIDC (code is present; live keys and app-store setup deferred).
- Multi-region deployment / data-residency controls (P2).
- Full accuracy harness CI with golden set and QS sign-off (requires Anthropic key and domain-expert labels).

## Assumptions

- `TS_ENV` will be set to `prod` in all real deployments; `dev` is only for local development and tests.
- Redis is optional for rate limiting and notifications in single-instance dev; production must configure `TS_REDIS_URL`.
- S3 is optional in dev/tests; production must configure `TS_STORAGE_TYPE=s3`.
