# Workspace, Project, and Super-Admin Refactor — Spec

**Status:** superseded — folded into task files, see below
**Requirement refs:** Doc §3.2, §5, §11, §16, §17
**Task refs:** TS-074..TS-078

This spec's content (public interface, data owned, behavior, acceptance
criteria) has moved into the corresponding task files as part of TS-126's
requirement/task-file restructure, per the split described in
`tasks/specs/README.md`: this file's job was "what to build," which is now
part of the task file's "how," not a separate document.

- **Design + full original spec content:**
  [`tasks/specs/TS-074-workspace-refactor-spec.md`](../tasks/specs/TS-074-workspace-refactor-spec.md)
- **Data model:** [`tasks/specs/TS-075-workspace-auth-models.md`](../tasks/specs/TS-075-workspace-auth-models.md)
- **`org_id` → `workspace_id` rename:** [`tasks/specs/TS-076-rename-org-id-workspace-id.md`](../tasks/specs/TS-076-rename-org-id-workspace-id.md)
- **CRUD/invites/admin endpoints:** [`tasks/specs/TS-077-workspace-project-crud-admin.md`](../tasks/specs/TS-077-workspace-project-crud-admin.md)
- **Verification:** [`tasks/specs/TS-078-verify-tenant-refactor.md`](../tasks/specs/TS-078-verify-tenant-refactor.md)

The living, current-state description of `auth`'s workspace/project model is
`specs/modules/auth.md` — this file is kept only so old links resolve.
