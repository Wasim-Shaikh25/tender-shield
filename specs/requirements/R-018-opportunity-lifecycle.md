# R-018 — Opportunity lifecycle and the bid/no-bid decision

**Status:** draft
**Severity:** P0 — the product produces "bid-decision artifacts" but has nowhere
to record the decision; `Opportunity.status` is a dead column
**Requirement refs:** Doc §0.1, §1.1, §10 (phase/kill gates)
**Task refs:** TS-111
**Gap refs:** `docs/PRODUCT_DISCOVERY_GAPS.md` §G-02
**Specs to update:** `specs/modules/ingestion.md`, `specs/frontend.md`

## Purpose

`Opportunity.status` defaults to `"reviewing"` and is **never assigned anywhere in
the codebase**:

```python
# backend/app/modules/ingestion/models.py
status: Mapped[str] = mapped_column(String, nullable=False, default="reviewing")
```

`grep` for writes to it returns nothing. There is no `PATCH /opportunities/{id}`.
The frontend renders `statusLabel(o.status)` on every card, so every opportunity
in the product permanently reads "reviewing".

Nothing anywhere records a bid/no-bid outcome — the decision the entire product
exists to inform. The user does the analysis in TenderShield and then leaves to
make and record the decision elsewhere.

Two consequences beyond the obvious:

- **R-012's dashboard cannot segment a pipeline** without a status to segment by.
- **The product overview's own metrics are unmeasurable.** The Phase-1 exit gate
  and the "<40% second-tender conversion" kill gate both require knowing what
  happened to a tender after review.

## Target

### B.1 A validated lifecycle

```
reviewing → bid | no_bid → submitted → won | lost
         ↘ withdrawn
```

Transitions are validated **server-side** against an explicit map — an invalid
jump is rejected, not silently written. Terminal states (`won`, `lost`,
`withdrawn`, `no_bid`) drop the record out of "live" views without deleting it.

`assumption:` this state list is inferred from the domain, not from a product
brief. It is a **product decision** — see Questions.

### B.2 The decision record

The outcome, who decided, when, and optionally why:

```python
decided_by: Mapped[uuid.UUID | None]
decided_at: Mapped[datetime | None]
decision_rationale: Mapped[str | None]
```

Kept on the opportunity rather than a separate table: there is exactly one
current decision per opportunity, and the transition history lives in the audit
trail (R-021) rather than being duplicated here.

### B.3 Route

`PATCH /api/ingestion/opportunities/{id}` — `estimator` or above. Accepts
`status` and decision fields; rejects invalid transitions with a specific code
(`invalid_transition`, 400) naming the current and attempted state.

### B.4 Every transition is audited

Writes to the audit trail (R-021) with actor, from-state, to-state and rationale.
A commercial decision worth £millions of exposure needs an evidence record.

## Behavior

- **B1** Status transitions are validated server-side against the map.
- **B2** A decision records actor and timestamp; rationale is optional.
- **B3** The board filters live vs closed; closed opportunities remain fully
  readable and exportable.
- **B4** Every transition is audited.
- **B5** Terminal-state opportunities stop generating deadline alerts (R-020).

## Acceptance criteria

- **A1** An invalid transition (e.g. `won` directly from `reviewing`) returns
  `400 invalid_transition` and writes nothing.
- **A2** A recorded decision carries `decided_by` and `decided_at`.
- **A3** The board can filter to live opportunities only, and a closed one is
  excluded without being deleted.
- **A4** Every transition appears in the audit trail with both states.
- **A5** A closed opportunity's findings, artifacts and exports remain reachable.
- **A6** A `viewer` cannot change status (`403`).

## Out of scope

- Approval workflows (a second person signing off a large-tender no-bid) — a real
  possibility for the P1 persona but unconfirmed; see Questions.
- Win/loss analytics and the outcome graph (Doc §0.1 roadmap, Phase 2+).
- Automatic status inference from deadlines (e.g. auto-closing past submission
  date) — surprising behavior on a commercial record; deliberate manual action
  only for v1.

## Questions for the product owner

1. **What is the authoritative status list** for an Indian GC's tender pipeline?
   Does "submitted" precede an award wait, and are "technical qualification" or
   "L1/L2 position" real states worth modelling?
2. **Should a no-bid require a reason from a controlled vocabulary?** If yes, that
   list becomes the most commercially valuable dataset the product collects —
   why contractors walk away from tenders, at scale.
3. Does a large-tender decision need second-person approval?

## Assumptions

- `assumption:` one decision per opportunity; re-deciding overwrites the current
  decision and leaves the prior one in the audit trail.
- `assumption:` status is manual. Nothing infers it from deadlines or exports.
