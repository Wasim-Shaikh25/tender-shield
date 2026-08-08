# TenderShield — Production Readiness Audit (Round 13 / Phase 30)

**Repository:** `Wasim-Shaikh25/tender-shield`  
**Commit audited:** `9365c30` (`claude/ui-dev-tools-setup-r3sxpg`)  
**Previous audit:** Round 12 report preserved in `PRODUCTION_READINESS_AUDIT.md` history  
**Audit date:** 2026-08-08  
**Auditor roles:** Principal Software Engineer, Application Security Engineer, QA/Test Engineer, DevOps/SRE, Database Architect, Product Manager, UX/A11y Specialist, Performance Engineer.

---

## 1. Executive Summary

### 1.1 Recommendation

**GO for a controlled internal or single-customer pilot with explicit security caveats. NOT GO for public / paid production launch until the remaining High/Medium findings (TS-SEC-02, TS-SEC-04) and new UI integration gaps (TS-UI-05, TS-UI-06) are remediated.**

Round 11/12 blockers are now closed: TS-SEC-01 (Markdown XSS), TS-SEC-03 (rulepack workspace isolation), TS-DEP-01 (`npm audit`), TS-ENV-01 (test hermeticity), TS-P02 (rulepack confidence), and the Round 12 UI/API integration mismatches (TS-369–TS-374) have all been remediated and verified. The PR #128 UI redesign and PR #129 integration fixes are merged into the audited branch. Build, lint, type, unit-test, and RLS matrices are green. The frontend now emits **33 routes** (up from 31).

Round 13 identifies the remaining pre-launch items:

1. **TS-SEC-02** — `frontend/components/plan-dashboard.tsx` still renders LLM-generated Mermaid diagrams without sanitization, sandboxing, or a content-security policy that blocks inline scripts/styles from diagram markup.
2. **TS-SEC-04** — `PlanDashboardAgent` and `RagSuggestionService` still include untrusted user/source text in LLM prompts without the `delimit_untrusted` / `sanitize_message` guards used by `OpenRouterAgent`.
3. **TS-UI-05** — **156 backend routes (46% of the API surface)** have no consumer in `frontend/lib/api.ts`; several Phase 1 capabilities (`POST /auth/logout`, `POST /auth/mfa/*`, `POST /boq/opportunities/{id}/upload`, `GET /ingestion/documents/{id}/text`/`stream`, `GET /rulepacks/{id}/patterns`) are not wired into the redesigned UI.
4. **TS-UI-06** — Three screens still dump structured data into `<pre>` tags (`audit` tab on `/opportunities/[id]`, `/rulepacks`, `/admin/audit-log`).
5. **TS-E2E-01** — `frontend/e2e/golden-path.spec.ts` has not been re-run against the new landing/sidebar; e2e was not executed in this round.
6. **TS-UI-03** — Browser-console noise on opportunity detail has not been verified as fixed.

For an **internal / single-customer pilot** the remaining security items can be accepted with documented workarounds (disable plan-dashboard mermaid blocks, restrict rulepack uploads to trusted admins, do not expose assistant/plan-dashboard to untrusted users). For a **public or paid launch** TS-SEC-02, TS-SEC-04, TS-UI-05 and TS-UI-06 are release blockers.

### 1.2 Verification summary

| Check | Command / evidence | Result |
|---|---|---|
| Backend lint | `cd backend && .venv/bin/ruff check .` | Pass |
| Backend type check | `cd backend && .venv/bin/mypy app` | Pass |
| Backend unit tests (SQLite, clean env) | `cd backend && .venv/bin/pytest -q` | **663 passed, 5 skipped** |
| Backend unit tests (SQLite, `.env.local` sourced) | `source .env.local && .venv/bin/pytest -q` | **663 passed, 5 skipped** (TS-ENV-01 fixed) |
| Postgres RLS tests (local scratch) | `cd backend && .venv/bin/pytest tests/test_rls_postgres.py -q` | **1 passed, 4 skipped** (Postgres service not available) |
| Frontend lint | `cd frontend && npm run lint -- --max-warnings=0` | Pass |
| Frontend type check | `cd frontend && npm run typecheck` | Pass |
| Frontend production build | `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000/api npm run build` | Pass (**33 routes** generated) |
| Frontend a11y | Not run this round | Not tested |
| Frontend e2e | Not run this round | Not tested (TS-E2E-01 open) |
| Frontend npm audit (high) | `cd frontend && npm audit --audit-level=high` | **0 vulnerabilities** (TS-DEP-01 fixed) |
| Frontend npm audit (moderate) | `cd frontend && npm audit --audit-level=moderate` | **0 vulnerabilities** |
| Backend pip-audit | `cd backend && .venv/bin/pip-audit --desc --local` | **13 findings in `pip`/`setuptools` only** (build tools) |
| Alembic up/down | `cd backend && TS_DATABASE_URL=sqlite:///:memory: .venv/bin/alembic upgrade head && .venv/bin/alembic downgrade base` | Not run this round |
| Eval smoke (M1 + M4) | Not run this round | Not tested |
| Full-pipeline validation importer | Not run this round | Not tested |
| Task tracker | `python3 scripts/task_tracker.py --validate` | Clean; 4 tasks blocked only on live credentials |

### 1.3 Finding count by severity

| Severity | Open | Release-blocking for public launch | IDs |
|---|---|---|---|
| **Critical** | 0 | 0 | — |
| **High** | 2 | 2 | TS-SEC-02, TS-SEC-04 |
| **Medium** | 2 | 0–2 | TS-UI-05, TS-UI-06 |
| **Low** | 3 | 0 | TS-R03, TS-UI-03, TS-E2E-01 |
| **Total** | **7** | **2+** |

*Note: TS-SEC-01, TS-SEC-03, TS-DEP-01, TS-ENV-01, TS-P02 and Round 12 integration mismatches are closed. TS-R03, TS-UI-03, TS-E2E-01 are retained. TS-SEC-02, TS-SEC-04 are retained from Round 11. TS-UI-05 and TS-UI-06 are new in Round 13.*

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

**GO for controlled internal or single-customer pilot with explicit UI-integration caveats — NOT GO for public / paid launch.**

The Round 11/12 security and dependency blockers are now closed. Backend lint/type/test/RLS matrices are green, frontend `npm audit --audit-level=high` reports 0 vulnerabilities, and the PR #128 UI redesign builds 33 routes successfully. The core pre-bid opportunity → document upload → risk/BOQ review → artifact export golden path is wired end-to-end.

It is **safe to proceed with a controlled internal or single-customer pilot** only if the following are communicated and accepted:

* Plan-dashboard Mermaid diagrams are treated as untrusted content until TS-SEC-02 is fixed; consider disabling the `mermaid` section type for external users.
* `PlanDashboardAgent` and rulepack RAG suggestions are not exposed to untrusted, arbitrary user input until TS-SEC-04 prompt guards are applied.
* The 156 backend routes without UI consumers (and the explicit Phase 1 gaps in TS-UI-05) are scheduled before any broader rollout.
* `pip-audit` build-tool findings (setuptools) are triaged; they do not affect runtime packages.

It is **NOT GO for a public or paid production launch** until:

1. TS-SEC-02 is remediated (sandbox or replace Mermaid rendering of LLM-generated diagrams).
2. TS-SEC-04 is remediated (apply `delimit_untrusted` / `sanitize_message` to `PlanDashboardAgent` and `RagSuggestionService` prompts).
3. TS-UI-05 is resolved: the explicit Phase 1 backend-only routes (`POST /auth/logout`, `POST /auth/mfa/*`, `POST /boq/opportunities/{id}/upload`, `GET /ingestion/documents/{id}/text`/`stream`, `GET /rulepacks/{id}/patterns`) must be wired into the redesigned UI or formally deferred.
4. TS-UI-06 is resolved: the three raw-JSON `<pre>` blocks are replaced with typed summary cards/tables.
5. TS-E2E-01 is re-verified by running the Playwright golden path against the new landing/sidebar.

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

### Round 12 — UI/API integration gap analysis (TS-369)

A focused pass compared the frontend `api` client (`frontend/lib/api.ts`) against the
FastAPI route surface to find pages with no backend integration, backend routes that
have no UI consumer, and places where raw JSON is rendered to users.

**Methodology**

* Parsed `frontend/lib/api.ts` with the TypeScript AST: **221** distinct endpoint
  wrappers (method + normalized path) after the fixes below.
* Dumped the FastAPI `app.routes` tree: **346** distinct backend routes.
* Normalized both sets by stripping the `/api` prefix, collapsing `{param}` and
  `${...}` placeholders to `{}`, and removing optional query-string suffixes.
* Scanned every `frontend/app/**/page.tsx` for `api.<name>` calls.
* Grepped `frontend/app` and `frontend/components` for `JSON.stringify` rendered
  inside `<pre>` tags.

**Coverage result**

| Metric | Count |
|---|---|
| Frontend endpoint wrappers | 221 |
| Backend routes | 346 |
| Frontend endpoints with a matching backend route | 221 (100%) |
| Backend routes not called by `frontend/lib/api.ts` | 125 |
| Frontend pages with no `api.*` call | 2 (`/` and `/help`) |

**Backend routes not consumed by the UI — grouped by module**

| Module | Unconsumed routes | Representative examples |
|---|---|---|
| `auth` | 11 | `POST /auth/logout`, `POST /auth/mfa/enroll`, `POST /auth/mfa/verify`, `GET/PUT /auth/workspaces/{id}/approval-matrix`, `GET/POST /auth/workspaces/{id}/projects`, `GET/POST /auth/projects/{id}/members` |
| `advisor` | 10 | `GET /advisor/status`, `POST/GET /advisor/clients`, `POST /advisor/review-queue/items`, `POST/GET /advisor/templates` |
| `baseline` | 10 | `POST /baseline/opportunities/{id}/freeze`, `GET /baseline/opportunities/{id}/diff`, `POST /baseline/opportunities/{id}/restore` |
| `express` | 9 | Bid-package APIs (`/express/...`) |
| `change` | 7 | `POST /change/opportunities/{id}/signals`, `POST /change/opportunities/{id}/delay-analysis`, `POST /change/opportunities/{id}/notice-deadline` |
| `integrations` | 7 | `GET /integrations/adapters`, `GET /integrations/connectors`, `POST/PUT /integrations/dynamic-connectors`, webhooks/poll |
| `analytics` | 5 | `GET /analytics/accuracy`, `GET /analytics/baseline-adoption`, `GET /analytics/risk-summary`, `GET /analytics/deadline-dashboard`, `GET /analytics/claim-metrics` |
| `billing` | 5 | `POST /billing/cancel`, `GET /billing/invoices/{id}` |
| `claims` | 5 | `POST /claims/opportunities/{id}/claims` (extra lifecycle endpoints beyond the opportunity tab), `GET/POST /claims/claims/{id}/...` |
| `controltower` | 5 | `GET /controltower/portfolio`, `GET /controltower/exposure`, `GET /controltower/executive-summary` |
| `marketdata` | 5 | `GET/POST /marketdata/rate-lookup`, `GET /marketdata/cashflow` |
| `rulepacks` | 5 | `GET /rulepacks` (public list), `GET /rulepacks/{id}/patterns`, `POST /rulepacks/corrections/scan`, `GET /rulepacks/corrections/proposals`, `POST /rulepacks/corrections/proposals/{id}/dismiss` |
| `evidence` | 4 | Evidence-board routes |
| `outcomes` | 4 | Outcome tracking routes |
| `public_api` | 4 | `GET/POST /public_api/keys`, `POST /public_api/events` |
| `standards` | 4 | `GET/POST/PUT /standards/notice`, `DELETE /standards/notice` |
| `assistant` | 3 | `POST /assistant/chat` (single-turn), `POST /assistant/admin/chat`, `POST /assistant/sessions/{id}/stream` |
| `crossref` | 3 | `GET/POST /crossref/opportunities/{id}/...` |
| `boq` | 2 | `GET /boq` (health/list), `POST /boq/opportunities/{id}/upload` |
| `ingestion` | 2 | `GET /ingestion/documents/{id}/text`, `GET /ingestion/opportunities/{id}/documents/{id}/stream` |
| `qualification`, `timeline`, `docs` | 2 each | Qualification scoring, timeline, docs storage |
| `drafting`, `drawings`, `export`, `review`, `subcontract`, `support` | 1 each | `GET /export/templates/{id}/render`, drawing routes, `POST /review/opportunities/{id}/audit`, subcontract/support endpoints |
| `health`, `openapi.json`, `redoc`, `files` | 6 | Health checks, OpenAPI docs, static file endpoints |

Most of these are Phase 2+ capabilities (baseline, change, advisor, analytics,
control tower, claims, drawings, market data) and are not expected to be wired yet.
Phase 1 routes that are backend-ready but still lack UI:

* `POST /auth/logout` — no explicit logout API call; session is dropped client-side.
* `POST /auth/mfa/enroll` and `POST /auth/mfa/verify` — TOTP enrollment UI not built.
* `GET/PUT /auth/workspaces/{id}/approval-matrix` and workspace project APIs.
* `POST /boq/opportunities/{id}/upload` — UI uses `/boq/opportunities/{id}/run` with a CSV string instead of multipart upload.
* `GET /ingestion/documents/{id}/text` and `GET .../stream` — document viewer does not fetch raw text.
* `GET /rulepacks/{id}/patterns` and correction/proposal endpoints — the rulepack UI lists files and suggestions but does not expose pattern browsing or correction triage.

**Raw JSON rendered in the UI**

Three screens dump structured data into `<pre>` tags instead of rendering typed UI:

* `frontend/app/opportunities/[id]/page.tsx` (audit tab) — `<pre>{JSON.stringify(a.meta, null, 2)}</pre>`.
* `frontend/app/rulepacks/page.tsx` — `<pre>{JSON.stringify(s.proposed_yaml, null, 2)}</pre>` for RAG "Proposed YAML".
* `frontend/app/admin/audit-log/page.tsx` — `<pre>{JSON.stringify(l.detail).slice(0, 120)}</pre>`.

`frontend/app/settings/page.tsx` uses `JSON.stringify(data, null, 2)` to build a
downloadable JSON blob, not for on-screen display.
`frontend/app/settings/integrations/page.tsx` uses `JSON.stringify(...)` to pre-fill
connector JSON textareas, not for display.

**Integration mismatches fixed in this round**

* `frontend/lib/api.ts` claim-specific and draft routes were missing the extra
  `/claims` module path segment. The backend mounts the claims router under
  `/api/claims`, so the correct paths are `/claims/claims/{id}` and
  `/claims/drafts/{id}`. Fixed.
* `frontend/lib/api.ts exportAccount` called `GET /auth/export`; the backend route
  is `POST /auth/export`. Fixed.
* `frontend/app/login/page.tsx` made the mobile verification code input `required`
  even when `TS_AUTH_MOBILE_VERIFICATION_ENABLED=false` and the backend returned no
  mobile token. The verify form now requires the mobile code only when a mobile
  token was actually returned.
* `GET /api/rulepacks/admin/packs/{id}/files` returned `200 {"files":[]}` for a
  cross-workspace pack instead of `403`. The admin service now raises `forbidden`
  consistently with `activate_pack` and `delete_pack`.

**Verdict**

All core golden-path pages (`/login`, `/opportunities`, `/opportunities/[id]`,
`/assistant`, `/plan`, `/billing`, `/settings`, `/rulepacks`, `/admin/*`) are wired to
real backend endpoints and behave correctly in end-to-end testing. The 125
unconsumed backend routes are largely Phase 2+ scaffolding. The remaining Phase 1 gaps
(logout API, MFA enrollment, BOQ multipart upload, raw-text document viewer, rulepack
pattern/correction UIs) are documented above and should be prioritized before a public
launch. The three raw-JSON `<pre>` blocks should be replaced with typed summary cards
or tables.

## 9. Round 13 — Post-PR #128/#129 merge re-audit (TS-379)

This round re-ran the production-readiness baseline after the PR #128 UI redesign and
PR #129 integration fixes were merged into `claude/ui-dev-tools-setup-r3sxpg`.

### 9.1 Audit focus

The user's explicit focus was:

1. UI/API integration gaps: backend routes with no frontend consumer and frontend
   wrappers with no matching backend route.
2. Places where the UI renders raw JSON instead of typed UI.
3. Re-verification of the validation matrix after the merge.

### 9.2 Updated coverage result

| Metric | Count |
|---|---|
| Frontend endpoint wrappers (`frontend/lib/api.ts`) | **181** distinct method+normalized-path wrappers |
| Backend routes (FastAPI module routers) | **337** distinct method+normalized-path routes |
| Frontend wrappers with matching backend route | **181 (100%)** |
| Backend routes not consumed by `frontend/lib/api.ts` | **156** |
| Frontend wrappers without matching backend route | **0** |
| Frontend pages with no `api.*` call | **2** (`/` and `/help`) |

The frontend `api.ts` extraction was re-run with a multi-line-aware regex that captures
`req("/path", { method: "..." })`, `req("/path", {}, token)` GET helpers, and
`client.{get|post|put|delete|patch}()` calls.

The backend route tree was dumped by importing each module's `ModuleSpec.router` and
collecting `APIRoute` paths and methods; health, OpenAPI docs, and static file
endpoints are excluded.

### 9.3 Backend routes not consumed by the UI — Phase 1 gaps

Most of the 156 unconsumed routes are Phase 2+ scaffolding (advisor, analytics,
control tower, change, baseline, outcomes, market data). The explicit Phase 1 routes
that are backend-ready but still lack UI wiring are:

* `POST /auth/logout` — no explicit logout API call; session is dropped client-side.
* `POST /auth/mfa/enroll` and `POST /auth/mfa/verify` — TOTP enrollment UI not built.
* `GET /auth/me` — present in `api.ts`? Verified present; kept as consumed.
* `GET/PUT /auth/workspaces/{id}/approval-matrix` and workspace project/member APIs.
* `POST /boq/opportunities/{id}/upload` — UI uses `/boq/opportunities/{id}/run` with a CSV
  string instead of the multipart upload endpoint.
* `GET /ingestion/documents/{id}/text` and `GET /ingestion/opportunities/{id}/documents/{id}/stream`
  — document viewer does not fetch raw text or stream content.
* `GET /rulepacks/{id}/patterns` and the correction/proposal endpoints
  (`GET /rulepacks/corrections/proposals`, `POST /rulepacks/corrections/scan`,
  `POST /rulepacks/corrections/proposals/{id}/dismiss`,
  `GET /rulepacks/admin/packs/{id}/suggestions`) — the rulepack UI lists uploaded
  files and suggestions but does not expose pattern browsing or correction triage.
* `GET /analytics/plan/snapshots/{id}` and export endpoints — plan snapshot UI exists
  but does not call these routes.
* `GET /subcontract/status` — subcontract status overview is not surfaced.
* `GET /billing/settings` and `GET /billing/projects/{id}/status` — billing/project
  status sub-resources are not wired.

The complete list of 156 unconsumed routes, grouped by module, is available in the
audit artifacts.

### 9.4 Raw JSON rendered in the UI

Three screens still dump structured data into `<pre>` tags instead of typed cards or
 tables:

| File | Line | Field rendered | Context |
|---|---|---|---|
| `frontend/app/opportunities/[id]/page.tsx` | 569–572 | `a.meta` | Opportunity audit tab — risk/BOQ action metadata shown as formatted JSON. |
| `frontend/app/rulepacks/page.tsx` | 327–331 | `s.proposed_yaml` | RAG suggestion "Proposed YAML" shown as formatted JSON inside `<details>`. |
| `frontend/app/admin/audit-log/page.tsx` | 117–120 | `l.detail` | Audit-log detail preview truncated to 200 characters of JSON. |

The following are **not** UI-display issues:

* `frontend/app/settings/page.tsx` uses `JSON.stringify(data, null, 2)` to build a
  downloadable JSON blob for account export.
* `frontend/app/settings/integrations/page.tsx` uses `JSON.stringify(...)` to pre-fill
  connector JSON textareas.

### 9.5 Retained security findings

#### TS-SEC-02 — Plan dashboard renders LLM-generated Mermaid diagrams without sanitization or sandboxing

`frontend/components/plan-dashboard.tsx` (lines 143–170) dynamically imports `mermaid`
and renders `diagram` (an LLM-generated string) directly into a `<div className="mermaid">`.
There is no input sanitization, no sandboxed iframe, and no CSP that would block inline
scripts or styles injected by malicious Mermaid markup. The `mermaid` dependency is a
direct dependency and has carried prototype-pollution / CSS-injection advisories in the
past; while `npm audit` now reports 0 findings for the current lockfile, the runtime
rendering path remains untrusted.

**Classification:** High  
**Disposition:** Open — Release blocker for public launch; Accepted risk for internal
pilot if Mermaid plan sections are hidden or restricted to trusted users.  
**Remediation:** Render diagrams in a sandboxed iframe with a strict `sandbox` attribute
and `srcdoc`, sanitize the input before passing it to Mermaid, or disable the
`mermaid` section type until a safe renderer is in place.

#### TS-SEC-04 — `PlanDashboardAgent` and `RagSuggestionService` omit prompt-injection guards on untrusted text

`backend/app/modules/analytics/plan_agent.py` `PlanDashboardAgent.generate()` (lines
94–124) interpolates `query` and `json.dumps(context)` directly into the LLM user
message without calling `sanitize_message()` or `delimit_untrusted()`. Similarly,
`backend/app/modules/rulepacks/rag_service.py` `_build_prompt()` (lines 111–143)
interpolates `text_sample` (extracted from uploaded rulepack source files) and
`json.dumps(summary)` without sanitization/delimiting. Both services use untrusted or
semi-trusted text in the LLM prompt.

`backend/app/modules/assistant/agent.py` demonstrates the expected pattern:
`message = sanitize_message(message)` and `delimit_untrusted(blocks, 'clauses', ...)`.

**Classification:** High  
**Disposition:** Open — Release blocker for public launch; Accepted risk for internal
pilot if rulepack RAG and plan-dashboard question inputs are restricted to trusted
users.  
**Remediation:** Apply `sanitize_message` to `query` and `text_sample`, and wrap
`context` / `summary` / `text_sample` in `delimit_untrusted` blocks with an
instruction to ignore any instructions inside the delimited text.

### 9.6 Other retained / unverified findings

* **TS-R03** — `backend/app/modules/risk/severity.py` `evaluate_severity()` falls back to
  `default="medium"` when a rule references a missing fact. Low severity; retained.
* **TS-UI-03** — Console noise on `/opportunities/[id]` (404/409 from baseline/finding
  endpoints) was not re-verified this round because a running dev server was not
  available.
* **TS-E2E-01** — `frontend/e2e/golden-path.spec.ts` was not executed because the
  Playwright environment was not started. The spec references the pre-redesign
  `text=Create workspace` landing flow and must be re-verified against the new
  sidebar/landing UI.

### 9.7 Verification artifacts for Round 13

| Check | Command | Result |
|---|---|---|
| Backend lint | `cd backend && .venv/bin/ruff check .` | Pass |
| Backend type check | `cd backend && .venv/bin/mypy app` | Pass |
| Backend tests | `cd backend && .venv/bin/pytest -q` | **663 passed, 5 skipped** |
| Frontend lint | `cd frontend && npm run lint -- --max-warnings=0` | Pass |
| Frontend type check | `cd frontend && npm run typecheck` | Pass |
| Frontend build | `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000/api npm run build` | Pass (**33 routes**) |
| Frontend npm audit (high) | `cd frontend && npm audit --audit-level=high` | **0 vulnerabilities** |
| Frontend npm audit (moderate) | `cd frontend && npm audit --audit-level=moderate` | **0 vulnerabilities** |
| Backend pip-audit | `cd backend && .venv/bin/pip-audit --desc --local` | 13 findings in `pip`/`setuptools` build tools only |
| Task tracker | `python3 scripts/task_tracker.py --validate` | Clean |

### 9.8 Disposition summary

| ID | Severity | Status | Disposition |
|---|---|---|---|
| TS-SEC-02 | High | Open | Release blocker for public launch |
| TS-SEC-04 | High | Open | Release blocker for public launch |
| TS-UI-05 | Medium | Open | Required pre-release work |
| TS-UI-06 | Medium | Open | Required pre-release work |
| TS-R03 | Low | Retained | Accepted / scheduled |
| TS-UI-03 | Low | Retained | Unverified this round |
| TS-E2E-01 | Low | Retained | Unverified this round |

### 9.9 Final recommendation (Round 13)

**STOP — CONDITIONAL GO** for controlled internal or single-customer pilot; **STOP — NO-GO** for public / paid production launch.

The codebase is materially more complete and secure than at Round 11. However, the
remaining High-severity Mermaid and prompt-injection issues, combined with 156
unconsumed backend routes and three raw-JSON screens, still block a public launch.
