# R-019 — Record lifecycle: archive, delete, restore

**Status:** draft
**Severity:** P0 for archive — every create path in the product is one-way
**Requirement refs:** Doc §11.4; product overview §Product invariants
**Task refs:** TS-112
**Gap refs:** `docs/PRODUCT_DISCOVERY_GAPS.md` §G-03
**Specs to update:** `specs/modules/ingestion.md`, `specs/frontend.md`,
`specs/data-model.md`

## Purpose

The application has exactly **two `DELETE` routes in total**, both on `standards`:

```
$ grep -rn '@router.delete' backend/app/modules/*/router.py
standards/router.py:75:  @router.delete("/notice")
standards/router.py:112: @router.delete("/commercial/{key}")
```

Nothing can delete or archive an opportunity, document, finding, artifact,
baseline, project, member or invitation. A test upload, a duplicate, or a
wrong-file mistake is permanent.

The confidentiality case is the sharper one: when the wrong client's pack is
uploaded into the wrong workspace — routine in the P3 QS-consultancy persona,
who works across several clients — there is currently **no way to withdraw it**.

## Target

### B.1 Archive is the default; permanent delete is separate and rarer

Soft-delete (`archived_at`) hides a record from live views, keeps all data, and
is restorable. Permanent delete (`deleted_at` + real destruction of derived
records and stored blobs) is a distinct, admin-only action with a heavier
confirmation.

This split matters for a records-oriented product: sealed baselines and issued
GST invoices are deliberately immutable, and archive gives users the cleanup
they actually want without touching them.

### B.2 Cascade is explicit and disclosed before it happens

Deleting a document destroys its derived clauses, deadlines and findings.
The confirmation dialog states exactly what will be destroyed and how many of
each — never "are you sure?" alone.

Cascade rules are decided per module, since findings and artifacts derive from
documents across module boundaries and must go through the owning module's
capability rather than a cross-module foreign key (CLAUDE.md §2).

### B.3 Blob deletion is part of deletion

`LocalStorage` has no `delete`. The `Storage` protocol gains one under
R-016/TS-106; until then, permanent delete of a document with a stored blob must
either be blocked or must leave a recorded orphan for later reaping — silently
leaving customer files on disk after a "delete" is not acceptable.

### B.4 Sealed baselines resist deletion

A baseline is a hash-sealed immutable handover record whose value is precisely
that it cannot be altered. Deleting one is either blocked outright or requires an
explicit, audited override. **Product decision — see Questions.**

## Behavior

- **B1** Archive hides from live views, retains data, and is restorable within a
  defined window.
- **B2** Permanent delete removes derived records and stored blobs.
- **B3** The confirmation states exactly what will be destroyed.
- **B4** Both actions are audited (R-021).
- **B5** RLS applies — one workspace can never archive or delete another's record,
  verified against real PostgreSQL.
- **B6** Archived records are reachable behind an explicit filter.

## Acceptance criteria

- **A1** An archived opportunity disappears from the board and the deadline wall,
  and is restorable to exactly its prior state.
- **A2** Permanently deleting a document removes its clauses, deadlines, findings
  and its stored blob.
- **A3** The confirmation names the counts of each derived record that will go.
- **A4** Archive, restore and delete each write an audit row naming the actor.
- **A5** A cross-workspace delete attempt fails under real Postgres RLS.
- **A6** A `viewer` cannot archive or delete (`403`); permanent delete requires
  `admin`.

## Out of scope

- Workspace-level and account-level deletion — that is a data-subject-rights
  concern with statutory retention interactions, specified in R-021.
- Bulk delete/archive across many records.
- Automatic retention-based expiry.

## Questions for the product owner

1. **Should customers be able to permanently delete at all**, or should permanent
   deletion be support-mediated? Archive-only is safer for a product carrying
   statutory invoices and sealed handover records.
2. **What is the restore window** before an archived record is purged — or is
   archive indefinite?
3. **Do sealed baselines resist deletion entirely?** Their entire value is
   immutability.

## Assumptions

- `assumption:` archive is indefinite (no automatic purge) until a retention
  policy is decided, because silently destroying customer data on a timer we
  never told them about is worse than clutter.
