# 00 — Codebase conventions primer (read this first)

**Audience:** an AI coding agent (Cursor Composer) or a new engineer picking up any task in
`tasks/backlog.md`. Everything here is extracted from code that exists and passes CI today —
these are not proposals. Match these patterns exactly; deviations get caught by
`backend/tests/test_architecture.py`, `ruff`, `mypy`, or `scripts/task_tracker.py`.

---

## 1. The non-negotiables (`CLAUDE.md` §2 / §4)

| Rule | Enforced by | What breaks if you ignore it |
|---|---|---|
| A module imports only `app.core.*` and its own package | `tests/test_architecture.py::test_no_cross_module_imports` | Test fails, PR blocked |
| Cross-module calls go through the **service registry** or **event bus** | same test | same |
| Numbers never come from an LLM (BOQ, dates, severity, money) | code review + per-module AST tests | Product invariant — the whole premise |
| Every extracted fact carries `source_page` + `source_quote` ≤200 chars, quote-verified | `evalinvariants/checks.py` M1 | Release gate |
| Money in **minor units** (paise), integer, with explicit currency | review + `evalinvariants` | Silent financial corruption |
| Org-scoped tables carry RLS | `tests/test_rls_postgres.py` | Cross-tenant leak = company-ending |
| Webhook is the only billing truth; redirects activate nothing | `tests/test_billing.py` | Revenue fraud |
| Tender text is untrusted input (prompt injection) | `app/core/prompt_guard.py` | Injection |
| Task → Spec → Implement → Commit → Changelog | `scripts/task_tracker.py --validate`, `scripts/check_changelog.py` (CI jobs `backlog` + `changelog`) | CI blocked |

---

## 2. Module anatomy

Modules live in `backend/app/modules/<name>/` and are **auto-discovered** — `app/core/loader.py`
enumerates packages under `app.modules` (skipping `_`-prefixed ones). You do **not** register a new
module in a list. `TS_ENABLED_MODULES` (comma-separated) can narrow the set; empty means "all".

Three hard constraints from `app/core/loader.py` + `app/main.py`:

1. `module.py` must expose `module: ModuleSpec`.
2. `ModuleSpec.name` **must equal the package directory name** (loader raises otherwise).
3. The router is always mounted at `/api/{spec.name}` — so **route prefix == package name ==
   `ModuleSpec.name`**. Pick a name that works as a URL segment (this is why `pricing-intel`
   shipped as `pricing`).

### `module.py` template

```python
"""`<name>` module registration (TS-###, spec §Public interface)."""

from app.core.module import AppContext, ModuleSpec
from app.modules.<name>.router import router
from app.modules.<name>.service import <Name>Service


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    # Publish capabilities other modules may consume by string name.
    reg.provide(
        "<name>.service_factory",
        lambda session: <Name>Service(
            session,
            # Soft deps resolved lazily so a disabled module is absence, not a crash.
            findings_factory=reg.get("findings.store_factory"),
            rulepacks_loader_provider=lambda: reg.get("rulepacks.loader"),
        ),
    )
    # Subscribe to events if needed:
    # ctx.events.subscribe("opportunity.created", _on_opportunity_created)


module = ModuleSpec(
    name="<name>",              # MUST match the package directory name
    version="0.1.0",
    router=router,
    soft_deps=("findings", "rulepacks", "auth"),   # advisory only — must degrade, never crash
    setup=setup,
)
```

### The registry contract (`app/core/registry.py`)

```python
reg.provide("name", obj)        # raises if already provided (pass replace=True to override)
reg.get("name", default=None)   # <- USE THIS for soft deps; None means "module disabled"
reg.require("name")             # raises CapabilityUnavailable — only when the feature CANNOT work
reg.has("name") / reg.names()
```

**Rule of thumb:** inside a feature module always `get()` and handle `None` by degrading with a
logged warning. `require()` is for infrastructure only (e.g. `db.sessionmaker` in
`app/core/deps.py`).

### The event bus (`app/core/events.py`)

```python
ctx.events.publish("outcome.recorded", {"opportunity_id": str(oid), "result": "won"})
ctx.events.subscribe("outcome.recorded", handler)   # handler(event: str, payload: dict) -> None
```

Handlers are isolated — one raising never breaks the publisher or other subscribers. Synchronous
and in-process today; the interface is deliberately minimal so it can be Redis-backed later.

---

## 3. Router pattern

From `app/modules/pricing/router.py` (the newest, cleanest example):

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require

router = APIRouter()          # NO prefix here — main.py adds /api/{module.name}


def _service(request: Request, session: Session) -> <Name>Service:
    reg = request.app.state.ctx.registry
    return <Name>Service(session, findings_factory=reg.get("findings.store_factory"))


@router.get("/opportunities/{opportunity_id}/thing")
def get_thing(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),   # role gate; binds RLS as a side effect
):
    try:
        return _service(request, session).do(principal.workspace_id, opportunity_id)
    except <Name>Error as exc:
        raise HTTPException(409, exc.code) from exc
```

**Auth dependencies** (`app/core/deps.py`) — resolved via registry, so no module imports `auth`:

| Dependency | Effect |
|---|---|
| `get_session` | Yields a `Session` from `db.sessionmaker`; closes it after |
| `current_principal` | Authenticates, **binds RLS**, sets `request.state.principal` |
| `require("<role>")` | `current_principal` + role check → 403 `insufficient_role` |
| `require_superadmin` | 403 `superadmin_required` unless `principal.is_superadmin` |

Roles are ranked in `app/modules/auth/rbac.py` — **use these exact names**:

```python
ROLE_RANK = {"viewer": 0, "reviewer": 1, "estimator": 2, "admin": 3, "owner": 4}
```

`require("estimator")` therefore admits `estimator`, `admin` and `owner`, but **not** `reviewer`.
Note `reviewer` sits *below* `estimator`: it is the review-workbench role, so a route that gates
export approval wants `require("reviewer")`, not a higher rank. `is_superadmin` is a separate
boolean flag, not a rank — use `require_superadmin` for it.

If `auth` is disabled these return **503 `auth_unavailable`** and the app still boots — that is
intended behaviour, not a bug.

**Body-vs-query:** use `POST` with a Pydantic body for anything carrying a payload (CSV, long text).
`pricing/router.py` documents why: a GET request body is unreliable across proxies. Always bound
string sizes with `Field(..., max_length=...)`.

---

## 4. Models, tables and RLS

```python
from app.core.db import Base, WorkspaceScopedMixin

class PiLoading(Base, WorkspaceScopedMixin):
    _tablename_ = "pi_loadings"                       # note the single underscores
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)   # minor units
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")  # always explicit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- `WorkspaceScopedMixin` adds `workspace_id` **and registers the table in
  `WORKSPACE_SCOPED_TABLES`**, which the RLS migration enumerates. Use it for every tenant table.
- **Reference/shared data must NOT use it** (see `marketdata`'s `md_*` tables in
  `docs/handover/02-marketdata.md`) — those are cross-tenant by design and need a test asserting no
  tenant data is written.
- Foreign keys may reference core tables (orgs/users) but **never another module's tables** — use
  IDs + events. `tests/test_architecture.py::test_findings_opportunity_id_has_no_foreign_key`
  pins this for `findings`.
- Money: `BigInteger` minor units + a `String` currency column. Never `Float` for money.
  (`Float` is fine for a percentage, as `PiRateMatch.variance_pct` shows.)

### Table prefixes in use

`pi_*` pricing · `oc_*` outcomes (planned) · `md_*` marketdata (planned) · `ex_*` express (planned).
Keep the prefix — it is how table ownership stays legible.

---

## 5. Migrations

```bash
cd backend
TS_DATABASE_URL="sqlite:///./_scratch.db" alembic revision --autogenerate -m "add <thing>"
TS_DATABASE_URL="sqlite:///./_scratch.db" alembic upgrade head
TS_DATABASE_URL="sqlite:///./_scratch.db" alembic downgrade base    # CI runs BOTH
rm -f _scratch.db
```

Header format (`from __future__ import annotations` first, typed revision vars):

```python
revision: str = "abc123def456"
down_revision: str | None = "5617d7dc8440"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Three real gotchas, each of which has already broken CI here:**

1. **Autogenerate picks up unrelated SQLite index drift** from earlier migrations. Hand-trim your
   revision down to only your own tables and say so in the docstring — see
   `06867937ef52_add_pricing_intel_tables.py`.
2. **`alembic downgrade base` is a CI gate.** Write a real `downgrade()`; test it.
3. **Never leave two heads.** After merging branches run `alembic heads`; if there are two, fix it
   with `alembic merge <rev1> <rev2>` (a no-op merge revision) — do **not** rewrite an existing
   migration's `down_revision` once it is pushed. Precedent:
   `f0d5a28efb7f_merge_pricing_intel_and_assistant_.py`. Strip the unused `op`/`sa` imports from
   the generated merge file or `ruff` will fail it.

---

## 6. Tests

Location: `backend/tests/test_<module>.py`. Run: `pytest -q` from `backend/`.
Current baseline: **420 passed, 5 skipped**. Suite must stay green.

```python
from tests.helpers import auth_headers_and_workspace, auth_headers

def test_thing(client):
    headers, workspace_id = auth_headers_and_workspace(client, "a@example.com")
    r = client.post("/api/<module>/thing", json={...}, headers=headers)
    assert r.status_code == 200, r.text
```

`tests/helpers.py` handles the full account dance (signup → verify email + mobile → login → OTP →
create workspace → switch). Use it; do not hand-roll auth in a test.

**Cross-tenant test — write one for every new workspace-scoped module:**

```python
def test_other_workspace_cannot_read(client):
    h1, ws1 = auth_headers_and_workspace(client, "a@example.com", workspace_name="A")
    h2, _   = auth_headers_and_workspace(client, "b@example.com", workspace_name="B")
    # create resource with h1 ... then:
    assert client.get(f"/api/<module>/{resource_id}", headers=h2).status_code in (403, 404)
```

**LLM-free assertion** (copy from `tests/test_pricing.py`) — a static AST scan proving a module
imports no LLM client. Required for any module doing money or aggregate math.

**Degradation test** — boot the app with the module's soft dep disabled and assert the feature
turns off with a warning rather than 500ing.

---

## 7. Quality gates before you commit

```bash
cd backend
ruff check .            # must print "All checks passed!"
mypy app                # must print "Success: no issues found in N source files"
pytest -q               # 420 passed, 5 skipped (or more passing)
cd .. && python3 scripts/task_tracker.py --validate   # "Validation: clean ✓"
```

CI jobs (`.github/workflows/ci.yml`): `backend`, `rls-postgres`, `frontend`, `backlog`, `changelog`.

---

## 8. The workflow loop (mandatory, `CLAUDE.md` §1)

1. **Task first** — the task must exist in `tasks/backlog.md` with an ID, req ref, spec ref, status.
   IDs are sequential and never reused; the next free ID is **TS-299**
   (TS-297/298 were taken by the branch-merge renumber; TS-195–TS-296 are Phase 16–21).
2. **Spec before code** — `specs/modules/<name>.md`, template in `specs/README.md`. If the spec
   exists, update it in the same change when behaviour diverges.
3. **Implement in small increments**, tests + lint green before each commit.
4. **Commit** `<type>(<scope>): <summary>` with `Task: TS-###` in the body.
   Types: `feat|fix|docs|spec|chore|test|refactor`.
5. **Changelog every push** — `CHANGELOG.md` `[Unreleased]`, Done + Next, naming task IDs.
   The `changelog` CI job enforces this; `[skip-changelog]` in a commit message is the escape hatch.
6. **Flip the task status** in `tasks/backlog.md` in the completing commit.

---

## 9. Spec template (`specs/README.md`)

```markdown
# <Name> — Spec
**Status:** draft | agreed | implemented
**Requirement refs:** Doc §…
**Task refs:** TS-…

## Purpose
## Public interface      # capabilities published/consumed, events, API routes
## Data owned
## Behavior              # numbered B1, B2 … so tests and reviews can cite them
## Acceptance criteria   # numbered A1, A2 … these become tests
## Out of scope
## Assumptions           # anything not backed by the Doc, marked `assumption:`
```
