# TS-013 — DB foundation: Base/mixins, RLS helpers, session factory, Alembic scaffold

**Status:** done
**Requirement:** Doc §3.2
**Spec(s) updated:** `specs/modules/core.md`
**Module(s):** `core`
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

The shared DB plumbing every module's own tables sit on: a declarative
`Base`, `WorkspaceScopedMixin`/`TimestampMixin`, the RLS statement generators
consumed by TS-012's binding, a session factory published as a registry
capability, and an Alembic scaffold that discovers models from whichever
modules are enabled (CLAUDE.md §2: each module owns its migrations).

## Implementation

```python
# backend/app/core/db.py
class Base(DeclarativeBase): ...

class WorkspaceScopedMixin:
    @declared_attr
    def __tablename__(cls) -> str: ...   # noqa: N805

class TimestampMixin: ...

def rls_statements(table: str, *, id_column: str = "workspace_id") -> list[str]:
    """ENABLE ROW LEVEL SECURITY + FORCE + a policy comparing id_column to
    current_setting('app.workspace_id')::uuid — the standard shape every
    module's migration calls for its own tables."""

def make_engine(settings: Settings) -> Engine: ...
def make_session_factory(engine: Engine) -> sessionmaker[Session]: ...
```

Session factory is published to the registry (`db.session_factory`) rather
than imported directly, so modules request a session without a hard import
on `app.core.db` internals beyond the published capability.

## Files touched

- `backend/app/core/db.py`
- `backend/migrations/env.py` (pluggable model discovery across enabled
  modules)
- `backend/alembic.ini`

## Tests

- `backend/tests/test_core_db.py`

## Acceptance criteria

- [x] `rls_statements()` produces `ENABLE`/`FORCE ROW LEVEL SECURITY` +
      policy DDL for a given table.
- [x] Alembic discovers models only from modules enabled via
      `TS_ENABLED_MODULES`.
- [x] SQLite continues to work for fast unit tests (RLS is a documented
      no-op there; real isolation is proven separately against Postgres).

## Commit

Predates commit-granular history (PR #10 bulk import).
