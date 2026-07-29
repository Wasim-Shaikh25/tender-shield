# TS-060 — Spec: `health` module

**Status:** done
**Requirement:** spec audit; Doc §11.1
**Spec(s) updated:** `specs/modules/health.md`
**Module(s):** `health`
**Severity / Gate:** P1 · Spec audit

## What this builds

A spec-audit finding: the `health` module (`GET /api/health`, listing
loaded modules per `app.main.create_app()`'s module-load report) had no
spec.

## Implementation

```python
# backend/app/modules/health/router.py
def health(request: Request) -> dict:
    """Returns the LoadReport from app.core.loader — which modules loaded,
    which failed (fail-isolated per CLAUDE.md §2/core spec B3), and each
    module's declared version."""
```

## Files touched

- `specs/modules/health.md` (new)

## Tests

None — documentation task.

## Acceptance criteria

- [x] `specs/modules/health.md` documents the `/api/health` response shape
      matching `LoadReport`.

## Commit

Predates commit-granular history (PR #10 bulk import).
