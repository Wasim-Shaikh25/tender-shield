# Phase 21 — Integrations, Subcontract Control & Advisor Edition — Tracker

**Requirement source:** Research Doc §4.I, §10.2, §12.3, §13; `docs/TenderShield_Roadmap_Stage1_to_5.md` §6
**Specs:** `specs/modules/integrations.md`, `specs/modules/subcontract.md`, `specs/modules/advisor.md`
**Backlog:** `tasks/backlog.md` §Phase 21 (TS-281 – TS-292)
**Master roadmap:** `docs/TenderShield_Roadmap_Stage1_to_5.md` · `tasks/roadmap_tracker.md`

**Phase goal.** Add an upload/export-first integration adapter framework, subcontract
flow-down and notice-chain control, an advisor multi-client workspace, and a
public API / e-signature foundation.

**Unlock gate:** Phase 20 in production use with at least one customer.

**Phase exit gate.** A user can configure a source adapter, upload a SharePoint / Procore /
ERP / schedule payload, see imported documents/events/activities/cost lines, and a
contractor can track subcontract back-to-back notice and pay-when-paid exposure.

---

## Sprint map

| Sprint | Theme | Tasks | Exit gate | Status |
|---|---|---|---|---|
| **0** | **Integration adapter framework** | TS-281–TS-287 | Adapter registry; upload-based imports for SharePoint/OneDrive, Procore, Autodesk, Aconex, ERP, schedule | done |
| **1** | **Subcontract control** | TS-288, TS-289 | Flow-down clause comparison; back-to-back notice calendar; pay-when-paid flags | done |
| **2** | **Advisor Edition** | TS-290, TS-291 | Multi-client workspace separation; per-client usage billing; white-label reports | done |
| **3** | **Public API + e-signature** | TS-292 | API-key auth; e-signature request/issue endpoints | done |

## Task table

| ID | Title | Module | Priority | Status | Acceptance (short) | Blockers |
|---|---|---|---|---|---|---|
| TS-281 | Spec: integration adapter framework | `integrations` | P0 | done | `specs/modules/integrations.md` agreed; registry boots | Phase 20 |
| TS-282 | SharePoint / OneDrive document-source adapter | `integrations` | P1 | done | Upload payload → `documents` + mapping rows | TS-281 |
| TS-283 | Procore adapter | `integrations` | P1 | done | RFI / change-event payload → `change_events` | TS-281 |
| TS-284 | Autodesk Construction Cloud adapter | `integrations` | P1 | done | Issues / submittals → documents/events | TS-281 |
| TS-285 | Oracle Aconex adapter | `integrations` | P1 | done | Mail / transmittal → documents + change events | TS-281 |
| TS-286 | ERP adapter (Tally / SAP / Dynamics) | `integrations` | P1 | done | Cost-code CSV/JSON → `integration_cost_lines` | TS-281 |
| TS-287 | Schedule import: P6 / MS Project | `integrations` | P1 | done | CSV/XML/XER → `integration_schedule_activities` | TS-281 |
| TS-288 | Subcontract flow-down and scope-gap checks | `subcontract` | P1 | done | Compare subcontract clauses to main contract; flag gaps | TS-281 |
| TS-289 | Back-to-back notice calendar and pay-when-paid exposure | `subcontract` | P1 | done | Notice deadlines + payment ageing across subcontract chain | TS-288 |
| TS-290 | Advisor Edition: multi-client workspaces | `advisor` | P1 | done | Advisor workspace links client workspaces | Phase 20 |
| TS-291 | White-label branded report templates | `advisor` | P1 | done | Per-client report theme/template config | TS-290 |
| TS-292 | Public API + e-signature integration | `public_api` | P1 | done | API keys, scopes, notice issue / signature webhook | TS-290 |

## Product invariants (Phase 21)

- **Upload/export first** — live OAuth/API polling is out of scope until exit gates prove value.
- **Adapter registry** — all source normalizers implement `BaseAdapter.normalize` and are registered by `name`.
- **No invented numbers** — imported cost/schedule values are taken verbatim from the uploaded payload.
- **Cross-module via registry** — integrations uses `ingestion` and `change` only through registry capabilities.
