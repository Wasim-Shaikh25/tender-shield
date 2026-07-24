# Standards (org-custom) — Spec

**Status:** implemented
**Requirement refs:** Doc §10 (Phase 2 "custom playbooks"), §0.1, §2 (rule-packs
as data)
**Task refs:** TS-047

## Purpose

The third layer of the notice-standards stack. Rule-packs provide the
**universal** base and a **regional** overlay (spec rulepacks B7); this module
lets a firm publish **its own** notice regimes — kept as org data, not filesystem
packs. A firm's standard either **prevails** over the rule-pack standard
(overriding matching regimes) or runs **side by side** (shown alongside for
comparison). The `baseline` module merges this layer on top when producing the
notice-rule register + gap detection.

## Public interface

- **Capability published:** `standards.org_notice_provider` →
  `OrgStandardsService(session)` exposing `get_notice(org_id) -> {mode,
  categories} | None`.
- **Events:** none.
- **Consumers:** `baseline` (merges the org overlay onto universal + regional).
- **API routes** (prefix `/api/standards`):
  - `GET /notice` (viewer) — the org's custom standard (`{mode, categories}`;
    empty default when unset).
  - `PUT /notice` (admin) — set mode + categories (validated, deduped by key).
  - `DELETE /notice` (admin) — clear it.

## Data owned

- `org_notice_standards` (org-scoped, RLS): one row per org — `mode`
  (`prevail` | `side_by_side`), `categories` (JSON list of notice categories:
  `key, label, typical_days, expected, keywords, note`), `updated_by`,
  `updated_at`. `org_id` is unique (one active standard per org).

## Behavior

- **B1 — Layered merge (consumed by baseline).** Effective categories =
  universal + regional (rule-pack) with the org overlay applied: `prevail`
  overrides a rule-pack category sharing the same `key` (keeping base fields the
  org omits) and appends org-only regimes; `side_by_side` appends every org
  regime without overriding. Org-origin categories are tagged `origin="org"`.
- **B2 — Validation at the boundary.** `PUT` validates each category
  (`NoticeCategoryIn`): non-empty `key`/`label`, `typical_days ≥ 0`; duplicate
  keys are rejected (`duplicate_keys`), bad mode rejected (`bad_mode`).
- **B3 — Role gating.** Reading is `viewer`; writing/clearing is `admin`
  (firm-level configuration).
- **B4 — Org isolation.** One row per org, filtered by `org_id` (RLS + explicit
  filter), like every module.

## Acceptance criteria

- A1: `GET` before any set returns `{mode: "prevail", categories: []}`.
- A2: `PUT` a regime then `GET` reads it back; `DELETE` clears it.
- A3: bad mode → 400; duplicate keys → 409.
- A4 (via baseline): an org `expected` regime absent from a contract appears as a
  gap tagged `origin="org"`; in `side_by_side` the contract's own window still
  classifies against the rule-pack category.

## Out of scope

- Per-opportunity or per-employer-family overrides (this is org-wide); risk/BOQ
  playbook customisation (separate future work); versioning/history of the org
  standard (single current row for now).

## Assumptions

- `assumption:` one active custom notice standard per org is sufficient for
  Phase 2; multiple named profiles are deferred.
