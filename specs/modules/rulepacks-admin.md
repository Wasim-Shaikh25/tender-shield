# Rulepack Admin — Spec

**Status:** draft
**Requirement refs:** Doc §2, §14; `specs/modules/rulepacks.md`; user request
**Task refs:** TS-348, TS-349, TS-350, TS-351

## Purpose

Extend the filesystem-based `RulePackLoader` with a runtime rulepack store so
non-developer admins and users can upload, version, and apply rulepacks from the
TenderShield UI. A project can combine a universal pack, one or more regional
packs, and private packs scoped to a workspace or account.

## Public interface

### Capabilities published

- `rulepacks.store_factory` — `create_pack(...)`, `list_packs(...)`,
  `get_pack(pack_id, version=None)`, `delete_pack(...)`.
- `rulepacks.loader` remains the runtime loader; it first checks the DB store,
  then falls back to the on-disk `rulepacks/` directory, so boot continues to
  work when the DB is empty.

### Routes (prefix `/api/rulepacks`)

- `POST /admin/packs` (super-admin) — upload a rulepack archive.
  Body: `multipart/form-data` with `archive` (zip of `pack.yaml` + directories),
  optional `scope` (`global` | `workspace`), optional `owner_workspace_id`.
- `GET /admin/packs` (super-admin) — list all packs with version + scope.
- `GET /admin/packs/{id}/versions` (super-admin) — list versions.
- `POST /admin/packs/{id}/activate` (super-admin) — mark a version as active.
- `POST /workspaces/me/packs` (owner/manager) — upload a private pack for the
  current workspace.
- `GET /workspaces/me/packs` (viewer+) — list packs available to this workspace
  (global active + workspace private).
- `DELETE /workspaces/me/packs/{id}` (owner/manager) — delete a private pack.
- `GET /opportunities/{opportunity_id}/packs` (viewer+) — packs currently applied
  to this opportunity.
- `PUT /opportunities/{opportunity_id}/packs` (editor+) — replace the applied
  pack list with a set of pack IDs + versions. Must include at least one pack.

### Events

- `rulepack.uploaded` — emitted when a new pack version lands.
- `rulepack.activated` — emitted when a version becomes the active default.
- `opportunity.packs_changed` — emitted when an opportunity's pack list changes.

## Data owned

| Table | Purpose |
|---|---|
| `rulepack` | Pack metadata: `id`, `version`, `scope`, `owner_workspace_id` (nullable), `is_active`, `uploaded_by`, `status` (`draft` \| `active` \| `deprecated`), `created_at`. |
| `rulepack_file` | File blobs belonging to a pack (`path`, `blob_storage_key`, `mime_type`, `checksum`). |
| `opportunity_rulepack` | Many-to-many link: `opportunity_id`, `rulepack_id`, `applied_at`, `applied_by`. |

The on-disk `rulepacks/` directory remains the built-in, immutable reference set.

## Behavior

- **B1 (upload validation):** every uploaded archive is extracted to a temp dir and
  run through `RulePackLoader` + `packsdk.validate()` before any DB write. A pack
  with load errors is rejected with `422 invalid_rulepack` and a detail list.
- **B2 (id conflict resolution):** if `pack.id` from `pack.yaml` already exists in
  the DB and the upload is not explicitly a new version, it is treated as a new
  version of the same pack (`version` auto-increment `major.minor`). If the
  directory name differs from `pack.id`, the upload is rejected.
- **B3 (scope):**
  - `global` packs are visible to all workspaces but mutable only by super-admins.
  - `workspace` packs are visible only inside `owner_workspace_id`.
- **B4 (private user packs):** a workspace-scoped pack uploaded by an owner is
  private to that workspace; it is never returned to other workspaces, even when
  querying by `pack_id`.
- **B5 (activation):** only one version per `pack_id` is active at a time.
  Inactive versions remain readable for projects that already reference them.
- **B6 (fallback to disk):** the loader first looks up the DB by `pack_id`; if
  absent, it loads from `rulepacks/<pack_id>/`. Disk packs are immutable and
  always treated as `active`.
- **B7 (per-project multi-pack):** an opportunity can reference multiple packs.
  The loader merges them deterministically in the order they are declared:
  patterns and checklists with the same `id` are overwritten by later packs;
  notice standards are merged by `key` as in `notice_standard()`; document
  precedence uses the last pack's default unless an earlier pack has an
  employer-family override.
- **B8 (required vs optional):** a project must have at least one active pack.
  On creation, the default set is `TS_DEFAULT_RULEPACKS` env (comma-separated,
  default `in-works`).
- **B9 (source documents):** PDF/Word/image files in the archive are stored as
  `rulepack_file` blobs and listed as `references` in the pack metadata; they are
  not parsed into findings, only exposed for download/review.
- **B10 (RAG suggestion only):** a separate job (`TS_RAG_RULEPACK_ENABLED`) may
  scan uploaded circulars/rulebooks and *suggest* new YAML files; it never edits
  an active pack directly. Suggestions live in `rulepack_correction_proposals`
  (reuse existing correction flow) and require human approval before they become
  a draft version.
- **B11 (geography):** regional packs are uploaded exactly like any other pack
  and applied per project. There is no hard-coded geography list; the pack's
  `jurisdiction` field in `pack.yaml` drives matching and UI labels.
- **B12 (rollback):** an opportunity's applied pack list is versioned in
  `opportunity_rulepack` history; a previous list can be restored.

## Acceptance criteria

- A1: a malformed zip without a valid `pack.yaml` returns `422 invalid_rulepack`.
- A2: uploading `in-works` with the same `pack.id` creates a new version and does
  not overwrite the on-disk `in-works` pack.
- A3: a workspace-private pack is invisible to another workspace's `/workspaces/me/packs`.
- A4: an opportunity can be linked to `in-works` + `ae-works`; BOQ/risk run
  sees patterns from both in declared order.
- A5: deleting a private pack does not break opportunities that referenced it if a
  newer active version exists; otherwise `opportunity.packs_changed` logs a warning.
- A6: the loader returns the DB pack for `in-works` if an active version exists,
  else the disk pack.
- A7: a source PDF in the archive is downloadable at
  `/api/rulepacks/{id}/files/{path}` with workspace/org isolation.
- A8: super-admin can list and deprecate global packs.
- A9: RAG-suggested YAML files are stored as draft-only and never auto-activate.
- A10: changing an opportunity's pack list re-runs ingestion/risk/BOQ when the
  user confirms, or marks the opportunity as `stale` until rerun.

## Out of scope

- Public marketplace / billing for third-party packs (Phase 3).
- Auto-approval of RAG-generated rule changes (human-in-the-loop only).
- Real-time collaborative pack editing.
- Enforcement of `validated`/`unvalidated` gating for uploaded packs (keep existing
  `TS_BETA_UNVALIDATED` behavior).

## Assumptions

- Pack archives are the same file layout as `rulepacks/<pack-id>/`.
- Large scanned PDFs/images may be stored in object storage when
  `TS_STORAGE_TYPE=s3`; SQLite dev mode keeps them as files referenced by
  `blob_storage_key`.
- Existing `RulePackLoader` cache is invalidated on `rulepack.activated` and
  `opportunity.packs_changed` events.
