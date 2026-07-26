# Tender Timeline — Spec

**Status:** implemented (TS-052)
**Requirement refs:** Phase 1.5 doc §5
**Task refs:** TS-052

## Purpose

Turn extracted deadlines into a single chronological milestone calendar so a
contractor can see the whole pre-award schedule at a glance and export it to a
calendar file.

## Public interface

- **Capabilities published:** `timeline.service_factory` (build a timeline for
  an opportunity).
- **Capabilities consumed (soft):** `ingestion.service_factory` (opportunity + deadlines).
- **API routes:**
  - `GET /api/timeline/opportunities/{id}` — JSON list of timeline events.
  - `GET /api/timeline/opportunities/{id}/timeline.ics` — iCal export.

## Data owned

None; the module is a read-only view over ingestion's `deadlines` and `opportunities`.

## Behavior

- **B1 (milestone normalization):** raw deadline kinds (`submission`, `prebid_meeting`,
  `emd`, `validity`, `completion_milestone`, etc.) are normalized to a canonical
  milestone vocabulary:
  `tender_published`, `pre_bid_meeting`, `clarification_cutoff`, `bid_submission`,
  `technical_opening`, `financial_opening`, `emd_validity`, `bid_validity`,
  `bg_submission`, `contract_signing`, `completion`.
- **B2 (synthetic anchor):** a `tender_published` event is created from the
  opportunity `created_at` timestamp as a proxy for the publication anchor.
- **B3 (sorting):** events are sorted by concrete `due_at` ascending, with
  undated events at the end.
- **B4 (provenance):** every event carries `source_page`, `source_quote`, and
  `confirmed`; synthetic events are marked `source: "synthetic"`.
- **B5 (export):** the `.ics` endpoint produces a valid iCalendar 2.0 file of
  all dated events for the opportunity.

## Acceptance criteria

- A1: `GET /api/timeline/opportunities/{id}` returns at least the 9 required
  milestone kinds when matching text is present in the tender pack.
- A2: undated events do not break sorting or export.
- A3: iCal export contains one `VEVENT` per dated milestone.

## Out of scope

- Gantt chart rendering (frontend P2), notification/reminder scheduling (P2),
  critical-path analysis between milestones (P3).
