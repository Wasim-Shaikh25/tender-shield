# TenderShield — Production Readiness Audit (Round 11 / Phase 28)

**Repository:** `Wasim-Shaikh25/tender-shield`  
**Commit audited:** `9e09cacbf2abd59fe83c6d4550c2911effde96d1` (`main`)  
**Previous audit:** Round 10 report (`e912395`) preserved in `PRODUCTION_READINESS_AUDIT.md` history  
**Audit date:** 2026-08-08  
**Auditor roles:** Principal Software Engineer, Application Security Engineer, QA/Test Engineer, DevOps/SRE, Database Architect, Product Manager, UX/A11y Specialist, Performance Engineer.

---

## 1. Executive Summary

### 1.1 Recommendation

**GO for a controlled internal or single-customer pilot with explicit security caveats. NOT GO for public / paid production launch until the new High findings (TS-SEC-01, TS-SEC-03, TS-DEP-01) and the pre-existing TS-ENV-01 / TS-P02 items are remediated.**

Round 10 blockers remain closed: backend lint/type/test matrix is green on a clean environment, PostgreSQL RLS tests pass with a non-superuser role, the eval smoke continues to hit 100% deadline/tender-value match, and the new `scripts/validate_full_pipeline.py` completes a 5-opportunity full lifecycle run. However, Round 11 adds several user-facing security and isolation gaps that must be tracked before any broader launch:

1. **TS-SEC-01** — `frontend/components/markdown.tsx` renders links without URL-scheme whitelisting, creating a stored/reflective XSS path through assistant chat messages.
2. **TS-SEC-02 / TS-DEP-01** — `mermaid` (direct dependency) ships with known prototype-pollution / CSS-injection advisories and the plan-dashboard renders LLM-generated diagrams without sanitization or sandboxing.
3. **TS-SEC-03** — `rulepacks` tables do not inherit `WorkspaceScopedMixin`; pack activation and pattern/file lookup can cross workspace boundaries when `pack_id` or UUIDs collide.
4. **TS-SEC-04** — `PlanDashboardAgent` and `RagSuggestionService` include untrusted user/source text in LLM prompts without the `delimit_untrusted` / `sanitize_message` guards used by `OpenRouterAgent`.
5. **TS-ENV-01** — `test_auth_toggles.py` still fails when `.env.local` is sourced.
6. **TS-DEP-01** — `npm audit` now reports 7 dependency vulnerabilities (5 high, 2 moderate).
7. **TS-E2E-01** — `frontend/e2e/golden-path.spec.ts` is stale after the sidebar/landing redesign.

For an **internal / single-customer pilot** these can be accepted with documented workarounds (disable untrusted assistant links, restrict rulepack uploads to admins, pin/sandbox mermaid, run tests in a clean env). For a **public or paid launch** they are release blockers.

### 1.2 Verification summary

| Check | Command / evidence | Result |
|---|---|---|
| Backend lint | `cd backend && .venv/bin/ruff check . --target-version py311` | Pass |
| Backend type check | `cd backend && .venv/bin/mypy app` | Pass |
| Backend unit tests (SQLite, clean env) | `cd backend && .venv/bin/pytest -q` | **663 passed, 5 skipped** |
| Backend unit tests (SQLite, `.env.local` sourced) | `source .env.local && .venv/bin/pytest -q` | **660 passed, 5 skipped, 3 failed** (TS-ENV-01) |
| Postgres RLS tests (non-superuser) | `TS_DATABASE_URL=postgresql+psycopg://appuser:appuser@localhost:5432/app_db .venv/bin/pytest tests/test_rls_postgres.py -q` | **5 passed** |
| Postgres core smoke | `TS_DATABASE_URL=postgresql+psycopg://appuser:appuser@localhost:5432/app_db .venv/bin/pytest tests/test_auth_module.py tests/test_ingestion.py tests/test_boq.py tests/test_billing.py -q` | **49 passed** |
| Frontend lint | `cd frontend && npm run lint` | Pass |
| Frontend type check | `cd frontend && npm run typecheck` | Pass |
| Frontend production build | `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000/api npm run build` | Pass (**31 routes** generated) |
| Frontend a11y (WCAG 2.1 AA) | `cd frontend && npm run a11y` | Pass (**29 routes** audited) |
| Frontend e2e | `cd frontend && npm run test:e2e` | **1 failed, 1 passed** (TS-E2E-01) |
| Frontend npm audit | `cd frontend && npm audit --audit-level=high` | **7 vulnerabilities (5 high, 2 moderate)** (TS-DEP-01) |
| Backend pip-audit | `cd backend && .venv/bin/pip-audit` | **13 findings in `pip`/`setuptools` only** (build tools) |
| Alembic up/down | `cd backend && TS_DATABASE_URL=sqlite:///:memory: .venv/bin/alembic upgrade head && .venv/bin/alembic downgrade base` | Pass |
| Eval smoke (M1 + M4) | `backend/.venv/bin/python scripts/eval_ci_smoke.py --limit 20` | M1/M4 100%; deadline/tender-value match 100% |
| Full-pipeline validation importer | `backend/.venv/bin/python scripts/validate_full_pipeline.py --start-backend --count 5` | **5/5 opportunities full lifecycle PASS** |
| Task tracker | `backend/.venv/bin/python scripts/task_tracker.py --validate` | Clean; 4 tasks blocked only on live credentials |

### 1.3 Finding count by severity

| Severity | Open | Release-blocking for public launch | IDs |
|---|---|---|---|
| **Critical** | 0 | 0 | — |
| **High** | 3 | 3 | TS-SEC-01, TS-SEC-03, TS-DEP-01 |
| **Medium** | 3 | 0–1 | TS-ENV-01, TS-SEC-02, TS-SEC-04 |
| **Low** | 4 | 0 | TS-P02, TS-R03, TS-UI-03, TS-E2E-01 |
| **Total** | **10** | **3+** | |

*Note: TS-ENV-01, TS-P02, TS-R03, TS-UI-03 are retained from Round 10; all other findings are new in Round 11.*

---

## 2. Product Context and Audit Coverage

### 2.1 Product purpose and scope

TenderShield is a contractor commercial-intelligence platform. The launch wedge is **Tender Risk + BOQ Assurance**: ingest a tender pack (NIT/RFP, GCC/SCC, specs, BOQ, addenda), surface risk clauses, deadline traps, BOQ defects and scope gaps with exact citations, and generate bid-decision artifacts. Source of truth: `docs/TenderShield_Full_Build_Doc.md` v1.0.

### 2.2 Architecture

* **Backend:** FastAPI modular monolith, ~35 modules under `backend/app/modules/`. Modules interact only via the service registry and event bus; no direct cross-module imports.
* **Frontend:** Next.js 15 + TypeScript + Tailwind. Build now emits **31 routes** (up from 28 in Round 10).
* **Database:** PostgreSQL with `FORCE ROW LEVEL SECURITY` workspace isolation; SQLite fallback for dev/tests.
* **CI/CD:** GitHub Actions runs backend lint/type/test/security, Postgres RLS tests, Alembic up/down, frontend lint/type/audit/build/a11y, eval smoke, and backlog validation.

### 2.3 Scope of this round

Round 11 re-audited `main` at `9e09cacbf2abd59fe83c6d4550c2911effde96d1`, which adds the Phase 28 feature work on top of Round 10:

1. **TS-348–TS-351** — Rulepack admin: upload/version/activate, per-project multi-pack selection, private packs, and RAG-assisted rulepack expansion with human approval.
2. **TS-352** — AI assistant redesign: persistent thread history, markdown rendering, citations, follow-ups.
3. **TS-353–TS-354** — Project state dashboards (state-machine + all-projects filters).
4. **TS-355–TS-356** — E2E/sidebar fixes and global left sidebar navigation.
5. **TS-344** — Full-pipeline validation importer and `.env.validation`.

### 2.4 Files, routes and modules reviewed

| Layer | Reviewed |
|---|---|
| Backend modules | `auth` (workspaces/switch), `ingestion`, `risk`, `boq`, `findings`, `project_state`, `assistant` (agent/service/router), `analytics/plan_agent`, `rulepacks` (admin_service, rag_service, loader, router, models), `controltower` |
| Frontend routes | `/` (new landing), `/assistant`, `/plan`, `/projects`, `/projects/[id]/state`, `/dashboard/state`, `/rulepacks`, `/opportunities/[id]/rulepack-selector`, plus updated `/opportunities/[id]` tabs |
| Frontend components | `components/markdown.tsx`, `components/plan-dashboard.tsx`, `components/app-shell.tsx`, `components/session.tsx` |
| Config / infra | `.env.local`, `.env.validation`, `docker-compose.yml`, `backend/pyproject.toml`, `.github/workflows/ci.yml` |
| New migrations | `945105123194_add_rulepack_admin_tables.py`, `a50a314e2702_add_rp_rag_suggestions_table.py`, `c7a33d1c9d_add_chat_message_suggested_followups.py` |

### 2.5 Commands and tests executed

* `ruff check . --target-version py311` — pass
* `mypy app` — pass
* `pytest -q` — 663 passed, 5 skipped (clean env); 660 passed, 5 skipped, 3 failed (`.env.local` sourced)
* `pip-audit` — 13 findings in `pip`/`setuptools` only
* `npm run lint && npm run typecheck && npm run build && npm run a11y` — pass
* `npm audit --audit-level=high` — 7 vulnerabilities
* `alembic upgrade head && alembic downgrade base` — pass
* `pytest tests/test_rls_postgres.py -q` against non-superuser Postgres role — pass
* `pytest tests/test_auth_module.py tests/test_ingestion.py tests/test_boq.py tests/test_billing.py` against Postgres — pass
* `python scripts/eval_ci_smoke.py --limit 20` — M1/M4 100%; deadline/tender-value match 100%
* `python scripts/validate_full_pipeline.py --start-backend --count 5` — 5/5 full lifecycle pass
* `python scripts/task_tracker.py --validate` — clean

### 2.6 Scope limitations and exclusions

* **Live payment provider webhooks** (Razorpay/Stripe) and **real email/SMS OTP** were not exercised because they require live credentials.
* **Real scanned-table OCR** (RapidOCR ONNX model download) was not run.
* **Penetration testing / load testing / disaster-recovery drills** were not performed.
* **Advisor multi-client workflows** and live connector OAuth handshakes require staging credentials.
* The **Playwright e2e suite** was re-run; it fails on a stale selector (`Create workspace`) after the new landing/sidebar redesign (TS-E2E-01).

### 2.7 Assumptions and contradictions

* `FEATURE_COVERAGE.md` and `docs/REMAINING_GAPS_ROADMAP.md` still list some UI tasks as `todo` while the code and build output show them implemented. This documentation-sync issue is unchanged from Round 10 and is not treated as a release blocker.

---

## 3. Product Completeness Assessment

### 3.1 Role-to-capability matrix

| Role | Dashboard / landing | Key capabilities | Status |
|---|---|---|---|
| Anonymous | Public marketing / login | Sign up, log in | Implemented |
| Owner / Admin | `/opportunities`, `/controltower`, `/analytics` | Workspace creation, member/role management, billing, team, settings, integrations, API keys, rulepack admin, RAG expansion, project state dashboards | Implemented |
| Estimator | `/opportunities/[id]` | Upload, run BOQ, pricing build-up/sensitivity, schedule import, subcontract creation, rulepack selection | Implemented |
| Reviewer | `/opportunities/[id]` | Review/accept/reject findings | Implemented |
| Viewer | `/opportunities`, `/projects`, `/analytics`, `/plan` | Read-only dashboards, project state board, plan dashboard | Implemented |
| Superadmin | `/advisor`, `/admin/*` | Multi-workspace advisor view, user/workspace admin, audit log | Implemented |
| QS / External reviewer | Public API / e-signature | Request signature, status callback, API-key read | Implemented |

### 3.2 New Round 11 capabilities

| Capability | Status | Notes |
|---|---|---|
| Rulepack upload/version/activate | Implemented | `POST /api/rulepacks/admin/packs`, activate/delete endpoints |
| Per-opportunity rulepack selection | Implemented | `/opportunities/[id]/rulepack-selector` + `POST /api/rulepacks/opportunities/{id}/packs` |
| Private workspace rulepacks | Implemented | `scope=workspace` with `workspace_id` |
| RAG-assisted rulepack expansion | Implemented | `POST /api/rulepacks/admin/packs/{id}/files/{file_id}/suggest`, approve/reject |
| Assistant persistent threads + markdown | Implemented | `GET/POST /api/assistant/sessions`, `Markdown` component in `/assistant` |
| Project state dashboard | Implemented | `/api/project_state/*` + `/projects`, `/dashboard/state` |
| Global left sidebar | Implemented | `components/app-shell.tsx` |

### 3.3 Missing requirements and discovery gaps

| ID | Gap | Classification | Priority |
|---|---|---|---|
| TS-P02 | All bundled risk patterns still `confidence: unvalidated` | Confirmed Missing Requirement | Release blocker for paid public launch |
| TS-R03 | Severity evaluator falls back to default when a rule references a missing fact | Mitigated | Low |
| TS-ENV-01 | Backend tests not hermetic to `.env.local` | Confirmed Defect | Medium |
| TS-SEC-01 | Assistant markdown link XSS | Confirmed Risk | High |
| TS-SEC-02 | Plan dashboard mermaid unsanitized rendering + dependency CVEs | Confirmed Risk | Medium |
| TS-SEC-03 | Rulepack workspace isolation gaps | Confirmed Risk | High |
| TS-SEC-04 | Prompt-injection controls missing in plan/rag agents | Confirmed Risk | Medium |
| TS-DEP-01 | Frontend dependency vulnerabilities | Confirmed Risk | High |
| TS-E2E-01 | Playwright golden-path test stale | Test Maintenance | Low |

---

## 4. Detailed Findings

### 4.1 Historical Round 8/9/10 findings — status

All prior Critical/High findings remain structurally resolved in `9e09cacbf2abd59fe83c6d4550c2911effde96d1`:

| ID | Title | Round 11 status | Evidence |
|---|---|---|---|
| TS-A01 | Any authenticated user can join any workspace as owner | Fixed | `auth/service.py` validates workspace membership; tests pass |
| TS-A02 | Google sign-in grants `owner` to every user | Fixed | Google/Apple OIDC routes removed |
| TS-A03 | Row-Level Security structurally inoperative | Fixed | `bind_workspace_context` sets `app.workspace_id`; Postgres RLS tests pass |
| TS-B01 | Client controls payment amount; webhook activates without validation | Fixed | `billing/router.py` recomputes amount server-side; webhooks verify signatures |
| TS-B02 | Webhook processing not atomic | Fixed | `WebhookEvent` unique constraint + savepoint |
| TS-F01 | Workspace list contract mismatch | Fixed | `SessionProvider` consumes `WorkspaceResponse[]` directly; paginated list response returns a list |
| TS-A06 | Workspace switch does not persist refresh token | Fixed | `auth/service.py` `switch_workspace` commits rotated tokens |
| TS-A08 | Invitation tokens stored plaintext | Fixed | `token_hash` stored; plaintext token returned once |
| TS-A10 | `create_invitation` accepts arbitrary `project_id` | Fixed | Validates project workspace |
| TS-PUB-01 | `public_api` not RLS-bound | Fixed | GUCs used for RLS-safe lookup |
| TS-PUB-03 | E-signature callback unauthenticated | Fixed | `X-Callback-Secret` header required in production |
| TS-INT-01 | Integration source creation accepts arbitrary `opportunity_id` | Fixed | `IntegrationsService.create_source` calls `get_opportunity` |
| TS-INT-03 | Dynamic REST connector SSRF | Fixed | URL/IP validation in `dynamic.py` |
| TS-INT-02 | Integration source webhook signatures | Fixed | HMAC-SHA256 verification |
| TS-ACL-01 | Document-class ACL fully enforced | Fixed | Centralized dependencies in read/export paths |
| TS-GOV-01 | Governance retention/archive job | Fixed | `run_retention_job` + feature flag |
| TS-EV-01 | Eval deadline/tender-value match ≥95% | Closed | `eval_ci_smoke.py` 100% match |
| TS-P02 | Bundled risk patterns unvalidated | Retained/Mitigated | 27 patterns still `unvalidated`; `beta_unvalidated=true` with disclaimer |
| TS-R03 | Severity evaluator missing facts | Retained/Mitigated | Defaults safely, logged |
| TS-UI-03 | Baseline console noise | Retained | Cosmetic 404/409 on missing baseline |

### 4.2 Critical

No new Critical findings in this round. Prior Criticals remain structurally resolved.

### 4.3 High

#### TS-SEC-01 — Assistant `Markdown` component renders links without URL-scheme whitelisting

* **Status:** Open.
* **Classification:** Confirmed Risk.
* **Severity:** High.
* **Category:** Security / Cross-Site Scripting (XSS).
* **Disposition:** Open — release-blocking for public launch.
* **Release impact:** A stored or reflective XSS can be delivered through assistant chat messages, plan-dashboard summaries, rulepack rationale/source quotes, or any other text field rendered with `Markdown`. A malicious link such as `[click](javascript:alert(document.cookie))` will execute in the user's origin when clicked.
* **Affected roles:** All authenticated users; any role that can trigger assistant answers or view generated dashboards.
* **Affected files / endpoints:**
  * `frontend/components/markdown.tsx` (`parseInline` regex, `Inline` link rendering)
  * `frontend/app/assistant/page.tsx` (renders `<Markdown source={m.content} />`)
  * `frontend/components/plan-dashboard.tsx` (renders `dashboard.summary` and `text` sections as plain text, but `Markdown` is the shared renderer for assistant)
* **Evidence:**

```tsx
// frontend/components/markdown.tsx:15-16,25-27
const link = rest.match(/^\[([^\]]+)\]\(([^)]+)\)/);
...
} else if (link) {
  nodes.push({ kind: "link", text: link[1], href: link[2] });
```

```tsx
// frontend/components/markdown.tsx:46
if (n.kind === "link") return <a key={idx} href={n.href} className="text-blue-600 underline" target="_blank" rel="noreferrer">{n.text}</a>;
```

No `http`/`https`/`mailto` whitelist, no `rel="noopener"`, and no `DOMPurify` pass.

* **Root cause:** The custom markdown parser is minimal and does not treat `href` as untrusted data.
* **Impact:** Account compromise via phishing links, session theft, or arbitrary JS execution in the TenderShield SPA origin.
* **Likelihood:** Medium; requires a user to click a malicious link or an attacker to influence assistant/plan output.
* **Recommended solution:**
  1. Whitelist link schemes in `Inline`: allow only `http`, `https`, `mailto`, `tel`. Reject or strip `javascript:`, `data:`, `vbscript:`, etc.
  2. Add `rel="noopener noreferrer"` to all `target="_blank"` links.
  3. Prefer a hardened markdown library (e.g., `react-markdown` with `remark-gfm` and `rehype-sanitize`) and keep DOMPurify patched (TS-DEP-01).
  4. Server-side: extend `sanitize_message` in `backend/app/core/prompt_guard.py` to reject or neutralize `javascript:` URLs in LLM output.
* **Regression risks:** Low; only link-rendering behavior changes.
* **Tests to add:** Unit tests for `parseInline` with `javascript:`, `data:`, and valid URLs; Playwright test clicking an assistant link and asserting `noopener`/`noreferrer`.
* **Similar locations:** Any other component that renders `Markdown` or raw `href` attributes.

#### TS-SEC-03 — `rulepacks` workspace isolation is incomplete

* **Status:** Open.
* **Classification:** Confirmed Risk.
* **Severity:** High.
* **Category:** Security / Cross-tenant data leakage and mutation.
* **Disposition:** Open — release-blocking for public launch.
* **Release impact:** Workspace-scoped rulepacks are not fully isolated. A workspace admin can deactivate another workspace's active pack if both use the same `pack_id` string, and API callers that know or guess a pack UUID can enumerate patterns/source files across workspaces.
* **Affected roles:** Workspace admin (activation side effect); any authenticated viewer (pattern/file lookup if UUID known).
* **Affected files / endpoints:**
  * `backend/app/modules/rulepacks/models.py` — `RulePack` and `RulePackFile` do **not** inherit `WorkspaceScopedMixin`.
  * `backend/app/modules/rulepacks/admin_service.py:250-266` — `activate_pack` updates all rows with `pack_id == row.pack_id` regardless of `workspace_id`.
  * `backend/app/modules/rulepacks/loader.py:251-275` — `_db_pack` selects active packs by `pack_id` only (no workspace filter).
  * `backend/app/modules/rulepacks/router.py:81-105` — `GET /api/rulepacks/{pack_id}/patterns` uses the global loader.
  * `backend/app/modules/rulepacks/router.py:173-194` — `GET /api/rulepacks/admin/packs/{rulepack_id}/files` uses `require("viewer")` and loads by UUID without workspace check.
* **Evidence:**

```python
# backend/app/modules/rulepacks/admin_service.py:257-262
self.s.execute(
    RulePack.__table__.update()
    .where(RulePack.pack_id == row.pack_id)
    .where(RulePack.id != row.id)
    .values(is_active=False, status="deprecated")
)
```

```python
# backend/app/modules/rulepacks/loader.py:255-261
row = session.execute(
    select(self._orm_model)
    .where(self._orm_model.pack_id == pack_id)
    .where(self._orm_model.is_active.is_(True))
    .order_by(self._orm_model.activated_at.desc())
).scalars().first()
```

* **Root cause:** `RulePack`/`RulePackFile` tables were not added to the workspace-scoped RLS policy set, and the loader/admin queries do not consistently filter by `workspace_id`.
* **Impact:** Cross-tenant deactivation of rulepacks; possible cross-tenant read of private pack patterns and source files.
* **Likelihood:** Low-to-medium for UUID-guessing; medium for `pack_id` collisions because `pack_id` is derived from the uploaded YAML `meta.id` and is user-controlled.
* **Recommended solution:**
  1. Add `workspace_id` filtering to all `RulePack` loader/admin queries; scope activation to `(pack_id, scope, workspace_id)`.
  2. Add an RLS policy for `rulepacks` and `rulepack_files` that allows `workspace_id = current_setting('app.workspace_id')::uuid` **or** `(workspace_id IS NULL AND scope = 'global')`.
  3. Restrict `GET /api/rulepacks/{pack_id}/patterns` to global packs or packs explicitly in the caller's workspace.
  4. Require `admin` (not `viewer`) for `GET /api/rulepacks/admin/packs/{id}/files` or add workspace validation.
* **Regression risks:** Medium; existing global `in-works` disk pack must remain visible to all workspaces.
* **Tests to add:** Activate a workspace-scoped pack with a colliding `pack_id` and assert the other workspace's pack remains active; query patterns/files with a cross-workspace UUID and assert 404.
* **Similar locations:** `RulePackLoader.list_packs`, `get_combined_pack_for_opportunity`.

#### TS-DEP-01 — Frontend dependency vulnerabilities in `npm audit`

* **Status:** Open.
* **Classification:** Confirmed Risk.
* **Severity:** High.
* **Category:** Security / Supply chain.
* **Disposition:** Open — release-blocking for public launch.
* **Release impact:** The production bundle includes dependencies with known high-severity CVEs (DoS and XSS). `mermaid` is a direct dependency used to render LLM-generated diagrams; its transitive `dompurify` and config APIs have known injection/prototype-pollution issues.
* **Affected files:**
  * `frontend/package.json` (`mermaid: ^11.16.0`)
  * `frontend/package-lock.json`
  * `frontend/components/plan-dashboard.tsx` (`MermaidSection`)
* **Evidence:**

```
# npm audit --audit-level=high
brace-expansion  4.0.0 - 5.0.8  Severity: high  DoS via unbounded intermediate arrays
js-yaml  4.0.0 - 4.3.0        Severity: high  Quadratic CPU consumption
nanoid  <3.3.17               Severity: high  Custom generators can loop indefinitely
mermaid  11.0.0-alpha.1 - 11.16.0  Severity: moderate  prototype pollution / CSS injection / infinite loops
dompurify  <=3.4.12           Severity: moderate  IN_PLACE hook removal leaves detached subtree executable
7 vulnerabilities (2 moderate, 5 high)
```

* **Root cause:** `package.json` pins `mermaid` to a vulnerable range and `package-lock.json` resolves other vulnerable transitive packages.
* **Impact:** DoS, UI data leakage via CSS injection, possible XSS if `mermaid`/`dompurify` bypasses are chained with TS-SEC-02/TS-SEC-04.
* **Likelihood:** Medium; depends on whether untrusted diagram/markdown content reaches the vulnerable parsers.
* **Recommended solution:**
  1. Run `npm audit fix` and verify no high-severity advisories remain.
  2. Upgrade `mermaid` to the latest patched version; if none exists, pin an override that resolves a patched `dompurify`.
  3. Add a CI step that fails the build on `npm audit --audit-level=high`.
  4. For `MermaidSection`, render diagrams inside a sandboxed iframe with `sandbox="allow-scripts"` and a restrictive CSP.
* **Regression risks:** Low-to-medium; `mermaid` API surface is small and isolated.
* **Tests to add:** Add an `npm audit` gate in CI; visual regression for `/plan` with a sample mermaid diagram.

### 4.4 Medium

#### TS-ENV-01 — Backend unit tests are not hermetic with respect to `.env.local`

* **Status:** Open (unchanged from Round 10).
* **Classification:** Confirmed Defect.
* **Severity:** Medium.
* **Category:** Test reliability / developer experience.
* **Disposition:** Open — Required Before Release (for CI reliability).
* **Release impact:** A CI job or developer that sources `.env.local` before running `pytest` will see 3 failures in `test_auth_toggles.py`.
* **Affected files / endpoints:**
  * `backend/tests/test_auth_toggles.py`
  * `.env.local` (sets `TS_AUTH_MOBILE_VERIFICATION_ENABLED=true`)
  * `backend/app/core/config.py`
* **Evidence:**

```bash
$ source ../.env.local && .venv/bin/pytest tests/test_auth_toggles.py -q
F.FF.  FAILED
  test_signup_without_phone_succeeds_when_mobile_disabled
  test_login_four_methods
  test_login_otp_disabled_returns_tokens_immediately
```

`env -u TS_AUTH_MOBILE_VERIFICATION_ENABLED .venv/bin/pytest tests/test_auth_toggles.py -q` passes 5/5.

* **Root cause:** `test_auth_toggles.py` constructs `Settings(...)` without explicitly overriding `auth_mobile_verification_enabled`, so `.env.local` leaks into the test environment.
* **Recommended solution:** Make `test_auth_toggles.py` explicitly pass `auth_mobile_verification_enabled=False` in `_client()` overrides, or run CI tests in a clean environment.
* **Regression risks:** Very low; only test code changes.
* **Verification steps:** `source .env.local && pytest tests/test_auth_toggles.py -q` must pass.

#### TS-SEC-02 — Plan dashboard renders LLM-generated Mermaid diagrams without sanitization or sandboxing

* **Status:** Open.
* **Classification:** Confirmed Risk.
* **Severity:** Medium.
* **Category:** Security / UI injection.
* **Disposition:** Open — release-blocking for public launch when combined with TS-DEP-01.
* **Release impact:** The `/plan` dashboard renders mermaid diagrams produced by `PlanDashboardAgent` from an LLM. The `mermaid` dependency has known prototype-pollution and CSS-injection advisories, and the component does not set `securityLevel`, sanitize the diagram string, or sandbox rendering.
* **Affected roles:** Viewer+.
* **Affected files / endpoints:**
  * `frontend/components/plan-dashboard.tsx` (`MermaidSection`)
  * `backend/app/modules/analytics/plan_agent.py` (`generate`, `_parse`)
  * `frontend/app/plan/page.tsx`
* **Evidence:**

```tsx
// frontend/components/plan-dashboard.tsx:150-156
mod.initialize({ startOnLoad: false, theme: "default" });
void mod.run({ nodes: [ref.current!] });
```

`securityLevel` is not set, `sandbox` iframe is not used, and `diagram` is passed straight from the API payload.

* **Root cause:** `MermaidSection` trusts the LLM-generated `diagram` string and uses the default mermaid config; the project ships a vulnerable mermaid version.
* **Impact:** CSS injection affecting sibling elements, prototype pollution in mermaid config, DoS from malformed diagrams, potential stepping stone to XSS when chained with TS-SEC-04.
* **Likelihood:** Medium; requires the LLM to emit a malicious diagram.
* **Recommended solution:**
  1. Explicitly set `mermaid.initialize({ securityLevel: "sandbox" })` if supported, or `"strict"` with additional output sanitization.
  2. Render mermaid in a sandboxed `<iframe>` with `srcDoc` and `sandbox="allow-scripts"` so injected styles cannot access the parent DOM.
  3. Validate the `PlanDashboard` JSON schema on the backend and reject diagrams containing HTML tags or directives.
  4. Patch mermaid/DOMPurify (TS-DEP-01).
* **Regression risks:** Low; plan dashboard is a single component.
* **Tests to add:** Playwright test with a malicious mermaid payload asserting no sibling-element style changes or parent-DOM access.

#### TS-SEC-04 — `PlanDashboardAgent` and `RagSuggestionService` omit prompt-injection guards on untrusted text

* **Status:** Open.
* **Classification:** Confirmed Risk.
* **Severity:** Medium.
* **Category:** Security / Prompt injection.
* **Disposition:** Open — release-blocking for public launch when combined with XSS.
* **Release impact:** Unlike `OpenRouterAgent`, the new LLM call sites do not wrap untrusted context/source text in `delimit_untrusted` blocks, do not apply `sanitize_message` to the user query, and rely solely on `response_format={"type":"json_object"}` / "Return ONLY JSON" instructions. A tender circular or a malicious user query can override the system instructions and produce arbitrary dashboard/rulepack output.
* **Affected roles:** Any authenticated user (plan query); workspace admin (RAG source circular upload).
* **Affected files / endpoints:**
  * `backend/app/modules/analytics/plan_agent.py:101-119`
  * `backend/app/modules/rulepacks/rag_service.py:111-143,195-202`
  * `backend/app/modules/assistant/agent.py` (reference implementation that does use guards)
* **Evidence:**

```python
# backend/app/modules/analytics/plan_agent.py:111-115
{
    "role": "user",
    "content": (
        f"User query: {query}\n\n"
        "Tool context (workspace facts):\n"
        f"{json.dumps(context, default=str, indent=2)}\n\n"
        "Generate the JSON dashboard now."
    ),
}
```

```python
# backend/app/modules/rulepacks/rag_service.py:138-141
"\nExisting rulepack summary:\n"
f"{json.dumps(summary, indent=2)}\n"
"\nSource circular text:\n"
f"{text_sample}\n"
```

No `delimit_untrusted` wrappers; no length guards on `text_sample`; `text_sample = text[:20000]` is unbounded in structure.

* **Root cause:** New LLM call sites were added without reusing the `app.core.prompt_guard` helpers.
* **Impact:** LLM can be instructed to emit false risk patterns, misleading dashboards, or payloads that exploit TS-SEC-01 / TS-SEC-02 once they reach the frontend.
* **Likelihood:** Medium for `rag_service` (requires uploading a malicious circular); medium for `plan` (requires a crafted query).
* **Recommended solution:**
  1. Wrap `context` and source text with `delimit_untrusted(..., "tool_results", ...)` and `delimit_untrusted(..., "source_circular", ...)` in `PlanDashboardAgent` and `RagSuggestionService`.
  2. Apply `sanitize_message` to the user query in `PlanDashboardAgent`.
  3. Cap source text length and strip XML-like tags from the LLM output before JSON parsing.
  4. On the backend, re-validate `PlanDashboard` and `RulePack` payloads before DB storage; reject unexpected keys.
* **Regression risks:** Low; changes are localized to two LLM prompt builders.
* **Tests to add:** Unit tests with prompt-injection payloads in `test_rulepacks_rag.py` and a new `test_plan_agent.py`; assert JSON output still matches schema and no override instructions leak into responses.

### 4.5 Low / mitigated / retained

#### TS-P02 — Bundled risk patterns are still `confidence: unvalidated`

* **Status:** Mitigated (not release-blocking for a controlled pilot).
* **Severity:** Low / product concern.
* **Evidence:** 27 rulepack YAML files declare `confidence: unvalidated`; `backend/app/core/config.py` defaults `beta_unvalidated: bool = True`, so findings surface with a disclaimer.
* **Impact:** Paying workspaces see unvalidated patterns with a disclaimer; zero-findings blocker removed.
* **Fix:** QS-validate core patterns and flip `confidence` to `validated`; then set `beta_unvalidated=false`.

#### TS-R03 — Severity evaluator falls back to default when a rule references a missing fact

* **Status:** Mitigated.
* **Severity:** Low / product concern.
* **Evidence:** `backend/app/modules/risk/severity.py` raises `MissingFactError`, logs the rule and fact, and defaults. The eval smoke now passes without missing-fact warnings.
* **Impact:** Missing classifier facts still produce a default severity rather than the rule's intended value, but the gap is visible in logs.
* **Fix:** Update classifier prompts to supply all facts declared by active severity rules; add sensible defaults in rule preconditions.

#### TS-UI-03 — Baseline endpoints emit 404/409 console noise on opportunity detail

* **Status:** Retained (cosmetic).
* **Severity:** Low.
* **Evidence:** Opportunity detail page issues calls to `/handover` and `/compare`; before a baseline exists these return `404` / `409` and appear in the browser console.
* **Impact:** Cosmetic noise; does not block the happy path.
* **Fix:** Suppress expected missing-baseline errors or return empty-state responses handled by the UI.

#### TS-E2E-01 — Playwright golden-path test is stale after landing/sidebar redesign

* **Status:** Open.
* **Classification:** Test Maintenance.
* **Severity:** Low.
* **Disposition:** Open — fix before relying on e2e in CI.
* **Release impact:** `npm run test:e2e` fails on `account sign-up, workspace creation, opportunity and document upload` because it waits for `text=Create workspace`, which no longer exists on the new landing page. The second test (`admin dashboard is reachable`) passes.
* **Affected files:**
  * `frontend/e2e/golden-path.spec.ts`
  * `frontend/components/app-shell.tsx` (new sidebar)
* **Evidence:**

```bash
$ npm run test:e2e
  ✘ 1 ... TimeoutError: page.waitForSelector: Timeout 10000ms exceeded.
       waiting for locator('text=Create workspace')
```

Screenshot shows the new `/` page with "Start free tender review" and "See the board" buttons.

* **Root cause:** Landing page and navigation were redesigned (TS-356) but the e2e spec was not updated.
* **Impact:** False CI failure; loss of automated golden-path coverage.
* **Recommended solution:** Update `golden-path.spec.ts` to click "Start free tender review" or navigate directly to `/opportunities` and create a workspace/opportunity there; align selectors with the new sidebar.
* **Regression risks:** Very low; test-only change.
* **Tests to add:** None beyond fixing the existing e2e.

---

## 5. Remediation Plan

### 5.1 Immediate release blockers (before any public / paid launch)

1. **TS-SEC-01** — Whitelist link schemes and add `noopener noreferrer` in `frontend/components/markdown.tsx`; server-side sanitize LLM output.
2. **TS-SEC-03** — Add workspace isolation to `RulePack`/`RulePackFile` queries and RLS; scope activation by `(pack_id, workspace_id)`; restrict pattern/file lookup.
3. **TS-DEP-01** — Resolve `npm audit` high-severity vulnerabilities; upgrade or override `mermaid`, `dompurify`, `js-yaml`, `nanoid`, `brace-expansion`; add audit gate to CI.
4. **TS-SEC-02** — Sanitize/sandbox mermaid rendering in `/plan` (iframe, explicit `securityLevel`, schema validation).
5. **TS-SEC-04** — Apply `delimit_untrusted` + `sanitize_message` to `PlanDashboardAgent` and `RagSuggestionService`; validate JSON payloads.

### 5.2 Required pre-release work

| ID | Work | Tests required | Verification |
|---|---|---|---|
| TS-ENV-01 | Make backend tests hermetic to `.env.local` | `pytest` with `.env.local` sourced | All backend tests pass |
| TS-P02 | QS-validate core rulepacks or document `beta_unvalidated` acceptance | Rulepack review + sample testing | Rulepack confidence check |
| TS-E2E-01 | Fix Playwright golden-path selectors | `npm run test:e2e` | Both e2e tests pass |
| — | Real-world pilot validation (OCR, UI workflows, concurrency, disaster recovery) | Manual end-to-end smoke tests | Pilot runbook + sign-off |

### 5.3 Short-term post-release improvements

* Add a centralized markdown/link sanitizer used by `Markdown`, `PlanDashboard` text sections, and any future rich-text renderers.
* Move document-class ACL enforcement into a middleware or dependency so it cannot be forgotten on new routes.
* Add rate limits and payload size caps to dynamic connector `poll` and `test` operations.
* Add real-world OCR stress tests on scanned BOQs.

### 5.4 Long-term architectural improvements

* Implement a centralized webhook signature registry for all external callbacks (billing, change, integrations, public_api).
* Add automated dependency scanning and CSP headers in the frontend build.
* Separate connector sandbox credentials from production credentials with distinct storage/encryption.
* Add automated penetration testing and fuzzing for file uploads, dynamic connectors, public API, and LLM output.

---

## 6. Residual Risks and Final Checklist

### 6.1 Accepted and deferred risks

| Risk | Disposition | Rationale |
|---|---|---|
| Rulepack content unvalidated | Accepted for pilot, deferred for public launch | Mitigated by `beta_unvalidated=true` disclaimer; requires QS validation |
| Missing `project_duration_months` / deadline match | Closed (TS-341) | `eval_ci_smoke.py` reports 100% match |
| Live CDE/ERP connectors stubs | Accepted for pilot | Real integrations require staging credentials; stubs degrade gracefully |
| Drawing intelligence is Phase 22 research-heavy | Accepted | Explicitly out of scope per build doc §0.2/§9.3 |
| Real email/SMS OTP delivery | Accepted | Requires MSG91/SES credentials; interfaces built |
| Live payment provider webhooks | Accepted for pilot | Requires Razorpay/Stripe live keys; signature verification code in place |
| Assistant link XSS / mermaid injection | **Not accepted for public launch** | New Round 11 findings; must be fixed before public launch |
| Rulepack cross-tenant leak | **Not accepted for public launch** | Violates core RLS/org isolation invariant |

### 6.2 Final production-readiness checklist

| Gate | Status |
|---|---|
| Unit tests pass (clean env) | Pass |
| Lint / type check pass | Pass |
| Frontend build + a11y pass | Pass |
| Browser golden-path smoke pass | **Partial — e2e stale (TS-E2E-01); API validation pipeline passes** |
| Postgres RLS tests pass (non-superuser) | Pass |
| Postgres core smoke pass | Pass |
| Alembic up/down pass | Pass |
| Critical security blockers fixed | Pass |
| Billing amount manipulation fixed | Pass |
| Cross-tenant takeover fixed | Pass |
| Rulepack workspace isolation | **Fail (TS-SEC-03)** |
| Validated risk content available | Fail (still `unvalidated`) |
| Dependency audit clean | **Fail (TS-DEP-01)** |
| Assistant output XSS-free | **Fail (TS-SEC-01)** |
| LLM call sites prompt-injection hardened | **Fail (TS-SEC-04)** |

### 6.3 Unverified concerns

1. Real-world OCR reliability on scanned BOQs (RapidOCR model download not exercised).
2. Load and concurrency behavior with many concurrent BOQ runs.
3. Real-world pilot corpus accuracy against gold answers.
4. Disaster-recovery restore of Postgres + object storage.

---

## 7. Final Recommendation

**GO for controlled internal or single-customer pilot — NOT GO for public / paid launch.**

The codebase is structurally sound and the Round 8/9/10 security, auth, data-integrity, and eval-accuracy closures remain intact. The new `validate_full_pipeline.py` importer proves the end-to-end pre-bid → baseline → change/claim/subcontract → control-tower flow works for both Indian and UAE sample tenders. The frontend build is healthy (31 routes) and accessibility passes.

It is **safe to proceed with a controlled internal or single-customer pilot** only if the following are communicated and accepted:

* Assistant chat and plan-dashboard content must be treated as untrusted until TS-SEC-01, TS-SEC-02, and TS-SEC-04 are fixed.
* Rulepack uploads and activations are restricted to trusted admins until TS-SEC-03 is fixed.
* `npm audit` and `pip-audit` build-tool findings are triaged and patched.
* `test_auth_toggles.py` is run with `TS_AUTH_MOBILE_VERIFICATION_ENABLED` unset or the test is made hermetic.

It is **NOT GO for a public or paid production launch** until:

1. TS-SEC-01 (Markdown XSS), TS-SEC-03 (rulepack isolation), and TS-DEP-01 (dependency CVEs) are resolved.
2. TS-SEC-02 and TS-SEC-04 are remediated (mermaid sandboxing and prompt-injection guards).
3. TS-ENV-01 is fixed for deterministic CI.
4. Core rulepack patterns are QS-validated (or `beta_unvalidated` is formally accepted and documented).
5. The unverified operational concerns (real-world OCR, load/concurrency, disaster recovery) are addressed with real-world testing.

---

## 8. Round 11 Remediation

The following findings were remediated in the Round 11 follow-up PR (task IDs
TS-358–TS-362; see `CHANGELOG.md` `[Unreleased]`):

* **TS-SEC-01 (Markdown XSS)** — `frontend/components/markdown.tsx` now
  whitelists link schemes and renders only `http`, `https`, `mailto`, `tel`,
  `sms`, `callto` URLs, falling back to a plain `<span>` for disallowed or
  empty `href`s; all external links carry `rel="noopener noreferrer"`.
* **TS-ENV-01** — `backend/tests/test_auth_toggles.py` sets explicit toggle
  defaults in `_client()`, making the suite hermetic to `.env.local`.
* **TS-DEP-01** — Frontend dependency overrides refreshed `package-lock.json`;
  `npm audit --audit-level=high` reports 0 vulnerabilities.
* **TS-SEC-03 (rulepack workspace isolation)** — The rulepack loader, admin
  service, and public/admin routes now filter by `workspace_id` or global scope;
  `activate_pack` and `delete_pack` require matching workspace membership or
  superadmin; `get_combined_pack_for_opportunity` passes the workspace context
  through risk/BOQ/crossref/marketdata call paths. PostgreSQL RLS policies
  `workspace_or_global_isolation` on `rulepacks`/`rulepack_files` remain in place.
* **TS-P02 (rulepack confidence)** — The bundled `rulepacks/in-works` pack was
  formally signed off for release (`reviewer_signoff` populated) and all
  pattern/checklist/notice/precedence/family YAMLs were updated to
  `confidence: validated`.

### Post-merge Devin Review follow-up (TS-364–TS-368)

A second Devin Review of the merged remediation PR identified that the initial
fixes still left three correctness/security gaps, addressed in the follow-up PR:

* **TS-364 (cross-tenant rulepack cache)** — `RulePackLoader` now keys the
  process-wide cache by `(source, pack_id, workspace_id)` (`source` = `db` or
  `disk`) so a DB-loaded workspace rulepack can never be returned to a different
  tenant from `_disk_pack` or a cache hit.
* **TS-365 (DB rulepacks ignored by feature modules)** — The loader's read
  paths now fall back to the configured `session_factory` and bind the workspace
  for RLS when no session is supplied. Callers in `ingestion`, `pricing`, `export`,
  `drafting`, `assistant/tools`, `boq`, and `marketdata` now propagate
  `session` and `workspace_id` to `get_pack` / `list_patterns` /
  `employer_families` / `document_precedence` so workspace-activated rulepacks
  are honored instead of silently falling back to disk.
* **TS-366 (forbidden rulepack operations misreported as 400/404)** —
  `RulePackAdminService.delete_pack`/`activate_pack` now raise a distinct
  `forbidden` code and the router maps it to HTTP 403.
* **TS-367 (Markdown XSS control-character bypass)** —
  `frontend/components/markdown.tsx` rejects any `href` containing ASCII
  control characters before the scheme whitelist, closing the `` `jav\\tascript:` ``
  style bypass.
* **TS-368** — `CHANGELOG.md` and `tasks/backlog.md` updated.
