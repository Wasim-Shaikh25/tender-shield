# Round 9 Audit Gap Closure — Requirements

**Sourced from:** `PRODUCTION_READINESS_AUDIT.md` (Round 9 / Phase 22)  
**Created:** 2026-08-02  
**Status:** Draft  
**Owner:** Engineering / Security  

## 1. Purpose

This document converts the Round 9 production-readiness audit findings into concrete, implementable requirements. Closing these gaps is the path from the current `STOP — CONDITIONAL GO` recommendation to `STOP — GO` for a controlled pilot, and eventually to public / paid general availability.

## 2. Scope

The gaps are tracked as new tasks `TS-335` through `TS-341` in `tasks/backlog.md`. The work is intentionally limited to the issues identified in the Round 9 audit:

| Audit ID | New task | Title | Priority | Release impact |
|---|---|---|---|---|
| TS-INT-03 | TS-336 | Dynamic REST connector SSRF protection | P0 (security) | Blocks public multi-tenant; pilot must disable or patch |
| TS-INT-02 | TS-337 | Integration source webhook signature verification | P0 (security) | Blocks enabling live webhooks; currently unauthenticated |
| TS-ACL-01 | TS-338 | Document-class ACL enforcement on read/export/change/claims/drafting paths | P1 (authorization) | Required if document-class ACL is marketed |
| TS-PUB-04 | TS-339 | Public API `request_signature` `notice_id` / `change_event_id` validation | P1 (data integrity) | Prevents cross-workspace reference pollution |
| TS-GOV-01 | TS-340 | Governance retention / archive execution job | P2 (compliance) | Needed for GDPR/DPDP deletion commitments |
| TS-EV-01 | TS-341 | Eval deadline and tender-value match ≥95% | P1 (accuracy) | Core product credibility |
| — | TS-335 | Gap-closure requirements + spec | P0 (coordination) | Enables the rest |

Out of scope for this batch:
* Rulepack QS validation (TS-P02) — product/content work, not a code-only fix.
* Live connector OAuth staging tests (TS-333) — blocked on provider credentials.
* Drawing-intelligence features (TS-321–TS-326) — deferred by build doc §0.2/§9.3.

## 3. Requirements

### R1 — Dynamic REST connector SSRF protection (TS-336)

**Requirement refs:** `PRODUCTION_READINESS_AUDIT.md` TS-INT-03; `specs/modules/integrations.md`  
**Status:** `done`.

The dynamic connector accepts an arbitrary `base_url`, `auth_config`, `headers`, and `pagination` from a workspace admin and makes outbound HTTP requests from the backend. The system must reject any `base_url` that could be used to access internal infrastructure, cloud metadata services, or non-HTTP protocols.

#### Acceptance criteria

1. **Scheme validation.** `base_url` must parse as `http://` or `https://`. `file://`, `ftp://`, `data://`, `gopher://`, and any other scheme are rejected with `400 invalid_url`.
2. **Host validation.** The host must not be a loopback address (`127.0.0.0/8`, `::1/128`), a link-local address (`169.254.0.0/16`, `fe80::/10`), a private RFC-1918 address (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7`), or `localhost`.
3. **DNS resolution guard.** If the host is a DNS name, the resolved IP must not fall into any blocked range. Implementation may perform a blocking DNS resolution and re-check, or use a library that enforces this.
4. **Credential strip.** URLs containing `user:password@` components are rejected.
5. **No path override surprises.** `httpx.Client(base_url=...)` with `client.get("/")` must not concatenate in a way that ignores the configured base path. Document and test the behavior for `base_url` ending with and without a trailing slash.
6. **Test coverage.** Unit tests must assert rejection for:
   - `http://127.0.0.1/`
   - `http://localhost/`
   - `http://169.254.169.254/latest/meta-data/`
   - `http://10.0.0.1/`
   - `file:///etc/passwd`
   - `http://user:pass@example.com/`
7. **Error responses.** Invalid URLs in `POST /api/integrations/dynamic-connectors` and `PUT ...` return `400` with code `invalid_url`. The `test` and `poll` endpoints must validate the stored URL again before issuing the request.

### R2 — Integration source webhook signature verification (TS-337)

**Requirement refs:** `PRODUCTION_READINESS_AUDIT.md` TS-INT-02; `specs/modules/integrations.md`  
**Status:** `done`.

`POST /api/integrations/sources/{source_id}/webhook` is currently unauthenticated and only publishes a domain event. Before the endpoint is used for live Procore, Aconex, Autodesk, SharePoint, or ERP webhooks, it must authenticate the caller.

#### Acceptance criteria

1. **Per-source secret.** `integration_sources.config` must support a `webhook_secret` field. `IntegrationsService.create_source` may generate one if the source supports webhooks, or accept one from the admin.
2. **Signature header.** The endpoint must require a signature header (`X-Integration-Signature`) containing the hex-encoded HMAC-SHA256 of the raw request body using `webhook_secret`.
3. **Connector abstraction.** `BaseConnector` exposes `verify_webhook(source, raw_body, signature, secret) -> bool` with a default HMAC-SHA256 implementation. Concrete connectors may override it (e.g., Procore's signed request format).
4. **Constant-time compare.** Signature comparison uses `hmac.compare_digest`.
5. **Failure handling.** Missing header, missing secret, or invalid signature returns `401 unauthorized` and does not publish the event.
6. **Test coverage.** Tests for:
   - Valid signature accepted.
   - Invalid signature rejected.
   - Missing header rejected.
   - Unknown `source_id` still returns `404` / generic error to avoid enumeration.

### R3 — Document-class ACL enforcement on read/export/change/claims/drafting (TS-338)

**Requirement refs:** `PRODUCTION_READINESS_AUDIT.md` TS-ACL-01; `specs/modules/auth.md`, `specs/modules/ingestion.md`  
**Status:** `done`.

`backend/app/modules/auth/acl.py` implements document-class rules (`auth.document_class_permitted`), but the check is currently only called on ingestion upload. If an admin sets a rule such as `document_class=boq min_role=estimator`, a `viewer` can still view or export those documents.

#### Acceptance criteria

1. **Reusable dependency.** Add `require_document_class(document_class: str)` to `app.core.deps` (or `app.modules.auth.deps`) that:
   - Looks up `auth.document_class_permitted` from the registry.
   - Returns a `Principal` when allowed.
   - Raises `403 document_class_forbidden` when denied.
   - Is permissive when no rule exists for the workspace/document class.
2. **Apply to read/export paths.** Add the dependency to relevant `GET`/`POST` routes in:
   - `export/router.py`
   - `change/router.py` where change event sources reference documents
   - `claims/router.py` where claims reference documents
   - `drafting/router.py`
   - Any other route that returns document content or derived artifacts.
3. **Apply to ingestion register.** Keep the existing checks in `ingestion/router.py` (they can be refactored to use the new dependency).
4. **Role inheritance.** `AuthAcl.ROLE_RANK` already defines `viewer < reviewer < estimator < admin < owner`; `permitted` uses `>=` rank. Preserve this behavior.
5. **Test coverage.** For a workspace with `boq -> estimator`:
   - `viewer` GET `/api/export/opportunities/{id}/report` with BOQ-derived findings → `403`.
   - `estimator` and `admin` succeed.
   - `viewer` GET `/api/opportunities/{id}/documents` for `gcc` documents (no rule) succeeds.

### R4 — Public API `request_signature` `notice_id` / `change_event_id` validation (TS-339)

**Requirement refs:** `PRODUCTION_READINESS_AUDIT.md` TS-PUB-04; `specs/modules/public_api.md`  
**Status:** `done`.

`public_api/service.py` validates that the `opportunity_id` belongs to the workspace, but it does not validate `notice_id` or `change_event_id`.

#### Acceptance criteria

1. **Notice validation.** If `notice_id` is provided, verify a `Notice` row exists where `workspace_id = principal.workspace_id` and `opportunity_id = body.opportunity_id`. If not, raise `PublicApiError("no_such_notice")` / `404`.
2. **Change event validation.** If `change_event_id` is provided, verify a `ChangeEvent` row exists in the same workspace/opportunity. If not, raise `PublicApiError("no_such_change_event")` / `404`.
3. **Cross-module lookup.** The `public_api` module must not import `change` or `baseline` directly; it must use the registry capability `change.service_factory` (or equivalent) to lookup events.
4. **Test coverage.**
   - Valid IDs succeed.
   - A `notice_id` from another workspace raises `404 no_such_notice`.
   - A `change_event_id` from another workspace raises `404 no_such_change_event`.
   - Missing optional IDs still succeed.

### R5 — Governance retention / archive execution job (TS-340)

**Requirement refs:** `PRODUCTION_READINESS_AUDIT.md` TS-GOV-01; `specs/modules/governance.md`  
**Status target:** `done` when retention policy is actually executed and audited.

`governance` currently stores `retention_days`, `archive_after_days`, `legal_hold`, and `encryption_at_rest` and can return retention candidates, but no job acts on them.

#### Acceptance criteria

1. **Scheduler job.** Add `governance.retention_job` capability that:
   - Scans all workspaces with `retention_days` set and `legal_hold=false`.
   - Computes the cutoff date (`now - retention_days`).
   - Calls `ingestion.documents_for_retention` (existing capability) to list candidates.
   - For each candidate older than `archive_after_days` (if set and < retention_days), moves the object to a cold/archive storage prefix or marks it archived.
   - For candidates older than `retention_days`, hard-deletes the document row and object storage blob.
   - Records every action in the `audit_log`.
2. **Legal hold override.** If `legal_hold=true`, no documents in the workspace are deleted or archived, regardless of age.
3. **Encryption at rest.** If `encryption_at_rest` is `sse-s3` or `sse-kms`, storage writes must use the corresponding SSE setting. The storage adapter already supports SSE-S3; verify it is wired through `governance` settings.
4. **Safety guards.**
   - Soft-delete first (set `deleted_at`) for a configurable grace period (e.g., 30 days) before hard deletion.
   - Run the job behind a feature flag `TS_RETENTION_JOB_ENABLED` in production until validated.
5. **Test coverage.**
   - Candidate older than retention and no legal hold is deleted.
   - Candidate with legal hold is untouched.
   - Archive-only candidates are soft-moved, not deleted.

### R6 — Eval deadline and tender-value match ≥95% (TS-341)

**Requirement refs:** `PRODUCTION_READINESS_AUDIT.md` TS-EV-01; `specs/modules/ingestion.md`, `specs/modules/risk.md`  
**Status target:** `done` when `scripts/eval_ci_smoke.py` reports `Deadline / tender-value match vs portal` ≥95%.

The eval smoke corpus currently reports 25% match for deadline and tender-value, and the severity evaluator logs `missing fact 'project_duration_months'`.

#### Acceptance criteria

1. **Prompt improvement.** Update the deadline/value extraction prompts to explicitly request:
   - `submission_date` / `tender_deadline`
   - `contract_value_minor` and `currency`
   - `project_duration_months`
   - `contract_period_start` / `contract_period_end` (if stated)
2. **Extraction reconciliation.** Add a deterministic post-processor that:
   - Parses numeric tender values from the extracted text and compares them to the portal value.
   - Parses dates using the existing deterministic date parser and flags mismatches.
   - Computes `project_duration_months` from `contract_period_start` and `contract_period_end` if absent.
3. **Severity rule facts.** The risk severity rule `critical if project_duration_months > 18 else high` must receive `project_duration_months` without defaulting to `medium`.
4. **Validation.** Re-run `python scripts/eval_ci_smoke.py --limit 20` and verify the `Deadline / tender-value match vs portal` metric reaches at least 95%.
5. **Regression.** M1/M4 pass rate and quote-verbatim rate must remain 100%.

## 4. Dependencies and ordering

1. TS-335 (requirements + spec) gates the rest.
2. TS-336 and TS-337 are security blockers and can be done in parallel.
3. TS-338 depends on the existing `auth.document_class_permitted` capability but is independent of TS-336/337.
4. TS-339 is independent of TS-336-338.
5. TS-340 depends on the scheduler and ingestion capabilities.
6. TS-341 depends on ingestion/risk prompt engineering and may require an LLM key.

## 5. Definition of done for the batch

- All P0/P1 tasks are `done` in `tasks/backlog.md`.
- Each task has a spec update or new spec in `specs/`.
- Backend lint, type check, and `pytest -q` pass.
- Postgres RLS tests pass with a non-superuser role.
- Frontend build and a11y pass.
- `CHANGELOG.md` `[Unreleased]` lists the closed tasks.
- `PRODUCTION_READINESS_AUDIT.md` is updated to reflect closure of TS-INT-03, TS-INT-02, TS-ACL-01, TS-PUB-04, TS-GOV-01, and TS-EV-01.
- The final audit recommendation can move from `STOP — CONDITIONAL GO` to `STOP — GO` for the controlled pilot (rulepack validation still pending for public launch).
