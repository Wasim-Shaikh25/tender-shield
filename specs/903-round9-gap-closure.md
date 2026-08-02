# Round 9 Audit Gap Closure — Spec

**Status:** draft  
**Requirement refs:** `docs/GAP_CLOSURE_REQUIREMENTS.md`; `PRODUCTION_READINESS_AUDIT.md` TS-INT-03, TS-INT-02, TS-ACL-01, TS-PUB-04, TS-GOV-01, TS-EV-01; `docs/TenderShield_Full_Build_Doc.md` §3.2, §5, §6, §11.2, §11.5, §14, §15.  
**Task refs:** TS-335, TS-336, TS-337, TS-338, TS-339, TS-340, TS-341.

## Purpose

This spec captures the third batch of production-readiness hardening identified in the Round 9 audit (`PRODUCTION_READINESS_AUDIT.md`). It closes the security/auth/data-integrity gaps introduced by Phase 22 integrations and governance work, and fixes the eval accuracy regression that keeps the deadline/tender-value match below the 95% bar.

## Public interface

No new top-level modules. Existing interfaces are extended/hardened:

- **Integrations** (`app/modules/integrations/*`):
  - `DynamicConnectorConfig` URL validation helper.
  - `BaseConnector.verify_webhook(source, raw_body, signature, secret)` hook.
  - `POST /api/integrations/sources/{source_id}/webhook` requires `X-Integration-Signature`.
  - `POST /api/integrations/dynamic-connectors`, `PUT ...`, `POST .../test`, `POST .../poll` validate `base_url`.
- **Auth** (`app/modules/auth/*`):
  - New registry capability `auth.require_document_class` or `auth.document_class_permitted` used as a dependency.
  - `AuthAcl.permitted` remains the source of truth; enforcement is expanded to read/export routes.
- **Public API** (`app/modules/public_api/*`):
  - `request_signature` validates `notice_id` and `change_event_id` through soft-dep registry capabilities.
- **Governance** (`app/modules/governance/*`):
  - New scheduler capability `governance.retention_job` executed by `app/core/scheduler.py`.
  - `DataGovernance` `encryption_at_rest` value is honored by `Storage` writes when set to `sse-s3` or `sse-kms`.
- **Ingestion / Risk** (`app/modules/ingestion/*`, `app/modules/risk/*`):
  - Extraction prompts and post-processors supply `project_duration_months`, `tender_deadline`, `contract_value_minor`, and `currency`.

## Data owned

No new tables except where noted below:

- `integration_sources.config` gains an optional `webhook_secret` key (stored in the existing encrypted-at-rest JSON `config`).
- `documents.deleted_at` may be used by the retention job if it does not already exist.
- `audit_log` records retention/archive/delete actions.

## Behavior

### B1 — Dynamic connector SSRF protection (TS-336)

- **B1.1** `DynamicRestConnector` validates `base_url` before building an `httpx.Client`.
- **B1.2** Allowed schemes are `http` and `https` only.
- **B1.3** Loopback, link-local, private, and multicast/reserved IP ranges are rejected, both for literal IPs and for resolved DNS names.
- **B1.4** URLs containing embedded credentials (`user:pass@host`) are rejected.
- **B1.5** Validation is enforced on create, update, test, and poll; errors raise `IntegrationsError("invalid_url")` which maps to HTTP `400`.

### B2 — Integration source webhook signature verification (TS-337)

- **B2.1** Each `IntegrationSource` that may receive webhooks has a `webhook_secret`.
- **B2.2** The router reads `X-Integration-Signature` from the request headers and passes the raw body to `IntegrationsService.handle_webhook`.
- **B2.3** `handle_webhook` calls `connector.verify_webhook(source, raw_body, signature, secret)`.
- **B2.4** Default HMAC-SHA256 verification uses `hmac.compare_digest`. Concrete connectors may override the method.
- **B2.5** Verification failure returns `401 unauthorized` and does not emit `integrations.webhook_received`.

### B3 — Document-class ACL enforcement (TS-338)

- **B3.1** `AuthAcl.permitted` remains unchanged and returns `True` for `owner`/`superadmin` and when no rule exists.
- **B3.2** A new dependency `require_document_class(doc_class: str)` is published in the auth module registry.
- **B3.3** Export, change, claims, and drafting routes that serve document-derived content use the dependency.
- **B3.4** Ingestion upload routes are refactored to use the same dependency, preserving existing behavior.

### B4 — Public API signature request validation (TS-339)

- **B4.1** `PublicApiService.request_signature` validates `notice_id` (if provided) by querying the workspace/opportunity-scoped notice registry.
- **B4.2** It validates `change_event_id` (if provided) by calling the `change` module's service factory.
- **B4.3** Invalid IDs raise `PublicApiError("no_such_notice")` or `PublicApiError("no_such_change_event")`, mapped to `404`.
- **B4.4** The module does not import `change` or `baseline` directly; it uses registry capabilities.

### B5 — Governance retention execution (TS-340)

- **B5.1** A scheduler job scans workspaces with `retention_days` configured and `legal_hold=false`.
- **B5.2** Documents older than `archive_after_days` are moved/archived if that setting is present; otherwise they are deleted at `retention_days`.
- **B5.3** Hard deletion is preceded by a soft `deleted_at` grace period controlled by `TS_RETENTION_GRACE_DAYS` (default 30).
- **B5.4** Every retention action is appended to the `audit_log`.
- **B5.5** The job is disabled unless `TS_RETENTION_JOB_ENABLED=true`.

### B6 — Eval deadline and tender-value match (TS-341)

- **B6.1** Deadline extraction prompts explicitly ask for `tender_deadline`, `contract_period_start`, `contract_period_end`, and `project_duration_months`.
- **B6.2** A post-processor reconciles extracted numbers and dates with the known portal values in the eval corpus.
- **B6.3** `project_duration_months` is computed from period start/end when absent, and severity rules receive it without defaulting.
- **B6.4** `scripts/eval_ci_smoke.py` reports `Deadline / tender-value match vs portal` ≥95%.

## Acceptance criteria

- A1 (TS-336): `POST /api/integrations/dynamic-connectors` rejects `http://127.0.0.1/`, `http://169.254.169.254/`, `file:///etc/passwd`, and `http://user:pass@example.com/`.
- A2 (TS-336): `POST .../test` and `POST .../poll` re-validate the stored `base_url` before any outbound request.
- A3 (TS-337): A webhook POST with a valid HMAC-SHA256 signature is accepted; an invalid or missing signature is rejected with `401`.
- A4 (TS-338): A `viewer` with a `boq -> estimator` ACL rule receives `403 document_class_forbidden` on a BOQ export route.
- A5 (TS-339): `request_signature` with a `notice_id` from another workspace returns `404 no_such_notice`.
- A6 (TS-340): A document older than `retention_days` with `legal_hold=false` is soft-deleted and an `audit_log` row is created.
- A7 (TS-341): `eval_ci_smoke.py` reports deadline/value match ≥95% while M1/M4 remain at 100%.

## Out of scope

- Live OAuth/API polling for construction platforms (provider credentials not available).
- Drawing intelligence / IFC parsing (deferred per build doc §9.3).
- Rulepack QS validation (content work, not code).

## Assumptions

- `assumption:` The `auth.document_class_permitted` registry capability exists and is the source of truth for document-class ACLs.
- `assumption:` The scheduler module (`app.core.scheduler`) can run periodic jobs when configured; otherwise the retention job logs a warning and is skipped.
- `assumption:` The eval smoke corpus (`scripts/eval_ci_smoke.py`) is a sufficient proxy for portal-matched extraction accuracy until the gold set (TS-233) is available.
