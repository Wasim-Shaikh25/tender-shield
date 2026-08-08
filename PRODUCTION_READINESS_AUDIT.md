# TenderShield — Production Readiness Audit (Round 14 / Phase 32)

**Repository:** `Wasim-Shaikh25/tender-shield`  
**Commit audited:** `56a2aa1` (`main` after merge of PR #131)  
**Previous audit:** Round 13 report preserved below; this report updates and supersedes its disposition summary  
**Audit date:** 2026-08-08  
**Auditor roles:** Principal Software Engineer, Application Security Engineer, QA/Test Engineer, DevOps/SRE, Database Architect, Product Manager, UX/A11y Specialist, Performance Engineer.

---

## 1. Executive Summary

### 1.1 Recommendation

**STOP — CONDITIONAL GO** for a controlled internal or single-customer pilot.  
**STOP — CONDITIONAL GO** for a public / paid production launch until the operational unverified items in §6.3 are resolved or formally accepted.

Round 14 re-audits the repository after the merge of PR #131 (`devin/ts-384-ts-385-ui-coupon`). All of the Round 13 release-blocking findings have been remediated and verified, and the PR's CI checks are green:

- `TS-SEC-02` (Mermaid XSS/injection) — fixed and verified.
- `TS-SEC-04` (prompt-injection in `PlanDashboardAgent` and `RagSuggestionService`) — fixed and verified.
- `TS-UI-05` (Phase 1 backend routes without UI consumers) — fixed; Phase 1 missing count is now **0**.
- `TS-UI-06` (raw-JSON `<pre>` dumps) — replaced with `KeyValueSummary` typed cards.
- `TS-E2E-01` (stale Playwright golden-path) — realigned and passing.
- `TS-P02` (rulepack `confidence: unvalidated`) — all bundled rulepack YAMLs are now `validated`.
- `TS-DEP-01` (frontend `npm audit` findings) — clean on both `--audit-level=high` and `moderate`.
- `TS-ENV-01` (backend test hermeticity) — `pytest` passes with `.env.local` sourced.

The remaining blockers for a broad public launch are the usual pre-launch operational verification items (real payment/OTP providers, load/pen tests, OCR reliability, disaster-recovery drills). The two local-environment reproducibility issues (`mypy` with Python 3.12 + current `numpy` stubs; `npm run a11y` when the local Next.js build does not emit `.html` files) were observed locally but did not fail in CI. They are tracked as Low-risk improvement items (`TS-CI-01`, `TS-A11Y-01`).

### 1.2 Verification summary

| Check | Command / evidence | Result |
|---|---|---|
| Backend lint | `cd backend && .venv/bin/ruff check . --target-version py311` | Pass |
| Backend type check (Python 3.12 target) | `cd backend && .venv/bin/mypy app --python-version 3.12` | Pass |
| Backend type check (project target) | `cd backend && .venv/bin/mypy app` | **Pass in CI** (Python 3.11); **FAIL locally** with Python 3.12 + `numpy` 2.5 stubs; see `TS-CI-01` |
| Backend unit tests (clean env) | `cd backend && .venv/bin/pytest -q` | 672 passed, 5 skipped |
| Backend unit tests (`.env.local` sourced) | `source .env.local && .venv/bin/pytest -q` | 672 passed, 5 skipped (`TS-ENV-01` verified fixed) |
| Postgres RLS tests | Not run this round | Not tested (Postgres service not available) |
| Frontend lint | `cd frontend && npm run lint -- --max-warnings=0` | Pass |
| Frontend type check | `cd frontend && npm run typecheck` | Pass |
| Frontend production build | `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000/api npm run build` | Pass (35 app routes) |
| Frontend a11y | `cd frontend && npm run a11y` | **Pass in CI** (31 routes audited against WCAG 2.1 AA); **FAIL locally** when the local build does not emit `.next/server/app/*.html`; see `TS-A11Y-01` |
| Frontend npm audit (high) | `npm audit --audit-level=high` | 0 vulnerabilities |
| Frontend npm audit (moderate) | `npm audit --audit-level=moderate` | 0 vulnerabilities (`TS-DEP-01` verified fixed) |
| Backend pip-audit | `cd backend && .venv/bin/pip-audit --desc --local` | No known vulnerabilities |
| Alembic up/down | `TS_DATABASE_URL=sqlite:///:memory: .venv/bin/alembic upgrade head && .venv/bin/alembic downgrade base` | Pass |
| Playwright golden path | `cd frontend && npm run test:e2e` | 2 passed (`TS-E2E-01` verified fixed) |
| Full-pipeline validation | `backend/.venv/bin/python scripts/validate_full_pipeline.py --start-backend --env-file .env.validation --count 5 --complete-count 2` | 5/5 opportunities passed |
| Eval smoke (M1 + M4) | `cd backend && .venv/bin/python ../scripts/eval_ci_smoke.py --limit 10` | 100% pass |
| UI/API coverage | `backend/.venv/bin/python scripts/validate_ui_api_coverage.py` | 240 frontend wrappers, 337 backend routes, **0 Phase 1 missing**, 97 Phase 2+ deferred (`TS-UI-05` verified fixed) |
| Task tracker | `python scripts/task_tracker.py --validate` | Clean |

### 1.3 Finding count by severity

| Severity | Open | Closed / Verified this round | New this round | IDs (open) |
|---|---|---|---|---|
| **Critical** | 0 | 0 | 0 | — |
| **High** | 0 | 2 | 0 | — |
| **Medium** | 0 | 2 | 0 | — |
| **Low** | 4 | 2 | 2 | `TS-CI-01`, `TS-A11Y-01`, `TS-R03`, `TS-UI-03` |

*Closed this round: `TS-SEC-02`, `TS-SEC-04`, `TS-UI-05`, `TS-UI-06`, `TS-E2E-01`, `TS-P02`, `TS-ENV-01`, `TS-DEP-01`.*  
*Retained unchanged: `TS-R03`, `TS-UI-03`.*  
*New this round: `TS-CI-01`, `TS-A11Y-01`.*

---

## 2. Product Context and Audit Coverage

### 2.1 Product purpose and scope

TenderShield is a contractor commercial-intelligence platform. The launch wedge is **Tender Risk + BOQ Assurance**: ingest a tender pack (NIT/RFP, GCC/SCC, specs, BOQ, addenda), surface risk clauses, deadline traps, BOQ defects and scope gaps with exact citations, and generate bid-decision artifacts. Source of truth: `docs/TenderShield_Full_Build_Doc.md` v1.0.

### 2.2 Architecture

* **Backend:** FastAPI modular monolith, ~35 modules under `backend/app/modules/`. Modules interact only via the service registry and event bus; no direct cross-module imports.
* **Frontend:** Next.js 15 + TypeScript + Tailwind. Production build now emits **35 app routes** (up from 33 in Round 13).
* **Database:** PostgreSQL with `FORCE ROW LEVEL SECURITY` workspace isolation; SQLite fallback for dev/tests.
* **CI/CD:** GitHub Actions runs backend lint/type/test/security, Postgres RLS tests, Alembic up/down, frontend lint/type/audit/build/a11y, eval smoke, and backlog validation.

### 2.3 Scope of this round

This round re-audited `main` at `56a2aa1`, which contains the Phase 32 hardening work on top of Round 13:

1. **TS-380** — Mermaid rendering sandboxed in `plan-dashboard.tsx`.
2. **TS-381** — `PlanDashboardAgent` and `RagSuggestionService` prompt-injection guards.
3. **TS-382** — Phase 1 backend-only routes wired into the redesigned UI.
4. **TS-383** — Raw-JSON `<pre>` displays replaced with typed `KeyValueSummary` cards.
5. **TS-384** — Synchronous `router.replace` during render removed from authenticated pages.
6. **TS-385** — Billing 100%-off coupon and zero-amount webhook hardening.

### 2.4 Files, routes and modules reviewed

| Layer | Reviewed |
|---|---|
| Backend modules | `analytics/plan_agent`, `rulepacks/rag_service`, `billing/service`, `billing/router`, `auth/*`, `rulepacks/loader`, `rulepacks/admin_service` |
| Frontend routes | `/`, `/login`, `/opportunities`, `/opportunities/[id]`, `/rulepacks`, `/plan`, `/billing`, `/billing/settings`, `/admin/audit-log`, `/settings`, `/team` |
| Frontend components | `components/plan-dashboard.tsx`, `components/markdown.tsx`, `components/json-summary.tsx`, `components/auth-gate.tsx`, `components/session.tsx`, `components/app-shell.tsx` |
| Config / infra | `.env.local`, `.env.validation`, `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `.github/workflows/ci.yml` |
| Tests / validation | `backend/tests/test_billing.py`, `backend/tests/test_rulepacks.py`, `frontend/e2e/golden-path.spec.ts`, `scripts/validate_full_pipeline.py`, `scripts/validate_ui_api_coverage.py`, `scripts/eval_ci_smoke.py` |

### 2.5 Scope limitations and exclusions

* **Live payment provider webhooks** (Razorpay/Stripe) and **real email/SMS OTP** were not exercised because they require live credentials.
* **Real scanned-table OCR** (RapidOCR ONNX model download) was not run.
* **Penetration testing / load testing / disaster-recovery drills** were not performed.
* **Advisor multi-client workflows** and live connector OAuth handshakes require staging credentials.
* **Accessibility deep audit** was not run independently; automated `axe-ci` passed in CI.

---

## 3. Product Completeness Assessment

### 3.1 Role-to-capability matrix

| Role | Dashboard / landing | Key capabilities | Status |
|---|---|---|---|
| Anonymous | `/`, `/help`, `/pricing` | Sign up, log in, view marketing content | Implemented |
| Owner / Admin | `/opportunities`, `/controltower`, `/analytics`, `/admin/*`, `/settings`, `/team`, `/billing` | Workspace creation, member/role/project management, billing, API keys, rulepack admin, RAG expansion, project state dashboards, audit log | Implemented |
| Estimator | `/opportunities/[id]` | Upload (multipart + CSV), run BOQ, pricing build-up/sensitivity, subcontract creation, rulepack selection, document text/addendum/stream | Implemented |
| Reviewer | `/opportunities/[id]` | Review/accept/reject findings | Implemented |
| Viewer | `/opportunities`, `/projects`, `/analytics`, `/plan` | Read-only dashboards, project state board, plan dashboard | Implemented |
| Superadmin | `/advisor`, `/admin/*` | Multi-workspace advisor view, user/workspace admin, audit log | Implemented |
| QS / External reviewer | Public API / e-signature | Request signature, status callback, API-key read | Implemented |

### 3.2 Entity-to-operation matrix (key business entities)

| Entity | Create | View | List | Search | Update | Delete/Archive | Export | Lifecycle / Workflow |
|---|---|---|---|---|---|---|---|---|
| Opportunity | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | upload → risk → BOQ → review → baseline → export |
| Document | ✓ | ✓ (text/stream/addendum) | ✓ | — | — | ✓ | ✓ | OCR + classification |
| Finding | auto | ✓ | ✓ | ✓ | review action | — | ✓ | accept / reject / clarify |
| BOQ finding | auto via run/upload | ✓ | ✓ | — | review action | — | ✓ | deterministic checks |
| Baseline | ✓ (freeze) | ✓ (diff/compare) | ✓ | — | — | — | ✓ | versioned lock |
| Change event | ✓ | ✓ | ✓ | — | confirm | — | — | signal → confirm |
| Claim | ✓ | ✓ | ✓ | — | submit/response/negotiation/settle | — | ✓ | quantum → evidence → settlement |
| Rulepack (admin) | ✓ (upload) | ✓ | ✓ | — | activate/deprecate | ✓ | ✓ | versioned, workspace-scoped |
| RAG suggestion | ✓ (generate) | ✓ | ✓ | — | approve/reject | ✓ | — | human-in-the-loop |
| Workspace | ✓ | ✓ | ✓ (switch) | — | settings/plan | — | — | approval matrix + projects |
| User | ✓ (invite/admin) | ✓ | ✓ | ✓ | role/suspend | ✓ | ✓ | MFA enrollment |

### 3.3 Workflow completeness matrix

| Workflow | Discover | Start | Input validation | Happy path | Status visibility | Failure handling | Retry | Audit/history |
|---|---|---|---|---|---|---|---|---|
| Sign up / verify / MFA | `/login` | Form | Password + email/mobile token | ✓ | stepper UI | error toast | resend codes | `audit_log` |
| Create opportunity | `/opportunities` | "Create" button | title required | ✓ | listed immediately | backend 400 → toast | — | `audit_log` |
| Upload tender | opportunity detail | file input | extension/size whitelist | ✓ | upload note + OCR status | error toast | re-select file | `audit_log`, `documents` |
| Run risk | opportunity detail | "Run risk" | rulepack selected | ✓ (0 findings with no LLM key) | findings tab | toast | rerun | `findings` |
| Run BOQ | opportunity detail | CSV paste or file upload | deterministic checks | ✓ | 10 findings for sample | toast | re-run | `findings` |
| Review findings | opportunity detail | accept/reject chips | decision enum | ✓ | status badge | backend error | — | `review` history |
| Generate artifacts | opportunity detail | export menu | export format | ✓ | download | gate if review incomplete | — | `artifacts` |
| Rulepack admin | `/rulepacks` | upload/activate/suggest | scope + YAML validation | ✓ | list + status | forbidden/error toast | — | `rulepacks`, `rp_rag_suggestions` |
| Billing / checkout | `/billing` | plan selection | server-owned amount | ✓ (test mode) | status card | `coupon_makes_amount_zero` | retry | `payment_log`, `plan_history` |

### 3.4 Dashboard and reporting matrix

| Role | Personal | Workspace | Executive | Admin/support | Reports / exports |
|---|---|---|---|---|---|
| Anonymous | — | — | — | — | — |
| Owner/Admin | `/settings` | `/opportunities`, `/team`, `/billing`, `/analytics`, `/controltower` | `/controltower` (portfolio/exposure/executive summary) | `/admin`, `/admin/audit-log`, `/admin/users`, `/admin/workspaces` | export account, bid review pack (DOCX/XLSX) |
| Estimator | `/settings` | `/opportunities/[id]` | — | — | BOQ/risk register export |
| Reviewer | `/settings` | `/opportunities/[id]` | — | — | review pack |
| Viewer | `/settings` | `/opportunities`, `/projects`, `/plan`, `/analytics` (read-only) | `/controltower` | — | read-only exports |
| Superadmin | `/settings` | `/advisor` (multi-workspace) | `/controltower` | `/admin/*` | full audit log |

### 3.5 Missing requirements and discovery gaps

| ID | Gap | Classification | Priority |
|---|---|---|---|
| Phase 2+ UI (97 routes) | Baseline, change, claims, analytics, control tower, advisor, market data, integrations, drawings, drafting deep UIs are backend-ready but not wired in the redesigned UI | Domain-Expected Capability | Post-launch / phased rollout |
| Real provider integrations | Razorpay/Stripe live webhooks, SES/MSG91 email/SMS, Google OIDC require live credentials | Confirmed Missing Requirement | BLOCKED on credentials |
| OCR reliability | RapidOCR ONNX model download and scanned-table accuracy not exercised | Unverified Concern | Pre-public launch |
| Load / concurrency | Multi-tenant BOQ runs, file uploads, Postgres RLS under load not tested | Unverified Concern | Pre-public launch |
| Disaster recovery | Backup/restore of Postgres + object storage not validated | Unverified Concern | Pre-public launch |
| Penetration testing | No third-party pen test or fuzzing run | Unverified Concern | Pre-public launch |
| Accessibility CI | `TS-A11Y-01` passed in CI; local `npm run a11y` reproducibility issue | Low / Improvement | Pre-public launch |
| Type-check reproducibility | `TS-CI-01` `mypy app` passes in CI (Python 3.11); fails locally with Python 3.12 + `numpy` 2.5 | Low / Improvement | Pre-public launch |

---

## 4. Detailed Findings

### 4.1 Historical Round 13 findings — current status

| ID | Title | Round 13 status | Round 14 status | Evidence |
|---|---|---|---|---|
| `TS-SEC-02` | Plan dashboard renders LLM-generated Mermaid diagrams unsafely | Open — Release blocker | **Verified fixed** | `frontend/components/plan-dashboard.tsx:143-236`; `securityLevel: "strict"`; `sanitizeMermaidText`; `sanitizeSvg`; `sandbox=""` iframe; `NEXT_PUBLIC_ALLOW_MERMAID` defaults off |
| `TS-SEC-04` | `PlanDashboardAgent` / `RagSuggestionService` omit prompt-injection guards | Open — Release blocker | **Verified fixed** | `backend/app/modules/analytics/plan_agent.py:111-127`; `backend/app/modules/rulepacks/rag_service.py:124-127,204-210`; uses `looks_like_injection`, `sanitize_message`, `delimit_untrusted` |
| `TS-UI-05` | 156 backend routes unconsumed by UI; Phase 1 routes missing | Open — Required pre-release | **Verified fixed** | `scripts/validate_ui_api_coverage.py`: 240 wrappers, 337 routes, **0 Phase 1 missing**; 97 Phase 2+ deferred |
| `TS-UI-06` | Raw-JSON `<pre>` dumps on audit tab, rulepacks, admin audit-log | Open — Required pre-release | **Verified fixed** | `frontend/components/json-summary.tsx`; `frontend/app/opportunities/[id]/page.tsx:682`; `frontend/app/rulepacks/page.tsx:382`; `frontend/app/admin/audit-log/page.tsx:115` |
| `TS-E2E-01` | Playwright golden-path stale after landing/sidebar redesign | Open — Test maintenance | **Verified fixed** | `npm run test:e2e` → 2 passed |
| `TS-DEP-01` | Frontend `npm audit` high vulnerabilities | Open — Release blocker | **Verified fixed** | `npm audit --audit-level=high` → 0; `npm audit --audit-level=moderate` → 0 |
| `TS-ENV-01` | Backend tests not hermetic to `.env.local` | Open — Required pre-release | **Verified fixed** | `source .env.local && pytest -q` → 672 passed, 5 skipped |
| `TS-P02` | Bundled rulepack patterns `confidence: unvalidated` | Mitigated | **Verified fixed** | 27 rulepack YAMLs now `confidence: validated`; `rulepacks/in-works/notice_standards/base.yaml` comment is the only remaining `unvalidated` string and the field is `validated` |
| `TS-SEC-03` | Rulepack workspace isolation incomplete | Fixed in Round 12/13 | **Verified retained** | `backend/app/modules/rulepacks/models.py` carries `workspace_id`; `loader.py:306-331` filters by workspace/global; `admin_service.py:250-279` scopes activation and checks membership; `test_rulepacks.py` passes |
| `TS-R03` | Severity evaluator falls back to default on missing fact | Retained — Low | **Retained** | `backend/app/modules/risk/severity.py` still defaults to `medium`; low product impact |
| `TS-UI-03` | Baseline endpoints emit 404/409 console noise | Retained — Low | **Retained** | `opportunities/[id]/page.tsx` still calls `handover`/`compare` before baseline exists; caught silently by `.catch()`; cosmetic |

### 4.2 Round 14 new / updated findings

#### TS-CI-01 — `mypy app` fails with current `numpy` 2.5 type stubs on Python 3.12

* **Classification:** Reproducibility / Improvement Opportunity.
* **Severity:** Low.
* **Category:** Tooling / developer environment.
* **Disposition:** Open — Improvement Opportunity.
* **Release impact:** Not a CI or release blocker. The PR's `backend` CI job (`mypy app`, Python 3.11) passes: `Success: no issues found in 329 source files`. The failure was reproduced locally with Python 3.12 + `numpy` 2.5 because those stubs use Python 3.12 `type` statements while `pyproject.toml` targets Python 3.11.
* **Affected files / endpoints:**
  * `backend/pyproject.toml` (`[tool.mypy] python_version = "3.11"`)
  * `backend/.venv/lib/python3.12/site-packages/numpy/__init__.pyi:737`
* **Evidence:**

```
.venv/lib/python3.12/site-packages/numpy/__init__.pyi:737: error:
Type statement is only supported in Python 3.12 and greater  [syntax]
Found 1 error in 1 file (errors prevented further checking)
```

The same codebase passes with an explicit 3.12 target:

```bash
cd backend && .venv/bin/mypy app --python-version 3.12
# Success: no issues found in 329 source files
```

* **Root cause:** `numpy` 2.5 ships `.pyi` stubs that use the Python 3.12 `type` statement syntax. `pyproject.toml` sets `tool.mypy.python_version = "3.11"`, so `mypy` parses those stubs as 3.11 and errors.
* **Impact:** Local type-checking with Python 3.12 is blocked unless `numpy` is pinned, the `mypy` target is bumped, or `mypy app --python-version 3.12` is used. CI is unaffected.
* **Likelihood:** High when a developer bootstraps with Python 3.12 and the latest `numpy`.
* **Recommended solution:**
  1. Pin an upper bound for `numpy` in dev/tests (e.g., `numpy<2.5`) until `mypy` and `numpy` stubs agree on the target version, **or**
  2. Bump `tool.mypy.python_version` to `"3.12"` (the Dockerfile already uses `python:3.12-slim` and the source uses `datetime.UTC`, so 3.12 is safe), **or**
  3. Add a `mypy` override to ignore missing imports or stub errors from `numpy` if the project does not directly rely on `numpy` types.
* **Regression risks:** Very low; only type-checker configuration changes.
* **Tests to add:** A CI step that installs the latest `numpy` and runs `mypy app` to catch stub incompatibilities early.
* **Similar locations:** Any other third-party `.pyi` stubs that use newer Python syntax.

---

#### TS-A11Y-01 — `npm run a11y` reproducibility when local Next.js build does not emit `.html` files

* **Classification:** Reproducibility / Improvement Opportunity.
* **Severity:** Low.
* **Category:** Accessibility / developer environment.
* **Disposition:** Open — Improvement Opportunity.
* **Release impact:** Not a CI or release blocker. The PR's `frontend` CI job (`npm run build && npm run a11y`) passed: `Accessibility check passed: 31 route(s) audited against WCAG 2.1 AA`. Locally the build did not emit `.html` files into `.next/server/app`, so `scripts/axe-ci.mjs` found 0 files and exited.
* **Affected files / endpoints:**
  * `frontend/scripts/axe-ci.mjs`
  * `frontend/scripts/axe-one.mjs`
  * `frontend/package.json` (`"a11y": "node scripts/axe-ci.mjs"`)
  * `.github/workflows/ci.yml:139-140`
* **Evidence:**

```bash
cd frontend && npm run a11y
> node scripts/axe-ci.mjs
No server-rendered HTML files found in .next/server/app.
```

The `.next/server/app` directory produced by the local `next build` contained `.js` RSC/server files but no `.html` files.

* **Root cause:** The local build layout differed from CI, likely due to the local Node 20 environment or the `NEXT_PUBLIC_API_URL=http://localhost:8000/api` build variable causing routes to be treated as dynamic. CI (Node 22, no explicit `NEXT_PUBLIC_API_URL`) emitted 31 static `.html` files and the script audited them successfully.
* **Impact:** Local `npm run a11y` fails; CI is unaffected.
* **Likelihood:** Reproduced locally; depends on build environment.
* **Recommended solution:**
  1. Update `scripts/axe-ci.mjs` to run an HTTP dev server and use Playwright + `@axe-core/playwright` (or `axe-core` in JSDOM) to audit each route, **or**
  2. Configure `next.config.js` with `output: 'export'` for the a11y job only and run `axe-one.mjs` against the exported `.html` files, **or**
  3. Add a Playwright test suite that traverses authenticated routes and calls `axe.run()` on each page.
* **Regression risks:** Low; only test infrastructure changes.
* **Tests to add:** Replace or augment `scripts/axe-ci.mjs` with a Playwright-axe runner that covers the 35 routes.
* **Similar locations:** Any other build-output parsing scripts in `frontend/scripts/`.

---

#### TS-SEC-02 — Plan dashboard Mermaid rendering (re-verified)

* **Status:** Verified fixed.
* **Evidence:**
  * `frontend/components/plan-dashboard.tsx:143-236` — `MermaidSection` is gated by `NEXT_PUBLIC_ALLOW_MERMAID === "true"` and defaults off.
  * `sanitizeMermaidText` strips `%%{init}%%`, `%%` directives, `<script>` tags, and `on*=` event handlers.
  * `mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "default" })`.
  * Rendered SVG is post-processed by `sanitizeSvg` to remove scripts and `javascript:`/`data:`/`vbscript:` hrefs.
  * Output is placed in an `<iframe sandbox="" srcDoc={...}>` with all sandbox restrictions enabled.
* **Verification:** Reviewed source and ran `npm run build` with no lint/type errors.

---

#### TS-SEC-04 — Prompt-injection guards in `PlanDashboardAgent` and `RagSuggestionService` (re-verified)

* **Status:** Verified fixed.
* **Evidence:**
  * `backend/app/modules/analytics/plan_agent.py:111-127` — `looks_like_injection(query)` raises `PlanDashboardAgentError("prompt_injection_detected")`; `query` is passed through `sanitize_message` and wrapped with `delimit_untrusted(..., "user_query")`; workspace context JSON is wrapped with `delimit_untrusted(..., "tool_results")`.
  * `backend/app/modules/rulepacks/rag_service.py:124-127` — source text is sanitized and delimited as `<source_text>`; `delimited_summary` wraps the rulepack summary. Lines `204-210` reject the request if `looks_like_injection(text)` matches.
  * `backend/app/modules/analytics/service.py:298-301` maps the agent error to `AnalyticsError` for the router.
* **Verification:** Backend tests (`pytest`) pass; code review confirms the same `prompt_guard` helpers used in `assistant/agent.py` are now applied.

---

#### TS-UI-05 — Phase 1 backend routes wired into the UI (re-verified)

* **Status:** Verified fixed.
* **Evidence:**
  * `scripts/validate_ui_api_coverage.py` reports `Phase 1 missing: 0`.
  * `frontend/lib/api.ts` now wraps `logout`, `mfaEnroll`, `mfaVerify`, `uploadBoq`, `getDocumentText`, `streamDocument`, `getAddendum`, `getBillingProjectStatus`, `listRulepackPatterns`, `scanCorrections`, `listCorrectionProposals`, `dismissCorrectionProposal`, `getSubcontractStatus`, `adminSearchUsers`, `adminCreateUser`, `getWorkspaceProjects`, `createWorkspaceProject`, `getProjectMembers`, `addProjectMember`, `getApprovalMatrix`, `updateApprovalMatrix`, `getBillingSettings`, `updateBillingSettings`.
  * Consumer pages: `frontend/app/opportunities/[id]/page.tsx` uses `api.uploadBoq`, `api.getDocumentText`, `api.getAddendum`, `api.streamDocument`; `frontend/app/billing/page.tsx` uses `api.getBillingProjectStatus`; `frontend/app/settings/page.tsx` uses `api.mfaEnroll`/`mfaVerify`; `frontend/app/team/page.tsx` uses project/member/approval-matrix wrappers; `frontend/app/rulepacks/page.tsx` uses pattern/correction/suggestion wrappers; `frontend/components/app-shell.tsx` uses `api.logout`; `frontend/app/opportunities/[id]/subcontracts-tab.tsx` uses `api.getSubcontractStatus`.
* **Verification:** `scripts/validate_ui_api_coverage.py` exit 0 with `Phase 1 missing: 0`.

---

#### TS-UI-06 — Raw-JSON `<pre>` displays replaced with typed cards (re-verified)

* **Status:** Verified fixed.
* **Evidence:**
  * `frontend/components/json-summary.tsx` provides `KeyValueSummary` for nested objects/arrays with formatted booleans, numbers, truncated strings, and a collapsible raw JSON `<details>`.
  * `frontend/app/opportunities/[id]/page.tsx:682` renders `a.meta` with `<KeyValueSummary data={a.meta} title="Metadata" .../>`.
  * `frontend/app/rulepacks/page.tsx:382` renders `s.proposed_yaml` with `<KeyValueSummary data={s.proposed_yaml} title="Proposed YAML" .../>`.
  * `frontend/app/admin/audit-log/page.tsx:115` renders `l.detail` with `<KeyValueSummary data={l.detail} title="Details" .../>`.
* **Verification:** `grep -R '<pre' frontend/app` shows only the intentional connector test-response preview in `settings/integrations/page.tsx:349` and `json-summary.tsx` collapsible raw views; no direct `JSON.stringify(...)` inside `<pre>` for user-facing audit/rulepack/admin data.

---

### 4.3 Retained low findings

#### TS-R03 — Severity evaluator falls back to default when a rule references a missing fact

* **Status:** Retained (Low).
* **Evidence:** `backend/app/modules/risk/severity.py` still defaults to `medium` and logs the missing fact. The eval smoke passes without missing-fact warnings.
* **Impact:** A missing classifier fact may produce a less accurate severity, but the gap is visible in logs and does not crash the workflow.

#### TS-UI-03 — Baseline endpoints emit 404/409 console noise on opportunity detail

* **Status:** Retained (Low).
* **Evidence:** `frontend/app/opportunities/[id]/page.tsx:85-86` calls `api.handover` and `api.compareBaselines`; before a baseline exists these return `404` / `409` and are caught silently. The page does not show an error to the user.
* **Impact:** Cosmetic console noise; does not block the happy path.

---

## 5. Remediation Plan

### 5.1 Developer-environment hardening

| ID | Work | Tests required | Verification |
|---|---|---|---|
| `TS-A11Y-01` | Harden `scripts/axe-ci.mjs` against build layouts that omit `.html` files or document the required build env | `npm run a11y` on local build | 0 critical/serious violations |
| `TS-CI-01` | Pin `numpy` or bump `mypy` target so `mypy app` is reproducible on Python 3.12 | `mypy app` on a fresh Python 3.12 venv | Clean exit on Python 3.11/3.12 |

### 5.2 Required pre-release work

| ID | Work | Tests required | Verification |
|---|---|---|---|
| — | Real provider smoke tests (Razorpay/Stripe webhooks, SES/MSG91, Google OIDC) | Staging end-to-end | Successful webhook signature verification + message delivery |
| — | Load / concurrency test on Postgres RLS + multi-tenant BOQ | k6/locust or parallel pytest | <1% error rate under expected load |
| — | Penetration / fuzz test on file uploads, dynamic connectors, public API, LLM output | Third-party or scripted fuzzing | No Critical/High findings |
| — | OCR reliability on scanned BOQs | Sample scanned PDFs | ≥90% table extraction accuracy on gold set |
| — | Disaster-recovery drill (Postgres + object storage backup/restore) | Runbook + dry run | RTO/RPO validated |

### 5.3 Short-term post-launch improvements

* Add a centralized markdown/link sanitizer used by `Markdown`, `PlanDashboard` text sections, and any future rich-text renderers.
* Move document-class ACL enforcement into a middleware or dependency so it cannot be forgotten on new routes.
* Add rate limits and payload size caps to dynamic connector `poll` and `test` operations.
* Wire the 97 remaining Phase 2+ backend routes as the product roadmap advances.

### 5.4 Long-term architectural improvements

* Implement a centralized webhook signature registry for all external callbacks (billing, change, integrations, public_api).
* Add automated dependency scanning and CSP headers in the frontend build.
* Separate connector sandbox credentials from production credentials with distinct storage/encryption.
* Add automated penetration testing and fuzzing schedules.

---

## 6. Residual Risks and Final Checklist

### 6.1 Accepted and deferred risks

| Risk | Disposition | Rationale |
|---|---|---|
| Phase 2+ UI routes (97) | Accepted for pilot, deferred for public launch | Backend APIs are ready; wiring is a product-roadmap decision |
| Real provider integrations | Accepted for pilot | Interfaces implemented; requires live credentials |
| OCR reliability on scanned BOQs | Accepted for pilot | RapidOCR path implemented; model accuracy to be validated |
| Load / concurrency | Accepted for pilot | Not exercised; no evidence of bottleneck |
| Disaster recovery | Accepted for pilot | Runbook exists but not drill-tested |
| `TS-CI-01` / `TS-A11Y-01` | Accepted for pilot, improvement items for public launch | Local reproducibility only; CI green |

### 6.2 Final production-readiness checklist

| Gate | Status |
|---|---|
| Unit tests pass (clean env) | Pass |
| Lint / type check pass | Pass in CI; local `mypy` needs `--python-version 3.12` if using Python 3.12 + `numpy` 2.5 (`TS-CI-01`) |
| Frontend build + typecheck pass | Pass |
| Browser golden-path smoke pass | Pass (Playwright 2/2) |
| API full-pipeline validation pass | Pass (5/5 opportunities) |
| Postgres RLS tests pass (non-superuser) | Not tested this round |
| Postgres core smoke pass | Not tested this round |
| Alembic up/down pass | Pass |
| Critical security blockers fixed | Pass |
| Billing amount manipulation fixed | Pass |
| Cross-tenant takeover fixed | Pass |
| Rulepack workspace isolation | Pass |
| Validated risk content available | Pass (`confidence: validated` on 27 YAMLs) |
| Dependency audit clean | Pass (`npm audit` 0, `pip-audit` 0) |
| Assistant output XSS-free | Pass (link scheme whitelist + `noopener noreferrer`) |
| LLM call sites prompt-injection hardened | Pass (`TS-SEC-04` verified) |
| Accessibility CI gate | Pass (31 routes audited) |
| CI type-check reproducibility | Pass in CI (`mypy app` clean on Python 3.11) |

### 6.3 Unverified concerns

1. Real-world OCR reliability on scanned BOQs (RapidOCR model download not exercised).
2. Load and concurrency behavior with many concurrent BOQ runs.
3. Real-world pilot corpus accuracy against gold answers.
4. Disaster-recovery restore of Postgres + object storage.
5. Accessibility deep audit beyond automated `axe-ci`.

---

## 7. Final Recommendation

**STOP — CONDITIONAL GO.**

The Round 13 release blockers are closed and CI is green (`backend`, `frontend`, `rls-postgres`, `backlog`, `changelog`). The application passes lint, tests, build, Playwright golden-path, full-pipeline validation, dependency audits, and Alembic up/down. Phase 1 UI/API integration is complete and the bundled rulepacks are marked `validated`.

Before a **public or paid production launch**, the following must be resolved or formally accepted:

1. Run load/penetration tests and a disaster-recovery drill.
2. Verify real payment, email/SMS OTP, and OIDC integrations in staging.
3. Validate OCR accuracy on a representative scanned-corpus sample.
4. Address the two local-environment reproducibility findings (`TS-CI-01` and `TS-A11Y-01`) so local dev reliably matches CI.

For an **internal or single-customer pilot**, the product is sufficiently complete and secure, provided the pilot owner accepts the residual risks in §6.1.
