# 04 — `outcomes`, correction loop, north-star (TS-215, TS-216, TS-218, TS-234)

**Specs:** `specs/modules/outcomes.md`, `specs/modules/rulepacks.md` (TS-218 update).
**Sprint 6** in `tasks/phase16_tracker.md`.

The spec calls TS-215 *"the cheapest moat increment in the plan — a handful of columns, one form,
one event."* It is also a **re-sequencing dependency**: `phase16_tracker.md` lists TS-234
(north-star) as depending on TS-215, so TS-215 must land **before or alongside** TS-234, not after.

---

## TS-215 — Outcome capture

**New module** `backend/app/modules/outcomes/`. Standard workspace-scoped module — follow
`00-conventions.md` §2–§4 exactly (this one *does* use `WorkspaceScopedMixin`, unlike `marketdata`).

```python
# models.py
class OcBidOutcome(Base, WorkspaceScopedMixin):
    _tablename_ = "oc_bid_outcomes"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True, unique=True)
    result: Mapped[str] = mapped_column(String, nullable=False)   # see BidResult below
    quoted_value_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    l1_value_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    bidder_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    prefilled_from: Mapped[str | None] = mapped_column(String, nullable=True)  # "marketdata"|None
    confirmed: Mapped[bool] = mapped_column(nullable=False, default=False)
    recorded_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)

class OcRiskMaterialization(Base, WorkspaceScopedMixin):
    _tablename_ = "oc_risk_materialization"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    materialized: Mapped[bool] = mapped_column(nullable=False)
    impact_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    narrative: Mapped[str | None] = mapped_column(String, nullable=True)
    recorded_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
```

Add the enum to `app/core/contracts/` (shared contract, not owned by one module):

```python
class BidResult(StrEnum):
    SUBMITTED    = "submitted"
    WON          = "won"
    LOST         = "lost"
    DECLINED     = "declined"
    DISQUALIFIED = "disqualified"
```

**Routes**

```
POST /api/outcomes/opportunities/{id}            # record/update outcome (upsert on opportunity_id)
POST /api/outcomes/findings/{id}/materialized    # mark a finding materialized
GET  /api/outcomes/opportunities/{id}
```

**Events** — publish through `ctx.events`, and note that a `finding_id` in the payload lets
`analytics` and the correction loop join without importing anything:

```python
ctx.events.publish("outcome.recorded", {
    "workspace_id": str(ws), "opportunity_id": str(oid), "result": result,
})
ctx.events.publish("outcome.risk_materialized", {
    "workspace_id": str(ws), "finding_id": str(fid),
    "impact_minor": impact, "currency": currency,
})
```

**Privacy is a hard requirement, not a preference.** Outcome data reveals a firm's win rate and
pricing. It is workspace-scoped, **never contributes to the shared `marketdata` graph**, and never
appears in a cross-tenant aggregate.

```python
def test_outcomes_never_reach_marketdata(client):
    # record an outcome in workspace A, then assert no md_* row references it
    ...
def test_cross_tenant_outcome_read_denied(client):
    h1, _ = auth_headers_and_workspace(client, "a@example.com", workspace_name="A")
    h2, _ = auth_headers_and_workspace(client, "b@example.com", workspace_name="B")
    # ... create with h1 ...
    assert client.get(f"/api/outcomes/opportunities/{oid}", headers=h2).status_code in (403, 404)
```

---

## TS-216 — Award-record prefill

**Design principle from the spec, in its own words: *"Prefill, don't demand."* Users will not fill
in forms.**

On `opportunity.status` reaching a terminal state, try to match the public award record through
`marketdata` and ask for **one-click confirmation**. Manual entry is always available and is never
the only path.

```python
def prefill(self, workspace_id, opportunity_id) -> dict | None:
    comparable = self._reg.get("marketdata.comparable_awards")
    if comparable is None:
        return None                      # marketdata disabled → manual path, no error
    try:
        award = comparable(self._session).by_tender_reference(ref)
    except Exception:
        logger.warning("marketdata prefill unavailable; falling back to manual entry")
        return None
    if award is None:
        return None
    return {
        "result": "lost" if award.winner_name != own_name else "won",
        "l1_value_minor": award.award_value_minor,
        "currency": award.currency,
        "bidder_count": award.bidder_count,
        "prefilled_from": "marketdata",
        "confirmed": False,              # NOT recorded until the user confirms
    }
```

`confirmed=False` matters: a prefilled-but-unconfirmed outcome must not feed the correction loop or
the north-star metric. Inferring outcomes from behaviour without user confirmation is explicitly
out of scope.

**Acceptance:** prefill works where a tender reference matches; **degrades silently to manual entry
where it does not**; disabling `marketdata` leaves outcome recording fully functional.

---

## TS-218 — Correction loop (`rulepacks`) — proposes, never mutates

**The one rule that governs this entire task:** *the loop proposes; a human approves.* Rulepacks are
**never auto-mutated** (Build Doc §2.4). If the implementation can write a pack file without a human
in the loop, it is wrong regardless of how good the signal is.

Aggregate review corrections per pattern per employer family → a **proposed overlay** surfaced in
the admin console:

```python
@dataclass(frozen=True)
class ProposedCorrection:
    pattern_id: str
    employer_family: str | None
    signal: str            # "severity_downgrade" | "severity_upgrade" | "new_pattern_candidate"
    evidence_count: int
    sample_size: int
    rationale: str         # human-readable, cites the counts — never an LLM opinion
    status: str = "proposed"          # proposed | accepted | rejected  (human sets the rest)
```

Signals (deterministic, from `outcome.risk_materialized` + review corrections):

- Pattern's findings are consistently marked `false_positive` across many reviews → **downgrade
  candidate**.
- Pattern's findings never materialize across many recorded outcomes → **downgrade candidate**.
- Findings that materialized but were never flagged → **new-pattern candidate**.

Apply the same suppression discipline as `marketdata`: **no proposal below a minimum sample size**,
and the sample size travels with the proposal.

```python
def test_correction_loop_never_writes_a_pack(tmp_path):
    before = _hash_tree(RULEPACK_DIR)
    run_correction_loop(session)
    assert _hash_tree(RULEPACK_DIR) == before, "correction loop mutated a rulepack (Build Doc §2.4)"
```

---

## TS-234 — North-star metric: "verified contractor margin protected" — **P0**

Source: Research Doc §12.1; Roadmap §6.1. Deterministic computation, **never LLM**. This is the
number the whole company is steered by, so its credibility depends entirely on it being
conservative and auditable.

**Three components, all from *accepted, confirmed* records only:**

```python
@dataclass(frozen=True)
class MarginProtected:
    accepted_risk_allowances_minor: int   # pricing loadings on ACCEPTED findings, priced into the bid
    declined_bid_exposure_minor: int      # exposure on bids DECLINED after review
    boq_corrections_minor: int            # BOQ defects corrected PRE-submission
    total_minor: int
    currency: str
    excluded: list[str]                   # every category deliberately left out, named
    sample: dict                          # counts feeding each component, for audit
```

**Inclusion rules — be strict; the metric is worthless if it is inflated:**

| Include | Only when |
|---|---|
| Risk allowance | `finding.review_status == "accepted"` **and** a `pricing` loading was produced **and** the bid was submitted |
| Declined-bid exposure | `outcome.result == "declined"` **and** `confirmed=True` **and** the decline cites reviewed findings |
| BOQ correction | Defect found **and** corrected **before** submission, with the corrected value recorded |

**Explicitly excluded — and the exclusions must be returned in the payload, not just documented:**
speculative value; unaccepted/proposed findings; unconfirmed prefilled outcomes; anything from an
Express (`unreviewed`) report; claims recovery (that arrives with Phase 19, TS-269).

```python
def compute(...) -> MarginProtected:
    ...
    return MarginProtected(
        ...,
        excluded=[
            "proposed_findings", "unconfirmed_outcomes", "unreviewed_express_reports",
            "speculative_future_savings", "claims_recovery_pending_phase_19",
        ],
        sample={"accepted_findings": n1, "declined_bids": n2, "boq_corrections": n3},
    )
```

Money: minor units, integer arithmetic, **one rounding at the end** — the same discipline
`app/core/costmeter.py` already applies. Mixed currencies must not be summed silently; either scope
the metric per currency or fail loudly.

The metric **grows as Phases 18–19 land** (notified change value, certified value, recovered claim
value). Design the shape so components can be added without redefining the total.

**Acceptance:** deterministic (byte-identical on re-run); excludes speculative value, test-asserted;
every component traces to accepted/confirmed records; disabling `pricing` or `outcomes` degrades to
a partial metric with the missing component named in `excluded`, never a silent zero.
