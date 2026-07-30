# Qualification Compliance Matrix — Spec

**Status:** implemented (TS-049)
**Requirement refs:** Phase 1.5 doc §5
**Task refs:** TS-049

## Purpose

Extract eligibility criteria (minimum turnover, similar-project experience,
equipment, engineer requirements, certifications, EMD, bid security,
experience years) from the tender pack and present a compliance matrix with
status, evidence, and required actions.

## Public interface

- **Capabilities published:** `qualification.service_factory`.
- **Capabilities consumed (soft):** `ingestion.service_factory` (clauses),
  `findings.store_factory` (persist gap findings).
- **API routes:**
  - `GET /api/qualification/opportunities/{id}` — build matrix in memory.
  - `POST /api/qualification/opportunities/{id}` — build and persist findings.

## Data owned

None; `qualification_gap` findings are written through the shared `findings` store.

## Behavior

- **B1 (deterministic extraction):** each criterion is matched by keyword set on
  the segmented clause text; no numbers or status come from an LLM.
- **B2 (status logic):**
  - `met` — currently not emitted; reserved for future org-profile comparison.
  - `unknown` — criterion was found in the tender, or it was not found and needs
    human review; the contractor must verify their evidence against the quoted requirement.
  - `not_met` — reserved for a confirmed mismatch between the tender requirement
    and the contractor's profile (future phase).
- **B3 (provenance):** every row carries `source_page` and `source_quote` of the
  clause the keyword matched.
- **B4 (findings):** a `POST` writes or replaces the producer's `qualification_gap`
  findings in the shared `findings` table. Missing criteria are written as `unknown`
  with MEDIUM severity, not as `not_met` with HIGH severity.
- **B5 (summary):** `status` is `not_eligible` if any row is `not_met`,
  `needs_review` if any row is `unknown`, otherwise `eligible`.

## Acceptance criteria

- A1: `POST /api/qualification/opportunities/{id}` returns at least the 8 required
  criteria rows.
- A2: missing criteria are `unknown` with an action-required note.
- A3: every `unknown` row cites a verbatim source quote and page.
- A4: the summary rolls up to `not_eligible` / `needs_review` / `eligible` correctly.

## Out of scope

- Org-profile comparison (phase 2), auto-document upload for evidence (phase 2).
