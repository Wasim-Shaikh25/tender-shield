# Support tickets

Requirement reference: scenarios 56–66 (account/admin/payment/tickets/analysis/observability).

## Purpose
Workspace users can raise support tickets with attachments; super-admins can search,
read, reply, and change ticket status across workspaces.

## Public interface

### Capabilities published
- `support.service` — not published; consumed internally by this module's router.

### Events consumed/emitted
- Emits `support.ticket_created`, `support.ticket_replied`, `support.ticket_status_changed`,
  `support.attachment_uploaded` via `app.core.audit.log`.

### API routes
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/support/tickets` | workspace member | create ticket |
| GET | `/api/support/tickets` | workspace member | list my workspace's tickets |
| GET | `/api/support/tickets/{id}` | workspace member | ticket + replies |
| POST | `/api/support/tickets/{id}/replies` | workspace member | reply |
| POST | `/api/support/tickets/{id}/attachments` | workspace member | attach file |
| GET | `/api/support/admin/tickets` | superadmin | list tickets in workspace |
| GET | `/api/support/admin/tickets/{id}` | superadmin | ticket + replies |
| POST | `/api/support/admin/tickets/{id}/status` | superadmin | update status |

## Data owned
- `support_tickets` — workspace-scoped.
- `support_ticket_replies` — workspace-scoped.
- `support_attachments` — workspace-scoped; file body stored in configured storage backend.

## Behavior
- A ticket can only be created when a workspace is selected (sentinel workspace is rejected).
- Attachments are validated against `ALLOWED_UPLOAD_EXTENSIONS` and sanitized by
  `app.core.storage.sanitize_filename`.
- Replies are rejected once the ticket is `closed`.
- Status values: `open`, `in_progress`, `resolved`, `closed`.

## Acceptance
- User can create a ticket and view its replies.
- Admin can change status and filter by category/status.
- File upload returns a storage key and is persisted.
