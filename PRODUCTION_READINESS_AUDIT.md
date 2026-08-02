# TenderShield — Production Readiness Audit (Round 9 / Phase 22)

**Repository:** `Wasim-Shaikh25/tender-shield`  
**Commit audited:** `90a10b0aa373178ace52b151dcbf162de4f386e3` (`main`)  
**Previous audit:** Round 8 report (`18d1e45`) is preserved in git history  
**Audit date:** 2026-08-02  
**Auditor roles:** Principal Software Engineer, Application Security Engineer, QA/Test Engineer, DevOps/SRE, Database Architect, Product Manager, UX/A11y Specialist, Performance Engineer.

---

## 1. Executive Summary

### 1.1 Recommendation

**GO for a controlled internal or single-customer pilot. NOT GO for public / paid production launch until core rulepack patterns are QS-validated (TS-P02) and the eval deadline/tender-value match reaches ≥95% (TS-EV-01).**

The Phase 22 gap-closure work (PRs #111–#113) materially advanced the product surface: the Next.js build now emits 28 routes, Control Tower, Plan, Advisor, Settings → Integrations / API keys, and the opportunity-detail Changes / Claims / Pricing / Drawings / Subcontracts tabs are wired. Backend lint, type checks, unit tests, Postgres RLS tests, frontend build, `npm audit`, `pip-audit`, accessibility (axe-core WCAG 2.1 AA), task-tracker validation, and eval M1/M4 smoke all pass locally.

The Round 9 security/auth/data-integrity gaps are now closed: dynamic connector SSRF controls (TS-336), integration webhook signature verification (TS-337), document-class ACL enforcement on read/export/change paths (TS-338), public API `notice_id` / `change_event_id` validation (TS-339), and governance retention/archive job execution (TS-340). The remaining blockers before a public/paid launch are QS-validated rulepacks (TS-P02) and raising the eval deadline/tender-value match to ≥95% (TS-EV-01).

### 1.2 Verification summary

| Check | Command / evidence | Result |
|---|---|---|
| Backend lint | `cd backend && .venv/bin/ruff check . --target-version py311` | Pass (321 files) |
| Backend type check | `cd backend && .venv/bin/mypy app` | Pass |
| Backend unit tests (SQLite) | `cd backend && .venv/bin/pytest -q` | **580 passed, 4 skipped** |
| Postgres RLS tests | `TS_DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/app_db pytest tests/test_rls_postgres.py -q` | **5 passed** (non-superuser role) |
| Postgres core smoke | `TS_DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/app_db pytest tests/test_auth_module.py tests/test_ingestion.py tests/test_boq.py tests/test_billing.py -q` | **54 passed** |
| Frontend lint | `cd frontend && npm run lint` | Pass |
| Frontend type check | `cd frontend && npm run typecheck` | Pass |
| Frontend production build | `cd frontend && npm run build` | Pass (28 routes generated) |
| Frontend a11y (WCAG 2.1 AA) | `cd frontend && npm run a11y` | Pass (26 routes audited) |
| Frontend npm audit | `npm audit --audit-level=high` | 0 vulnerabilities |
| Backend pip-audit | `cd backend && .venv/bin/pip-audit` | No known vulnerabilities |
| Alembic up/down | `alembic upgrade head && alembic downgrade base` (SQLite) | Pass |
| Eval smoke (M1 + M4) | `python scripts/eval_ci_smoke.py --limit 5` | M1/M4 pass; deadline/tender-value match 25% vs 95% bar |
| Task tracker | `python scripts/task_tracker.py --validate` | Clean; 4 tasks blocked only on live credentials |

### 1.3 Finding count by severity

| Severity | Open | Release-blocking | IDs |
|---|---|---|---|
| **Critical** | 0 | 0 | — |
| **High** | 0 | 0 | — |
| **Medium** | 1 | 0 | TS-EV-01 |
| **Low** | 3 | 0 | TS-P02 (rulepack unvalidated — mitigated), TS-R03 (missing classifier facts — mitigated), TS-UI-03 (baseline console noise) |
| **Total** | **4** | **0** | |

*Note: TS-P02 and TS-R03 are retained/mitigated from Round 8; TS-EV-01 is the remaining open Round 9 gap; TS-INT-03, TS-INT-02, TS-ACL-01, TS-PUB-04, and TS-GOV-01 are closed.*

---

## 2. Product Context and Audit Coverage

### 2.1 Product purpose and scope

TenderShield is a contractor commercial-intelligence platform. The launch wedge is **Tender Risk + BOQ Assurance**: ingest a tender pack (NIT/RFP, GCC/SCC, specs, BOQ, addenda), surface risk clauses, deadline traps, BOQ defects and scope gaps with exact citations, and generate bid-decision artifacts. Source of truth: `docs/TenderShield_Full_Build_Doc.md` v1.0.

### 2.2 Architecture

* **Backend:** FastAPI modular monolith, ~34 modules under `backend/app/modules/`. Modules interact only via the service registry and event bus; no direct cross-module imports.
* **Frontend:** Next.js 15 + TypeScript + Tailwind. Build now emits 28 routes (up from 24 in Round 8).
* **Database:** PostgreSQL with `FORCE ROW LEVEL SECURITY` workspace isolation; SQLite fallback for dev/tests.
* **CI/CD:** GitHub Actions runs backend lint/type/test/security, Postgres RLS tests, Alembic up/down, frontend lint/type/audit/build/a11y, eval smoke, and backlog validation.

### 2.3 Scope of this round

Round 9 audited the Phase 22 changes merged in PRs #111–#113:

1. Frontend surfaces for Changes, Claims, Control Tower, Subcontracts, Pricing, Drawings, Settings → Integrations, Settings → API keys, and Advisor.
2. Generic dynamic REST connector and live CDE/ERP connector scaffolding.
3. Governance / data residency / retention controls.
4. Document-class ACL backend.
5. Re-verification of Round 8 security/auth/RLS fixes plus the new code.

### 2.4 Files, routes and modules reviewed

| Layer | Reviewed |
|---|---|
| Backend modules | `auth` (ACL, approval, service), `ingestion`, `risk`, `boq`, `findings`, `review`, `drafting`, `export`, `billing`, `public_api`, `integrations` + `connectors/dynamic`, `change`, `claims`, `controltower`, `outcomes`, `analytics`, `assistant`, `baseline`, `drawings`, `governance`, `subcontract`, `pricing` |
| Frontend routes | `/login`, `/opportunities`, `/opportunities/[id]` (tabs: risks, BOQ, artifacts, changes, claims, pricing, drawings, subcontracts, handover, audit), `/analytics`, `/controltower`, `/plan`, `/assistant`, `/billing`, `/team`, `/settings`, `/settings/integrations`, `/settings/api-keys`, `/advisor`, `/admin/*`, `/help`, `/support/tickets` |
| Config / infra | `.env.local`, `.env.dev`, `.env.prod`, `docker-compose.yml`, `backend/Dockerfile`, `backend/pyproject.toml`, `.github/workflows/ci.yml`, `docs/runbooks/` |

### 2.5 Commands and tests executed

* `ruff check . --target-version py311` — pass
* `mypy app` — pass
* `pytest -q` — 580 passed, 4 skipped
* `pip-audit` — no known vulnerabilities
* `npm run lint && npm run typecheck && npm run build && npm run a11y` — pass
* `npm audit --audit-level=high` — 0 vulnerabilities
* `alembic upgrade head && alembic downgrade base` — pass
* `pytest tests/test_rls_postgres.py -q` against a non-superuser Postgres role — pass
* `pytest tests/test_auth_module.py tests/test_ingestion.py tests/test_boq.py tests/test_billing.py` against Postgres — pass
* `python scripts/eval_ci_smoke.py --limit 5` — M1/M4 pass; deadline match 25%
* `python scripts/task_tracker.py --validate` — clean

### 2.6 Scope limitations and exclusions

* **Live payment provider webhooks** (Razorpay/Stripe) and **real email/SMS OTP** were not exercised because they require live credentials; the adapters and signature verification code were reviewed and unit tests pass.
* **Real scanned-table OCR** (RapidOCR ONNX model download) was not run in this sandbox.
* **Full browser golden-path smoke** (sign-up → upload → BOQ → review → export) was not re-recorded in this round; Round 8 evidence and the passing frontend build + a11y provide UI-level confidence.
* **Penetration testing / load testing / disaster-recovery drills** were not performed.
* **Advisor multi-client workflows** and live connector OAuth handshakes require staging credentials not available.

### 2.7 Assumptions and contradictions

* The product build doc explicitly postpones general-purpose BIM/drawing intelligence (§0.2, §9.3). The new Drawings module is therefore a Phase 22 / P3 capability and is audited for security/RLS but not for domain completeness.
* `FEATURE_COVERAGE.md` and `docs/REMAINING_GAPS_ROADMAP.md` list TS-301–TS-334. The Round 22 PRs mark many UI tasks `done`, but `REMAINING_GAPS_ROADMAP.md` still shows TS-301–TS-307 as `todo`. This is a documentation sync contradiction; the code and build output show the UI surfaces implemented.

---

## 3. Product Completeness Assessment

### 3.1 Role-to-capability matrix

| Role | Dashboard / landing | Key capabilities | Status |
|---|---|---|---|
| Anonymous | Public marketing / login | Sign up, log in | Implemented |
| Owner / Admin | `/opportunities`, `/controltower`, `/analytics` | Workspace creation, member/role management, billing, team, settings, integrations, API keys, subcontract/change/claims/pricing/drawings tabs | Implemented |
| Estimator | `/opportunities/[id]` | Upload, run BOQ, pricing build-up/sensitivity, schedule import, subcontract creation | Implemented |
| Reviewer | `/opportunities/[id]` | Review/accept/reject findings | Implemented |
| Viewer | `/opportunities`, `/analytics` | Read-only access to dashboards and reports | Implemented |
| Superadmin | `/advisor`, `/admin/*` | Multi-workspace advisor view, user/workspace admin, audit log | Implemented |
| QS / External reviewer | Public API / e-signature | Request signature, status callback, API-key read | Implemented (backend; public portal minimal) |

### 3.2 Entity-to-operation matrix (selected)

| Entity | Create | View | List | Update | Delete | Search/Filter | Export | Audit |
|---|---|---|---|---|---|---|---|---|
| Opportunity | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Document | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| Finding | auto | ✓ | ✓ | ✓ (review) | — | ✓ | ✓ | ✓ |
| BOQ run | ✓ | ✓ | ✓ | — | — | — | ✓ | ✓ |
| Baseline | ✓ | ✓ | — | — | — | — | ✓ | ✓ |
| Change event | ✓ | ✓ | ✓ | ✓ (confirm/triage/impacts) | — | ✓ | ✓ | ✓ |
| Claim | ✓ | ✓ | ✓ | ✓ (quantum/responses/negotiations/settlement) | — | ✓ | ✓ | ✓ |
| Subcontract | ✓ | ✓ | ✓ | ✓ (clauses/scope/payments) | — | ✓ | — | ✓ |
| Integration source | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | ✓ |
| Dynamic connector | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | ✓ |
| Public API key | ✓ | ✓ | ✓ | revoke | — | — | — | ✓ |
| Report template | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | ✓ |
| Data governance policy | ✓ | ✓ | — | ✓ | — | — | — | ✓ |
| Document-class ACL rule | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | ✓ |

### 3.3 Workflow completeness

| Workflow | Status | Notes |
|---|---|---|
| Pre-bid (upload → classify → deadlines → risk → BOQ → review → export) | Implemented | Golden path covered by tests and Round 8 E2E |
| Award & baseline (award → compare → freeze → handover → notice register) | Implemented | Backend + Handover tab |
| Change-to-claim (signal → event → confirm → notice deadline → draft → evidence → claim → outcome) | Implemented | Backend + Changes/Claims tabs |
| Subcontract flowdown | Implemented | Backend + Subcontracts tab |
| Commercial Control Tower | Implemented | `/controltower` with exposure/forecast/response times/clause trends |
| Integrations / dynamic REST connector | Partial | UI + backend scaffolding; live connectors need staging credentials |
| Advisor / multi-client workspace | Partial | `/advisor` exists; multi-client usage requires real usage data |

### 3.4 Dashboard and reporting matrix

| Dashboard | Role | Route | Status |
|---|---|---|---|
| Opportunities board | All internal | `/opportunities` | Implemented |
| Opportunity detail / tender workbench | All internal | `/opportunities/[id]` | Implemented |
| Analytics / risk / deadline / BOQ summary | Viewer+ | `/analytics` | Implemented |
| AI plan dashboard | Viewer+ | `/plan` | Implemented (nav link added) |
| Control Tower | Admin+ | `/controltower` | Implemented |
| Billing & plan | Owner/Admin | `/billing`, `/billing/settings` | Implemented |
| Team management | Owner/Admin | `/team` | Implemented (Round 8 fix) |
| Settings (profile, notifications, integrations, API keys, document ACL) | Owner/Admin | `/settings`, `/settings/integrations`, `/settings/api-keys` | Implemented |
| Advisor / multi-client | Superadmin | `/advisor` | Implemented |
| Admin console | Superadmin | `/admin/*` | Implemented |

### 3.5 Missing requirements and discovery gaps

| ID | Gap | Classification | Priority |
|---|---|---|---|
| TS-P02 | All bundled risk patterns still `confidence: unvalidated` | Confirmed Missing Requirement | Release blocker for paid public launch |
| TS-EV-01 | Eval `Deadline / tender-value match vs portal` is 25% vs 95% bar | Confirmed Missing Requirement | High |
| TS-ACL-01 | Document-class ACL enforced on ingestion read/export/change paths (TS-338) | Closed | Medium |
| TS-GOV-01 | Governance retention/archive job implemented (TS-340) | Closed | Medium |
| TS-INT-02 | Integration source webhook receiver verifies HMAC-SHA256 signatures (TS-337) | Closed | Medium |
| TS-INT-03 | Dynamic REST connector validates and blocks unsafe URLs (TS-336) | Closed | High |
| TS-PUB-04 | Public API `request_signature` validates `notice_id` / `change_event_id` (TS-339) | Closed | Medium |

### 3.6 Product decisions required

1. **Rulepack validation roadmap:** When will QS-validated patterns be available, and which patterns must be validated before public launch?
2. **Eval deadline/value match:** What is the timeline and data/LLM work needed to raise `Deadline / tender-value match vs portal` from 25% to ≥95%?

---

## 4. Detailed Findings

### 4.1 Historical Round 8 findings — status

The prior Round 8 audit identified catastrophic cross-tenant and billing release blockers. All were fixed before `main` commit `90a10b0`:

| ID | Title | Round 9 status | Evidence |
|---|---|---|---|
| TS-A01 | Any authenticated user can join any workspace as owner | Fixed | `auth/service.py` validates workspace membership; tests pass |
| TS-A02 | Google sign-in grants `owner` to every user | Fixed | Google/Apple OIDC routes removed |
| TS-A03 | Row-Level Security structurally inoperative | Fixed | Migrations `ENABLE` + `FORCE ROW LEVEL SECURITY`; `bind_workspace_context` sets `app.workspace_id`; Postgres RLS tests pass with non-superuser role |
| TS-B01 | Client controls payment amount; webhook activates without validation | Fixed | `billing/router.py` recomputes amount server-side; webhooks verify signatures and idempotency |
| TS-B02 | Webhook processing not atomic | Fixed | `WebhookEvent` unique constraint + savepoint in `_claim_event_id` |
| TS-F01 | Workspace list contract mismatch | Fixed | `SessionProvider` consumes `WorkspaceResponse[]` directly |
| TS-A06 | Workspace switch does not persist refresh token | Fixed | `auth/service.py` commits rotated tokens |
| TS-A08 | Invitation tokens stored plaintext | Fixed | `token_hash` stored; plaintext token returned once |
| TS-A10 | `create_invitation` accepts arbitrary `project_id` | Fixed | Validates project workspace |
| TS-PUB-01 | `public_api` not RLS-bound | Fixed | `app.api_key_hash` / `app.external_id` GUCs used for RLS-safe lookup |
| TS-PUB-03 | E-signature callback unauthenticated | Fixed | `X-Callback-Secret` header required in production; status allow-list enforced |
| TS-INT-01 | Integration source creation accepts arbitrary `opportunity_id` | Fixed | `IntegrationsService.create_source` calls `get_opportunity` |
| TS-O01 | Rate limiting ineffective across instances | Fixed | Production requires `TS_REDIS_URL` and `TS_TRUSTED_PROXIES`; `core/ratelimit.py` derives client IP from `X-Forwarded-For` |
| TS-R03 | Severity evaluator defaults missing facts | Mitigated | `MissingFactError` raised, logged, and defaulted; see §4.4 |
| TS-P02 | Rulepack patterns unvalidated | Mitigated | `beta_unvalidated=true` default with disclaimer; see §4.4 |

### 4.2 Critical

No new Critical findings in this round. Prior Criticals are structurally resolved.

### 4.3 High

#### TS-INT-03 — Dynamic REST connector `test`/`poll` endpoints allow server-side request forgery

* **Status:** Closed (TS-336).
* **Classification:** Probable Risk.
* **Severity:** High.
* **Category:** Security / SSRF.
* **Disposition:** Closed — `DynamicRestConnector` validates `base_url` scheme, host, IP range, embedded credentials, and fragments before any outbound request. Disabling dynamic connectors remains possible via `TS_DYNAMIC_CONNECTORS_ENABLED`.
* **Release impact:** A workspace admin can cause the backend to issue HTTP requests to arbitrary `base_url` values, including cloud metadata endpoints (`http://169.254.169.254/`), internal services, or file URLs. The `test` endpoint returns the response body preview to the caller.
* **Affected roles:** Admin (dynamic connector creation/testing).
* **Affected files / endpoints:**
  * `backend/app/modules/integrations/connectors/dynamic.py:76-90` (`_client` construction)
  * `backend/app/modules/integrations/connectors/dynamic.py:125-181` (`fetch`)
  * `backend/app/modules/integrations/service.py:700-728` (`test_dynamic_connector`)
  * `backend/app/modules/integrations/router.py:385-396` `POST /api/integrations/dynamic-connectors/{id}/test`
  * `backend/app/modules/integrations/router.py:398-410` `POST /api/integrations/dynamic-connectors/{id}/poll`
* **Evidence:**

```python
# backend/app/modules/integrations/connectors/dynamic.py:76-90
def _client(self, config: DynamicConnectorConfig) -> httpx.Client:
    headers = dict(config.headers or {})
    auth = None
    auth_config = config.auth_config or {}
    if config.auth_type == "bearer":
        token = auth_config.get("token", "")
        headers["Authorization"] = f"Bearer {token}"
    ...
    return httpx.Client(base_url=config.base_url, headers=headers, auth=auth, timeout=30.0)
```

There is no validation of `config.base_url` scheme, host, or IP range. `test_dynamic_connector` then calls `client.get("/")` and returns `body` (`resp.text[:500]`) in the JSON response.

* **Root cause:** Input URL is trusted without SSRF validation.
* **Impact:** Cloud metadata theft, internal reconnaissance, credential exfiltration from internal services, or request smuggling.
* **Likelihood:** Medium in a pilot with trusted admins; High in public multi-tenant.
* **Recommended solution:**
  1. Validate `base_url` in `create_dynamic_connector` / `update_dynamic_connector`: require `http`/`https`, reject non-public / private / loopback / link-local / metadata IPs, and reject URLs containing credentials or fragments.
  2. Enforce a short timeout and explicit DNS resolution block list.
  3. Consider disabling dynamic connectors by default behind `TS_DYNAMIC_CONNECTORS_ENABLED` until validated.
* **Code example:**

```python
# Illustrative validation helper (add to integrations/connectors/dynamic.py)
import ipaddress, urllib.parse

_BLOCKED_SCHEMES = {"file", "ftp", "gopher", "data"}
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

def _is_safe_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    try:
        addr = ipaddress.ip_address(hostname)
        if any(addr in net for net in _BLOCKED_NETWORKS):
            return False
    except ValueError:
        # hostname; resolve after DNS to ensure it does not resolve to blocked ranges
        pass
    return True
```

* **Regression risks:** Existing dynamic connector tests that use `http://localhost` or private fixtures will need safe test URLs.
* **Tests to add:** SSRF attempts against `169.254.169.254`, `127.0.0.1`, `file:///etc/passwd`, and private ranges must be rejected.
* **Similar locations:** `integrations/connectors/base.py` subclasses (`ProcoreAdapter`, `AutodeskAdapter`, etc.) if/when live HTTP clients are implemented.

### 4.4 Medium

#### TS-INT-02 — Integration source webhook receiver is unauthenticated

* **Status:** Closed (TS-337).
* **Classification:** Confirmed Risk.
* **Severity:** Medium.
* **Category:** Security / webhooks.
* **Disposition:** Closed — `POST /api/integrations/sources/{source_id}/webhook` requires `X-Integration-Signature` and `BaseConnector.verify_webhook` performs HMAC-SHA256 comparison.
* **Release impact:** Any caller that knows or guesses a `source_id` can POST to `/api/integrations/sources/{source_id}/webhook` and emit an `integrations.webhook_received` event.
* **Affected roles:** Anonymous / unauthenticated.
* **Affected files / endpoints:**
  * `backend/app/modules/integrations/router.py:297-307` `POST /api/integrations/sources/{source_id}/webhook`
  * `backend/app/modules/integrations/service.py:591-606` `handle_webhook`
* **Evidence:**

```python
@router.post("/sources/{source_id}/webhook")
def receive_webhook(
    source_id: str,
    payload: dict,
    request: Request,
    session: Session = Depends(get_session),
):
    try:
        return _service(request, session).handle_webhook(source_id, payload)
    except IntegrationsError as exc:
        _raise(exc)
```

No signature header, secret query parameter, or HMAC verification is required. `handle_webhook` only publishes an event and returns `{"status": "received"}`, but the event could be consumed by future subscribers.

* **Root cause:** Webhook endpoint was scaffolded without provider-specific signature verification.
* **Impact:** Event spoofing, noise, and potential downstream actions if handlers are added later.
* **Likelihood:** Low until live connectors are enabled; becomes Medium/High with real Procore/Aconex/etc. webhooks.
* **Recommended solution:**
  1. Store a per-source `webhook_secret` (or use the source config) and require a signature header.
  2. Add an `BaseConnector.verify_webhook(source, raw_body, signature, secret)` hook.
  3. Return `401` when signature is missing or invalid.
* **Code example:**

```python
# Illustrative signature check in integrations/router.py
import hmac, hashlib

@router.post("/sources/{source_id}/webhook")
async def receive_webhook(
    source_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    raw = await request.body()
    signature = request.headers.get("X-Integration-Signature", "")
    service = _service(request, session)
    try:
        return service.handle_webhook(source_id, raw, signature)
    except IntegrationsError as exc:
        _raise(exc)
```

#### TS-ACL-01 — Document-class ACL is only enforced on ingestion upload/register

* **Status:** Closed (TS-338).
* **Classification:** Confirmed Missing Requirement.
* **Severity:** Medium.
* **Category:** Authorization.
* **Disposition:** Closed — `require_document_class` / `require_document_access` dependencies guard ingestion read routes; `ExportService.export` and `ChangeService.run_baseline_diff` enforce the ACL via `auth.document_class_permitted`.
* **Release impact:** An admin can create a rule restricting `document_class=BOQ` to `estimator+`, but a `viewer` can still read/export those documents through `export`, `change`, `claims`, and `drafting` endpoints.
* **Affected roles:** Viewer / Reviewer / Estimator.
* **Affected files:**
  * `backend/app/modules/auth/acl.py` (ACL rule engine)
  * `backend/app/modules/ingestion/router.py:120-125` (enforced on upload)
  * Missing in: `backend/app/modules/export/router.py`, `backend/app/modules/change/router.py`, `backend/app/modules/claims/router.py`, `backend/app/modules/drafting/router.py`
* **Evidence:** Grep shows `permitted_fn` usage only in `ingestion/router.py`:

```python
permitted_fn = request.app.state.ctx.registry.get("auth.document_class_permitted")
if permitted_fn is not None and not permitted_fn(
    session, principal.workspace_id, principal.role, document_class
):
    raise HTTPException(403, "document_class_forbidden")
```

No other module calls this capability.

* **Root cause:** ACL check was added to the upload path but not generalized to read/export paths.
* **Impact:** Unauthorized access to restricted document classes despite configured policy.
* **Likelihood:** Medium once document-class ACL rules are configured in production.
* **Recommended solution:** Centralize document-class enforcement in a dependency (e.g., `require_document_class(document_class)`) and apply it to all routes that read, export, or modify documents of a given class. The ACL default should remain permissive when no rule exists.
* **Tests to add:** Viewer should be denied `GET /api/export/opportunities/{id}/report` when `document_class` is restricted; estimator/owner should pass.

#### TS-PUB-04 — Public API `request_signature` accepts arbitrary `notice_id` / `change_event_id`

* **Status:** Closed (TS-339).
* **Classification:** Confirmed Risk.
* **Severity:** Medium.
* **Category:** Authorization / data integrity.
* **Disposition:** Closed — `PublicApiService.request_signature` validates both IDs against workspace/opportunity-scoped `ChangeEvent` rows via `change.service_factory`; mismatches return `404 no_such_notice` / `404 no_such_change_event`.
* **Release impact:** A caller with a valid workspace API key (write scope) can create a `PublicSignatureRequest` referencing a `notice_id` or `change_event_id` that does not belong to the workspace. The row is stored with the correct `workspace_id`, but the foreign reference may be invalid or cross-tenant.
* **Affected roles:** External API consumer (write scope).
* **Affected files:**
  * `backend/app/modules/public_api/router.py:120-145`
  * `backend/app/modules/public_api/service.py:117-154`
* **Evidence:**

```python
def request_signature(self, workspace_id, opportunity_id, *, ...):
    opportunity_uuid = uuid.UUID(str(opportunity_id))
    opp = self._ingestion().get_opportunity(workspace_id, opportunity_uuid)
    if opp is None:
        raise PublicApiError("no_such_opportunity")
    external_id = secrets.token_urlsafe(16)
    row = PublicSignatureRequest(
        workspace_id=uuid.UUID(str(workspace_id)),
        opportunity_id=uuid.UUID(str(opportunity_id)),
        notice_id=uuid.UUID(str(notice_id)) if notice_id else None,   # not validated
        change_event_id=uuid.UUID(str(change_event_id)) if change_event_id else None,  # not validated
        ...
    )
```

* **Root cause:** Only `opportunity_id` is validated against the workspace.
* **Impact:** Data-integrity pollution; possible cross-tenant reference; signature requests linked to wrong notices.
* **Likelihood:** Low (requires a valid API key and knowledge of another workspace's UUIDs).
* **Recommended solution:**
  1. If `notice_id` is provided, verify a `Notice` row exists for `(workspace_id, opportunity_id, notice_id)`.
  2. If `change_event_id` is provided, verify it belongs to the opportunity/workspace through the `change` service.
  3. Return `404 no_such_notice` / `no_such_event`.

#### TS-GOV-01 — Governance retention/archive settings are config-only

* **Status:** Closed (TS-340).
* **Classification:** Confirmed Missing Requirement.
* **Severity:** Medium.
* **Category:** Data governance / operations.
* **Disposition:** Closed — `GovernanceService.run_retention_job` archives, soft-deletes, and hard-deletes documents according to `retention_days` / `archive_after_days` / `TS_RETENTION_GRACE_DAYS`, with audit logging and a `TS_RETENTION_JOB_ENABLED` feature flag.
* **Release impact:** Workspaces can set `retention_days`, `archive_after_days`, `legal_hold`, and `encryption_at_rest`, but there is no automated job that archives or deletes documents based on these settings. `retention_candidates` only returns a list.
* **Affected roles:** Admin / compliance.
* **Affected files:**
  * `backend/app/modules/governance/service.py:73-80`
  * `backend/app/modules/governance/router.py:75-85`
  * `backend/app/modules/governance/models.py`
* **Evidence:**

```python
def retention_candidates(self, workspace_id) -> list[dict]:
    settings = self.get_settings(workspace_id)
    if settings.get("legal_hold"):
        return []
    retention_days = settings.get("retention_days")
    if not retention_days or self._ingestion_retention is None:
        return []
    return self._ingestion_retention(workspace_id, retention_days)
```

No follow-up deletion/archival code was found.

* **Root cause:** Governance module ships the policy model and API but not the execution layer.
* **Impact:** Customers cannot enforce retention without manual action; GDPR/DPDP deletion commitments may be unmet.
* **Likelihood:** Medium in production once retention policies are configured.
* **Recommended solution:** Add a scheduled Celery/scheduler task that calls `retention_candidates`, produces an audit log, and either hard-deletes or marks documents archived according to policy and `legal_hold`.

#### TS-EV-01 — Eval smoke `Deadline / tender-value match vs portal` is 25% vs 95% bar

* **Status:** Open.
* **Classification:** Confirmed Missing Requirement.
* **Severity:** Medium.
* **Category:** Domain accuracy / data quality.
* **Disposition:** Open — Required Before Release.
* **Release impact:** The deadline and tender-value extraction pipeline does not reliably match the portal source of truth in the synthetic smoke corpus. This directly threatens the product's core value proposition (deadline wall and bid-decision artifacts).
* **Affected files:**
  * `backend/app/modules/ingestion/deadlines.py`
  * `backend/app/modules/risk/severity.py` (missing `project_duration_months` fact)
* **Evidence:**

```
# scripts/eval_ci_smoke.py --limit 5
| Deadline / tender-value match vs portal | ≥ 95% | 25.0% | ❌ |
severity rule 'critical if project_duration_months > 18 else high' missing fact 'project_duration_months'; defaulting to 'medium'
```

* **Root cause:** The classifier/prompt chain does not always supply `project_duration_months`, and the date/value extraction heuristics are not yet tuned to the eval corpus.
* **Impact:** Users may see incorrect deadlines or contract values, undermining trust.
* **Likelihood:** High on real tenders until fixed.
* **Recommended solution:**
  1. Update extraction prompts to explicitly request `project_duration_months`, `submission_date`, `contract_value_minor`, etc.
  2. Add a post-extraction reconciliation step that cross-checks extracted values against known portal fields.
  3. Re-run `eval_ci_smoke.py` and the backtest harness until the metric meets the 95% bar.

### 4.5 Low / mitigated / retained

#### TS-P02 — Bundled risk patterns are still `confidence: unvalidated`

* **Status:** Mitigated (not release-blocking for a controlled pilot).
* **Severity:** Low / product concern.
* **Evidence:** 27 rulepack YAML files declare `confidence: unvalidated`; `backend/app/core/config.py:122` defaults `beta_unvalidated: bool = True`, so findings surface with a disclaimer.
* **Impact:** Paying workspaces see unvalidated patterns with a disclaimer; zero-findings blocker removed.
* **Fix:** QS-validate core patterns and flip `confidence` to `validated`; then set `beta_unvalidated=false`.

#### TS-R03 — Severity evaluator falls back to default when a rule references a missing fact

* **Status:** Mitigated.
* **Severity:** Low / product concern.
* **Evidence:** `backend/app/modules/risk/severity.py` raises `MissingFactError`, logs the rule and fact, and defaults. The Round 9 eval smoke no longer crashes, but `project_duration_months` is still missing.
* **Impact:** Missing classifier facts still produce a default severity rather than the rule's intended value, but the gap is visible in logs.
* **Fix:** Update classifier prompts to supply all facts declared by active severity rules; add sensible defaults in rule preconditions.

#### TS-UI-03 — Baseline endpoints emit 404/409 console noise on opportunity detail

* **Status:** Retained (cosmetic).
* **Severity:** Low.
* **Evidence:** Opportunity detail page issues calls to `/handover` and `/compare`; before a baseline exists these return `404` / `409` and appear in the browser console.
* **Impact:** Cosmetic noise; does not block the happy path.
* **Fix:** Suppress expected missing-baseline errors or return empty-state responses handled by the UI.

---

## 5. Remediation Plan

### 5.1 Immediate release blockers (before any pilot)

No new Critical findings. Prior Criticals are resolved. The remaining blockers for a **public paid launch** are:

1. **TS-P02 / TS-EV-01** — QS-validate core rulepacks and raise deadline/tender-value match to ≥95%.

For an **internal / single-customer pilot**, the remaining rulepack and eval accuracy work can be accepted with documented disclaimers.

### 5.2 Required pre-release work

| ID | Work | Tests required | Verification |
|---|---|---|---|
| TS-EV-01 | Improve deadline/value extraction and portal reconciliation | Re-run `scripts/eval_ci_smoke.py --limit 20` until match >= 95% | `eval_ci_smoke.py` scorecard |
| TS-P02 | QS-validate core rulepacks or document `beta_unvalidated` acceptance | Rulepack review + sample testing | Rulepack confidence check |

### 5.3 Short-term post-release improvements

* Improve eval corpus coverage for `project_duration_months` and portal-matched deadlines.
* Add rate limits and payload size caps to dynamic connector `poll` and `test` operations.
* Harden drawing overlay / IFC parsing against malformed inputs.
* Add real-world OCR stress tests on scanned BOQs.

### 5.4 Long-term architectural improvements

* Move document-class ACL enforcement into a middleware or dependency so it cannot be forgotten on new routes.
* Implement a centralized webhook signature registry for all external callbacks (billing, change, integrations, public_api).
* Separate connector sandbox credentials from production credentials with distinct storage/encryption.
* Add automated penetration testing and fuzzing for file uploads, dynamic connectors, and public API.

---

## 6. Residual Risks and Final Checklist

### 6.1 Accepted and deferred risks

| Risk | Disposition | Rationale |
|---|---|---|
| Rulepack content unvalidated | Accepted for pilot, deferred for public launch | Mitigated by `beta_unvalidated=true` disclaimer; requires QS validation |
| Missing `project_duration_months` / deadline match 25% | Deferred | Not a security risk; domain accuracy work in progress |
| Live CDE/ERP connectors stubs | Accepted for pilot | Real integrations require staging credentials; stubs degrade gracefully |
| Drawing intelligence is Phase 22 research-heavy | Accepted | Explicitly out of scope per build doc §0.2/§9.3 |
| Real email/SMS OTP delivery | Accepted | Requires MSG91/SES credentials; interfaces built |
| Live payment provider webhooks | Accepted for pilot | Requires Razorpay/Stripe live keys; signature verification code in place |

### 6.2 Final production-readiness checklist

| Gate | Status |
|---|---|
| Unit tests pass | Pass |
| Lint / type check pass | Pass |
| Frontend build + a11y pass | Pass |
| Postgres RLS tests pass (non-superuser) | Pass |
| Alembic up/down pass | Pass |
| Critical security blockers fixed | Pass |
| Billing amount manipulation fixed | Pass |
| Cross-tenant takeover fixed | Pass |
| Validated risk content available | Fail (still `unvalidated`) |
| Public API production-ready | Pass (TS-PUB-04 closed) |
| Dynamic connector SSRF controls | Pass (TS-INT-03 closed) |
| Integration webhook authentication | Pass (TS-INT-02 closed) |
| Document-class ACL fully enforced | Pass (TS-ACL-01 closed) |
| Governance retention executed | Pass (TS-GOV-01 closed) |
| Out-of-box sign-up works with `.env.local` | Pass |
| Postgres multi-tenant core tests pass | Pass |
| Observability + runbooks reviewed | Partial (runbooks exist; not exercised) |

### 6.3 Unverified concerns

1. Real-world OCR reliability on scanned BOQs (RapidOCR model download not exercised).
2. End-to-end browser smoke on the new Phase 22 UI tabs (Changes/Claims/Pricing/Drawings/Subcontracts).
3. Load and concurrency behavior with many concurrent BOQ runs.
4. Real-world pilot corpus accuracy against gold answers.
5. Disaster-recovery restore of Postgres + object storage.

---

## 7. Final Recommendation

**GO for controlled pilot — NOT GO for public/paid launch.**

The codebase is structurally sound and the Round 8 and Round 9 security/auth/data-integrity release blockers are closed. The validation matrix is green except for rulepack validation and eval accuracy. It is safe to proceed with a **controlled internal or single-customer pilot** provided users are informed that rulepack findings are `confidence: unvalidated` and carry a beta disclaimer.

It is **NOT GO for a public or paid production launch** until:

1. Core rulepack patterns are QS-validated (or `beta_unvalidated` is acceptable and documented), and
2. The eval deadline/tender-value match reaches the 95% bar (TS-EV-01).

Once those items close and the unverified concerns are addressed with real-world testing, the recommendation can move to **GO for public/paid launch**.
