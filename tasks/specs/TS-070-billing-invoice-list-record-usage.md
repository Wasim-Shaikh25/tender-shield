# TS-070 — Add billing invoice list and `billing.record_usage` capability

**Status:** done
**Requirement:** spec audit; Doc §7, §15
**Spec(s) updated:** `specs/modules/billing.md`
**Module(s):** `billing`
**Severity / Gate:** P2 · Spec audit

## What this builds

A workspace-scoped invoice list endpoint, and publishes `record_usage` as a
registry capability so other modules can meter usage events without
importing `billing` directly (CLAUDE.md §2).

## Implementation

```python
# backend/app/modules/billing/service.py
def record_usage(self, workspace_id, event: str, ref_id=None, *, commit: bool = True) -> None: ...
def list_invoices(self, workspace_id) -> list[Invoice]:
    """Filters explicitly by workspace_id in the query (not relying on RLS
    alone, R-007 §A9) — defense in depth even though RLS should already
    scope this."""
```

```python
# backend/app/modules/billing/module.py
reg.provide(
    "billing.record_usage",
    lambda session, workspace_id, event, ref_id=None: BillingService(
        session
    ).record_usage(workspace_id, event, ref_id),
)
```

```python
# backend/app/modules/billing/router.py
def list_invoices(...): ...
```

## Files touched

- `backend/app/modules/billing/{service,module,router}.py`

## Tests

- `backend/tests/modules/billing/test_service.py::test_record_usage`,
  `test_list_invoices`

## Acceptance criteria

- [x] `registry.get("billing.record_usage")` lets another module record a
      usage event without importing `app.modules.billing`.
- [x] `list_invoices` returns only the caller's workspace's invoices, with
      an explicit `workspace_id` filter as defense in depth alongside RLS.

## Commit

Predates commit-granular history (PR #10 bulk import).
