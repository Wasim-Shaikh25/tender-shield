# Control Tower — Spec

**Status:** draft
**Requirement refs:** Research Doc §4.H, §12.2, §13; `docs/TenderShield_Roadmap_Stage1_to_5.md` §4 Stage 5
**Task refs:** TS-271, TS-272, TS-273, TS-274, TS-275, TS-276, TS-277, TS-278, TS-279, TS-280

## Purpose

A portfolio-level commercial control tower for construction contractors. It aggregates claim,
change, baseline, deadline, evidence, finding, billing, and outcome data into deterministic
commercial intelligence: exposure, forecast, response-time analytics, clause trends, executive
summaries, payment control, economics, and customer outcomes.

## Public interface

### Capabilities published

- `controltower.service_factory` → `ControlTowerService(session)`.
- `controltower.exposure_for_opportunity` — deterministic exposure snapshot for one opportunity.
- `controltower.dashboard_for_opportunity` — deadline + evidence-health summary for one opportunity.
- `controltower.portfolio_summary` — workspace-level rollup of exposure, claim status counts, and
  evidence-health averages.
- `controltower.forecast_for_opportunity` — risk-adjusted forecast at completion.
- `controltower.response_times_for_opportunity` — client/consultant response-time analytics.
- `controltower.clause_trends_for_workspace` — portfolio clause trends and loss-reason rollup.
- `controltower.executive_summary_for_opportunity` — high-level summary with drill-down links.
- `controltower.payment_schedule_for_opportunity` — RA/progress/retention/security schedule with
  ageing.
- `controltower.economics_for_workspace` — paid conversion, gross margin, CAC payback, retention,
  expansion revenue.
- `controltower.customer_outcomes_for_workspace` — risks priced, bad bids declined, omissions
  corrected, value notified/certified, hours saved.

### Capabilities consumed (soft)

| Capability | Use |
|---|---|
| `ingestion.service_factory` | List opportunities and contract value. |
| `claims.service_factory` / `claims.summary_for_opportunity` / `claims.response_analytics_for_opportunity` | Claim value, status, and response-time analytics. |
| `change.events_for_opportunity` | Unnotified / unclaimed change events. |
| `evidence.completeness_for_event` | Evidence-health score per change event. |
| `findings.store_factory` | Cross-project clause/loss-reason rollups. |
| `outcomes.service_factory` / `outcomes.bid_outcomes_for_workspace` / `outcomes.risk_materializations_for_workspace` / `outcomes.margin_protected` | Bid outcomes, materializations, claim recoveries, customer-outcome metrics. |
| `billing.service_factory` / `billing.invoices_for_workspace` / `billing.subscriptions_for_workspace` | Economics and payment metrics. |

### Events emitted

- `controltower.exposure_computed` — per-opportunity exposure totals.
- `controltower.forecast_computed` — per-opportunity forecast assumptions and result.

### API routes (prefix `/api/controltower`)

- `GET /exposure?opportunity_id={id}` (viewer) — per-project exposure model.
- `GET /dashboard?opportunity_id={id}` (viewer) — deadline + evidence-health dashboard.
- `GET /portfolio` (viewer) — workspace exposure + health rollup.
- `POST /forecast` (viewer) — risk-adjusted forecast at completion.
- `GET /response-times?opportunity_id={id}` (viewer) — response-time analytics.
- `GET /clause-trends` (viewer) — portfolio clause trends and loss-reason analysis.
- `GET /executive-summary?opportunity_id={id}` (viewer) — executive summary with source links.
- `GET /payment-schedule?opportunity_id={id}` (viewer) — payment control schedule.
- `POST /payment-schedule` (estimator) — add/update a payment event.
- `GET /economics` (viewer) — workspace economics metrics.
- `GET /customer-outcomes` (viewer) — workspace customer-outcome metrics.

## Data owned

- `ct_payment_events` — payment-control schedule entries (RA/progress, retention, security) per
  opportunity. Workspace-scoped with RLS.

For TS-274–TS-280 the remaining data is read from other modules via the registry.

## Behavior

### Exposure model (B1–B7, TS-272)

- **B1 — Contract value anchor.** If `Opportunity.contract_value_minor` is set, it is used as the
  revenue base; otherwise `contract_value_minor` is `None` and at-risk revenue is omitted.
- **B2 — Submitted value.** Sum of `claim_amount_minor` for claims with status in
  `submitted`, `under_review`, `negotiated`, `disputed`.
- **B3 — Certified value.** Sum of `recovered_amount_minor` for `settled` claims.
- **B4 — Rejected/withdrawn value.** Sum of `claim_amount_minor` for claims with status
  `rejected` or `withdrawn`.
- **B5 — Unnotified change value.** Sum of `claim_amount_minor` on `draft` claims linked to a
  change event. Change events with no linked claim are reported as a count, not a rupee value.
- **B6 — Ageing.** For each unsettled claim, `age_days = today - submitted_at`; average and max are
  exposed.
- **B7 — Cash exposure.** Sum over unsettled claims of
  `claim_amount_minor * age_days * (cost_of_capital_pa / 365)`. `cost_of_capital_pa` is an explicit
  query parameter.

### Deadline + evidence-health dashboard (B8–B11, TS-273)

- **B8 — Deadline list.** All `deadlines` for the opportunity, sorted by `due_at`, flagged
  `overdue`, `due_soon` (< 7 days), or `ok`.
- **B9 — Evidence health.** Average `evidence.completeness_for_event` across confirmed change
  events; list events below 100%.
- **B10 — Unclaimed change events.** Confirmed events with no linked submitted claim.
- **B11 — Degradation.** Missing soft deps produce explicit `unavailable` flags.

### Portfolio summary (B12, TS-272/273)

- **B12 — Workspace rollup.** Sum per-opportunity exposure totals; classify opportunities by
  evidence-health tier (`healthy` ≥ 80, `at_risk` 50–79, `poor` < 50).

### Risk-adjusted forecast at completion (B13–B15, TS-274)

- **B13 — Explicit inputs.** The caller provides `projected_final_cost_minor`,
  `contingency_percent` (0–100), and `cost_of_capital_pa`. The forecast is never invented.
- **B14 — Forecast revenue.** `forecast_revenue_minor = contract_value_minor - at_risk_revenue_minor`.
- **B15 — Forecast cost.** `forecast_cost_minor = projected_final_cost_minor * (1 + contingency_percent/100) + unnotified_change_minor + cash_exposure_minor`.
  The response includes every assumption and input value.

### Client / consultant response-time analytics (B16–B18, TS-275)

- **B16 — Response time.** For each `ClaimResponse`, `response_days = received_at - submitted_at`.
- **B17 — Grouping.** Group by `responder`; compute `min`, `max`, `avg`, `median`, `p90` response
  days and count.
- **B18 — Negotiation cadence.** `ClaimNegotiation` rounds are counted per claim; average days
  between rounds (`recorded_at` deltas) are exposed.

### Portfolio clause trends and loss-reason analysis (B19–B21, TS-276)

- **B19 — Pattern rollup.** Count and total `amount_exposure` of `FindingRow` per
  `category`/`pattern_id` across the workspace.
- **B20 — Loss reasons.** For `FindingRow` with `review_status = rejected`, group by
  `review_reason` and count.
- **B21 — Trend summary.** Top recurring categories, patterns, and loss reasons by volume and
  exposure value.

### Executive summaries with source links and drill-down (B22–B24, TS-277)

- **B22 — Summary card.** Opportunity title, contract value, exposure totals, health score,
  response-time summary, and forecast.
- **B23 — Top risks.** Up to 5 findings by `amount_exposure` with `source_page`, `source_quote`,
  `document_id`, and finding id for drill-down.
- **B24 — Drill-down lists.** Deadlines, unclaimed change events, unsettled claims, and payment
  events each carry their entity ids.

### Payment control (B25–B30, TS-278)

- **B25 — Payment event kinds.** `ra` (running account), `progress`, `retention`, `security`.
- **B26 — Schedule fields.** `opportunity_id`, `kind`, `due_date`, `amount_minor`,
  `certified_amount_minor`, `currency`, `status` (`pending`/`certified`/`released`), `released_at`.
- **B27 — Certification variance.** `variance_minor = amount_minor - certified_amount_minor`.
- **B28 — Ageing.** For pending events, `age_days = today - due_date`; overdue flagged.
- **B29 — Collection actions.** Overdue pending RA/progress events are listed as `collection_actions`.
- **B30 — Retention / security release.** Events with kind `retention`/`security` that are
  certified but not released are surfaced as release actions.

### Economics metrics (B31–B36, TS-279)

- **B31 — Explicit cost inputs.** `cost_of_sales_minor` and `customer_acquisition_cost_minor` are
  caller-provided query/body parameters; the platform does not invent them.
- **B32 — Paid conversion.** `paid_opportunities / total_opportunities` where paid means the
  opportunity has a paid `ProjectSubscription` or paid invoice.
- **B33 — Gross margin.** `(total_invoiced_minor - cost_of_sales_minor) / total_invoiced_minor`.
  If `total_invoiced_minor` is zero, report `None`.
- **B34 — CAC payback.** `customer_acquisition_cost_minor / avg_revenue_per_opportunity_minor`;
  `avg_revenue_per_opportunity` is total paid invoice value divided by paid opportunity count.
- **B35 — Project retention.** Percentage of opportunities with a paid invoice that also have a
  subscription (or more than one invoice).
- **B36 — Expansion revenue.** Paid invoice value from opportunities that had a prior invoice.

### Customer-outcome metrics (B37–B42, TS-280)

- **B37 — Risks priced.** Count of findings with `amount_exposure` set and total exposure value.
- **B38 — Bad bids declined.** Count of `OcBidOutcome` with `result = declined` and total
  `quoted_value_minor` avoided.
- **B39 — Omissions corrected.** Count of materialized risks where `materialized = false` (the
  risk was caught and mitigated) and total `impact_amount_minor` avoided.
- **B40 — Value notified/certified.** Sum of submitted and settled claim value plus change-event
  evidence count.
- **B41 — Hours saved.** A caller-provided `hours_per_review_saved` parameter multiplied by
  reviewed finding count.
- **B42 — Degradation.** Missing `outcomes` or `findings` soft deps produce explicit `unavailable`
  flags, not invented numbers.

## Acceptance criteria

- A1 (TS-271): `controltower.md` spec exists and is indexed in `specs/README.md`.
- A2 (TS-272): `/exposure` returns deterministic submitted/certified/rejected/unnotified/ageing/cash values.
- A3 (TS-273): `/dashboard` returns deadlines, evidence-health, and unclaimed events.
- A4 (TS-274): `/forecast` requires explicit inputs and returns assumptions + forecast revenue/cost.
- A5 (TS-275): `/response-times` returns per-responder min/max/avg/median/p90 and negotiation cadence.
- A6 (TS-276): `/clause-trends` returns pattern counts, exposure totals, and loss-reason breakdown.
- A7 (TS-277): `/executive-summary` includes top risks with source links and drill-down ids.
- A8 (TS-278): `/payment-schedule` supports CRUD and reports certification variance, ageing, and
  collection/release actions.
- A9 (TS-279): `/economics` computes paid conversion, gross margin, CAC payback, retention, and
  expansion revenue from explicit inputs + billing data.
- A10 (TS-280): `/customer-outcomes` computes risks priced, bad bids declined, omissions corrected,
  value notified/certified, and hours saved.

## Out of scope

- Phase 21 integrations (Procore, Aconex, Autodesk, ERP, schedule imports) and subcontract control.
- Forecasts based on machine learning; this slice is deterministic.

## Assumptions

- `assumption:` `Opportunity.contract_value_minor` is present because the Phase 20 foundation
  added it.
- `assumption:` Economics and customer-outcome metrics that need cost or hours inputs are explicit
  parameters; the platform does not invent them.
- `assumption:` Payment-control schedule is a controltower-owned table because no other module owns
  RA/progress/retention/security events.
