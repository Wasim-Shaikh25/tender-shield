# Advisor Edition — Spec

**Status:** draft
**Requirement refs:** Research Doc §8.3, §10.1
**Task refs:** TS-290, TS-291

## Purpose

Support independent advisors (quantity surveyors, claims consultants) who manage
multiple client workspaces from a single TenderShield account. Provides
multi-client links, a shared review queue, per-client usage billing records, and
white-label report templates.

## Public interface

- **Capability published:** `advisor.service_factory`.
- **Events emitted:** `advisor.client_linked`, `advisor.review_queued`.
- **Capabilities consumed (soft):**
  - `billing.service_factory` — to read workspace subscription/plan for per-client billing.
  - `export.service_factory` — to render white-label reports (future).

### API routes (prefix `/api/advisor`)

- `POST /clients` — link a client workspace to the advisor workspace.
- `GET /clients` — list linked clients.
- `GET /clients/{client_id}/usage` — usage billing summary for one client.
- `POST /review-queue/items` — add a review queue item for a client opportunity.
- `GET /review-queue` — list review queue items.
- `POST /review-queue/{item_id}/status` — update status (pending, in_review, approved).
- `POST /templates` — create a white-label report template.
- `GET /templates` — list templates.
- `GET /templates/{template_id}/config` — template config for export.

## Data owned

- `advisor_clients` — links advisor workspace to client workspaces.
- `advisor_review_queue` — review items for advisor staff.
- `advisor_templates` — white-label report templates with theme config.

All tables are workspace-scoped with RLS.

## Behavior

### Multi-client separation (TS-290)

- The advisor's `workspace_id` is the advisor workspace.
- `client_workspace_id` points to the linked client workspace.
- Advisors see only their own linked clients; RLS on `workspace_id` enforces this.

### Review queue (TS-290)

- Items reference an `opportunity_id` in the client workspace.
- `assigned_to`, `priority`, `status`, `due_date`.
- List supports filtering by `status`.

### Per-client usage billing (TS-290)

- `usage_events` summarize counts by `client_workspace_id` and `period`.
- `GET /usage` returns totals (opportunities, documents, reports) per client.

### White-label templates (TS-291)

- `AdvisorTemplate` stores `name`, `client_workspace_id` (nullable for default),
  `theme` (JSON), and `header` / `footer` text.
- `GET /templates/{id}/config` returns the merged theme for a client workspace
  (client-specific template overrides the advisor default).

## Acceptance criteria

- A1 (TS-290): CRUD for advisor client links.
- A2 (TS-290): Review queue create/list/update.
- A3 (TS-290): Per-client usage summary.
- A4 (TS-291): White-label templates CRUD and client-specific override lookup.
- A5: Migration and RLS present.

## Out of scope

- True multi-tenant billing aggregation across unrelated organizations.
- Marketplace publishing of advisor templates.
