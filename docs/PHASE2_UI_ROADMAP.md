# Phase 2+ UI Roadmap — Backend Routes Deferred from Round 13

**Sourced from:** `PRODUCTION_READINESS_AUDIT.md` Round 13
**Status:** Auto-generated from `scripts/validate_ui_api_coverage.py`

This document lists backend routes with no UI consumer. Phase 1 routes
must be wired in TS-382 before public launch; Phase 2+ routes are deferred.

| Module | Method | Route | Proposed phase | Rationale |
|---|---|---|---|---|
| `advisor` | GET | `/advisor/clients` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `advisor` | GET | `/advisor/clients/{}/usage` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `advisor` | GET | `/advisor/review-queue` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `advisor` | GET | `/advisor/status` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `advisor` | GET | `/advisor/templates` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `advisor` | GET | `/advisor/templates/{}/config` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `advisor` | POST | `/advisor/clients` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `advisor` | POST | `/advisor/review-queue/items` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `advisor` | POST | `/advisor/review-queue/{}/status` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `advisor` | POST | `/advisor/templates` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `analytics` | GET | `/analytics/accuracy` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `analytics` | GET | `/analytics/baseline-adoption` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `analytics` | GET | `/analytics/boq-defect-summary` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `analytics` | GET | `/analytics/claim-metrics` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `analytics` | GET | `/analytics/deadline-dashboard` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `analytics` | GET | `/analytics/plan/snapshots/{}` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `analytics` | GET | `/analytics/plan/snapshots/{}/export` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `analytics` | GET | `/analytics/plan/templates` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `analytics` | GET | `/analytics/risk-summary` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `analytics` | POST | `/analytics/reports/export` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `assistant` | GET | `/assistant/sessions` | TBD | Deferred pending product prioritization and phase exit gate. |
| `assistant` | POST | `/assistant/admin/chat` | TBD | Deferred pending product prioritization and phase exit gate. |
| `assistant` | POST | `/assistant/chat` | TBD | Deferred pending product prioritization and phase exit gate. |
| `assistant` | POST | `/assistant/sessions/{}/stream` | TBD | Deferred pending product prioritization and phase exit gate. |
| `auth` | POST | `/auth/export` | TBD | Deferred pending product prioritization and phase exit gate. |
| `auth` | POST | `/auth/members` | TBD | Deferred pending product prioritization and phase exit gate. |
| `baseline` | GET | `/baseline/baselines/{}` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `baseline` | GET | `/baseline/baselines/{}/verify` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `baseline` | GET | `/baseline/opportunities/{}/compare/award` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `baseline` | GET | `/baseline/opportunities/{}/cost-codes` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `baseline` | GET | `/baseline/opportunities/{}/handover/export` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `baseline` | GET | `/baseline/opportunities/{}/watchlist` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `baseline` | POST | `/baseline/opportunities/{}/award-document` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `baseline` | POST | `/baseline/opportunities/{}/cost-codes` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `baseline` | PUT | `/baseline/opportunities/{}/notice-register/contacts` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `baseline` | PUT | `/baseline/watchlist/{}` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `billing` | POST | `/billing/authorize-review` | TBD | Deferred pending product prioritization and phase exit gate. |
| `billing` | POST | `/billing/projects/{}/checkout` | TBD | Deferred pending product prioritization and phase exit gate. |
| `billing` | POST | `/billing/webhooks/razorpay` | TBD | Deferred pending product prioritization and phase exit gate. |
| `billing` | POST | `/billing/webhooks/stripe` | TBD | Deferred pending product prioritization and phase exit gate. |
| `change` | GET | `/change/events/{}/confirmations` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `change` | GET | `/change/opportunities/{}/inbox/email` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `change` | POST | `/change/events/{}/evidence` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `change` | POST | `/change/opportunities/{}/diff` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `change` | POST | `/change/opportunities/{}/inbox/email` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `change` | POST | `/change/opportunities/{}/signals/poll` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `change` | POST | `/change/webhooks/inbound-email` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `change` | PUT | `/change/events/{}/impacts` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `claims` | GET | `/claims/claims/{}/conflicts` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `claims` | GET | `/claims/claims/{}/timeline` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `claims` | GET | `/claims/opportunities/{}/claim-metrics` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `claims` | GET | `/claims/opportunities/{}/delay-register` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `claims` | POST | `/claims/opportunities/{}/delay-register` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `claims` | PUT | `/claims/claims/{}` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `comparison` | GET | `/comparison/opportunities` | Phase 1/2 | Deferred pending product prioritization and phase exit gate. |
| `comparison` | GET | `/comparison/opportunities/{}/deviation` | Phase 1/2 | Deferred pending product prioritization and phase exit gate. |
| `controltower` | GET | `/controltower/clause-trends` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `controltower` | GET | `/controltower/customer-outcomes` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `controltower` | GET | `/controltower/dashboard` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `controltower` | GET | `/controltower/economics` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `controltower` | GET | `/controltower/executive-summary` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `controltower` | GET | `/controltower/exposure` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `controltower` | GET | `/controltower/payment-schedule` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `controltower` | GET | `/controltower/portfolio` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `controltower` | GET | `/controltower/recurring-omissions` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `controltower` | GET | `/controltower/response-times` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `controltower` | POST | `/controltower/forecast` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `controltower` | POST | `/controltower/payment-schedule` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `crossref` | GET | `/crossref/opportunities/{}` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `crossref` | GET | `/crossref/opportunities/{}/contradictions` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `crossref` | POST | `/crossref/opportunities/{}/diff` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `drafting` | GET | `/drafting/artifacts/{}` | Phase 1/2 | Deferred pending product prioritization and phase exit gate. |
| `drawings` | GET | `/drawings/opportunities/{}/drawings/{}` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `drawings` | GET | `/drawings/opportunities/{}/drawings/{}/heatmap` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `drawings` | POST | `/drawings/opportunities/{}/drawings/{}/symbol-assist` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `evidence` | GET | `/evidence/events/{}/completeness` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `evidence` | GET | `/evidence/events/{}/records` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `evidence` | GET | `/evidence/records/{}` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `evidence` | POST | `/evidence/events/{}/records` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `export` | GET | `/export/opportunities/{}` | Phase 1/2 | Deferred pending product prioritization and phase exit gate. |
| `export` | POST | `/export/opportunities/{}/comparison-summary` | Phase 1/2 | Deferred pending product prioritization and phase exit gate. |
| `export` | POST | `/export/opportunities/{}/email-summary` | Phase 1/2 | Deferred pending product prioritization and phase exit gate. |
| `express` | GET | `/express/sessions/{}` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `express` | GET | `/express/sessions/{}/export` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `express` | GET | `/express/sessions/{}/report` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `express` | GET | `/express/sessions/{}/teaser` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `express` | POST | `/express/sessions` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `express` | POST | `/express/sessions/{}/checkout` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `express` | POST | `/express/sessions/{}/claim` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `express` | POST | `/express/sessions/{}/documents` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `governance` | PUT | `/governance/workspaces/{}/data-governance` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `health` | GET | `/health/details` | N/A | Deferred pending product prioritization and phase exit gate. |
| `health` | GET | `/health/live` | N/A | Deferred pending product prioritization and phase exit gate. |
| `health` | GET | `/health/metrics` | N/A | Deferred pending product prioritization and phase exit gate. |
| `health` | GET | `/health/ready` | N/A | Deferred pending product prioritization and phase exit gate. |
| `integrations` | GET | `/integrations/connectors/{}/callback` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `integrations` | GET | `/integrations/schedule/opportunities/{}/activities` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `integrations` | GET | `/integrations/sources/{}/documents` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `integrations` | GET | `/integrations/sources/{}/events` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `integrations` | GET | `/integrations/sources/{}/jobs` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `integrations` | GET | `/integrations/status` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `integrations` | POST | `/integrations/dynamic-connectors/{}/poll` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `integrations` | POST | `/integrations/schedule/import` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `integrations` | POST | `/integrations/sources/{}/import` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `integrations` | POST | `/integrations/sources/{}/poll` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `integrations` | POST | `/integrations/sources/{}/webhook` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `marketdata` | GET | `/marketdata/employers/{}/profile` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `marketdata` | GET | `/marketdata/opportunities/{}/benchmark` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `marketdata` | GET | `/marketdata/opportunities/{}/comparables` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `marketdata` | GET | `/marketdata/opportunities/{}/employer-context` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `outcomes` | GET | `/outcomes/metrics/margin-protected` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `outcomes` | GET | `/outcomes/opportunities/{}` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `outcomes` | GET | `/outcomes/opportunities/{}/scope-patterns` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `outcomes` | POST | `/outcomes/findings/{}/materialized` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `outcomes` | POST | `/outcomes/opportunities/{}` | Phase 3 | Deferred pending product prioritization and phase exit gate. |
| `public_api` | GET | `/public_api/signatures/{}/status` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `public_api` | GET | `/public_api/status` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `public_api` | POST | `/public_api/notices/{}/request-signature` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `public_api` | POST | `/public_api/signatures/callback` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `qualification` | GET | `/qualification/opportunities/{}` | Phase 1/2 | Deferred pending product prioritization and phase exit gate. |
| `qualification` | POST | `/qualification/opportunities/{}` | Phase 1/2 | Deferred pending product prioritization and phase exit gate. |
| `review` | GET | `/review/opportunities/{}/audit` | Phase 1/2 | Deferred pending product prioritization and phase exit gate. |
| `review` | GET | `/review/opportunities/{}/queue` | Phase 1/2 | Deferred pending product prioritization and phase exit gate. |
| `standards` | DELETE | `/standards/commercial/{}` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `standards` | GET | `/standards/commercial` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `standards` | POST | `/standards/opportunities/{}/check` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `standards` | PUT | `/standards/commercial/{}` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `support` | GET | `/support/admin/tickets` | Phase 1/2 | Deferred pending product prioritization and phase exit gate. |
| `support` | POST | `/support/tickets/{}/attachments` | Phase 1/2 | Deferred pending product prioritization and phase exit gate. |
| `timeline` | GET | `/timeline/opportunities/{}/timeline` | Phase 2 | Deferred pending product prioritization and phase exit gate. |
| `timeline` | GET | `/timeline/opportunities/{}/timeline.ics` | Phase 2 | Deferred pending product prioritization and phase exit gate. |

## Next actions

- When a module is promoted, move its routes to `docs/ROUND13_GAP_CLOSURE_REQUIREMENTS.md` R3.1 and create the corresponding `frontend/lib/api.ts` wrapper and page.
- Review this roadmap at the start of each phase to confirm deferrals are still valid.
