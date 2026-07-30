# Admin observability

Requirement reference: scenarios 56–66 (admin dashboard, user management, log observability).

## Purpose
Super-admin endpoints to manage users/workspaces and inspect audit logs for support
and compliance.

## Public interface

### Capabilities consumed
- `review.service_factory` — used by `/api/auth/admin/audit-log` to fetch workspace
  audit trails; degrades gracefully when unavailable.

### API routes
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/auth/admin/dashboard` | superadmin | KPI counts |
| GET | `/api/auth/admin/users/search` | superadmin | search users by email/phone/org |
| GET | `/api/auth/admin/users/{id}` | superadmin | user detail |
| POST | `/api/auth/admin/users/{id}/suspend` | superadmin | suspend user |
| POST | `/api/auth/admin/users/{id}/unsuspend` | superadmin | unsuspend user |
| DELETE | `/api/auth/admin/users/{id}` | superadmin | delete user + data |
| GET | `/api/auth/admin/workspaces/{id}` | superadmin | workspace detail |
| POST | `/api/auth/admin/workspaces/{id}/plan` | superadmin | change workspace plan |
| GET | `/api/auth/admin/audit-log` | superadmin | search audit log by workspace/action/object/actor/date |

## Behavior
- Suspending a user revokes all of their refresh tokens.
- Deleting a user reuses the workspace-scoped erasure logic from account deletion.
- Changing a workspace plan writes an audit entry.
- Audit-log search binds the requested workspace context before querying `AuditLog`
  so RLS policies remain satisfied.

## Acceptance
- Dashboard returns total users, suspended users, active workspaces, pending verifications,
  and recent signups.
- Admin can suspend, unsuspend, and delete a user.
- Admin can inspect a workspace and change its plan.
- Audit-log search returns filtered rows with action/object/actor/detail.
