# TS-112 — Archive / delete / restore for opportunities and documents

**Status:** todo
**Requirement:** [R-019](../../specs/requirements/R-019-record-lifecycle.md)
**Spec(s) updated:** `specs/modules/ingestion.md` (to be updated when built)
**Module(s):** `ingestion`, frontend
**Severity / Gate:** P0 (archive) · Gate 5

## What this builds

There is currently no way to clean up an opportunity or document list at
all — no archive, no delete, no restore. This task adds both a soft
"archive" (the common case) and a rarer, heavier permanent delete.

## Implementation (reference plan — not yet built)

Archive (`archived_at`) hides a record from live views, keeps all data,
and is restorable — the everyday cleanup action. Permanent delete
(`deleted_at` + real destruction of derived records and stored blobs) is a
distinct, admin-only action with a heavier confirmation. This split matters
specifically because sealed baselines (TS-041) and issued GST invoices
(TS-096) are deliberately immutable — archive lets users clean up without
touching those.

Cascade is explicit and disclosed *before* it happens: deleting a document
destroys its derived clauses/deadlines/findings, and the confirmation
dialog states exactly what will be destroyed and how many of each — never
a bare "are you sure?" Cascade rules are decided per owning module (findings
and artifacts derive from documents across module boundaries and must go
through the owning module's own capability, not a cross-module foreign key,
per CLAUDE.md §2).

Blob deletion is part of deletion: `LocalStorage` has no `delete` today —
the `Storage` protocol gains one under TS-106; until then, permanent
delete of a document with a stored blob must either be blocked or leave a
recorded orphan for later reaping. Silently leaving customer files on disk
after a "delete" is not acceptable.

A sealed baseline (TS-041) resists deletion — blocked outright or requires
an explicit, audited override (`assumption:` flagged as a product decision
needing owner sign-off).

## Files touched (planned)

- `backend/app/modules/ingestion/{models,service,router}.py`
- `frontend/app/opportunities/[id]/page.tsx` (archive/delete confirmation UI)
- depends on TS-106 for real blob deletion

## Tests (planned)

- `backend/tests/modules/ingestion/test_lifecycle.py::test_archive_restorable`,
  `test_delete_cascade_disclosed`

## Acceptance criteria (R-019, A1–A6)

- [ ] Archive hides a record from live views, retains all data, and is
      restorable within a defined window.
- [ ] A delete confirmation names exactly what will be destroyed (counts
      per derived record type), not a generic warning.
- [ ] A sealed baseline cannot be deleted without an explicit, audited
      override.

## Commit

Not yet implemented.
