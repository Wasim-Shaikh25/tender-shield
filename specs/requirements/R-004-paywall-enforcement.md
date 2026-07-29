# R-004 — Paywall enforcement and the free-tier watermark

**Status:** draft
**Severity:** P0 — the product cannot charge for anything today
**Requirement refs:** Doc §7, §15, §11.4
**Task refs:** TS-087 (metering), TS-088 (watermark)
**Task files:** code-level detail (current-vs-target snippets, file:line, files touched, tests) now lives per-task, split out by TS-126's restructure: [TS-087](../../tasks/specs/TS-087-meter-review-path.md), [TS-088](../../tasks/specs/TS-088-export-watermark.md). This document stays the business/behavior-level record (purpose, target behavior, acceptance criteria).

**Gap refs:** `docs/GAP_ANALYSIS.md` §2.1, §2.2
**Specs to update:** `specs/modules/billing.md`, `specs/modules/risk.md`, `specs/modules/export.md`

## Purpose

`BillingService.authorize_review` contains correct, tested paywall logic that
**nothing in the review path calls**, and `Grant.watermark` is computed and
thrown away. Together these mean: unlimited free reviews, producing clean
paid-grade output. This is the single highest-value fix in the repo — every
other billing task is worthless until it lands.

---

## Part A — Meter the review path (TS-087)

### A.1 Current

```python
# backend/app/modules/billing/module.py:6
def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    # Metering consumed by risk/ingestion before starting a review (Doc §7).
    reg.provide("billing.service_factory", lambda session: BillingService(...))
```

The capability is published with a comment stating exactly what should consume
it. Nothing does:

```console
$ grep -rn "authorize_review" backend/app
app/modules/billing/service.py:52:    def authorize_review(self, workspace_id) -> Grant:
app/modules/billing/router.py:59:def authorize_review(
app/modules/billing/router.py:65:        grant = _service(request, session).authorize_review(...)
```

`POST /api/risk/opportunities/{id}/run` (`risk/router.py:23`) — the endpoint that
performs the work being sold — goes straight to `RiskService.run_opportunity`.
The frontend never calls `/billing/authorize-review` either (`lib/api.ts` has no
billing calls at all), so the paywall is an opt-in courtesy nobody opts into.

### A.2 Target — a guard dependency, resolved by capability

The module rule (`CLAUDE.md` §2) forbids `risk` importing `billing`. Metering
therefore travels as a registry capability, consumed through a shared dependency
in `app/core/` so any module can gate a billable action identically.

```python
# backend/app/core/deps.py  (append)

def meter(event: str):
    """Gate a billable action through the billing capability (Doc §7).

    Resolved by name so no module imports billing. When billing is disabled the
    action proceeds unmetered and a warning is logged — the app must boot with
    any module subset (spec core B2), but a disabled billing module must never
    silently become a free tier in production.
    """

    def guard(
        request: Request,
        session: Session = Depends(get_session),
        principal: Any = Depends(current_principal),
    ) -> Any:
        factory = request.app.state.ctx.registry.get("billing.service_factory")
        if factory is None:
            if request.app.state.ctx.settings.env == "production":
                raise HTTPException(503, "billing_unavailable")
            logger.warning("billing module disabled — %r proceeding unmetered", event)
            return None
        try:
            return factory(session).authorize_review(principal.workspace_id)
        except Exception as exc:   # PaywallError, resolved structurally
            code = getattr(exc, "code", None)
            if code is None:
                raise
            raise HTTPException(402, detail={"code": code, "upsell": getattr(exc, "upsell", {})}) from exc

    return guard
```

`PaywallError` is caught structurally (`getattr(exc, "code", ...)`) rather than
by import, keeping `app.core` free of module imports.

Applied at the billable boundary:

```python
# backend/app/modules/risk/router.py

@router.post("/opportunities/{opportunity_id}/run")
def run(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
    grant: Any = Depends(meter("review_started")),      # ← 402 before any work
):
    ...
    findings = _service(request, session).run_opportunity(principal.workspace_id, opportunity_id)
    return {"count": len(findings), "watermark": bool(grant and grant.watermark), "findings": [...]}
```

### A.3 Which actions are billable

Doc §7 B1: *"a review is metered at processing start, not export; addendum
re-processing on a metered opportunity is free."* The current
`authorize_review(workspace_id)` signature cannot express that second clause —
it has no opportunity id, so it cannot tell a first run from a re-run.

```python
def authorize_review(self, workspace_id, opportunity_id=None) -> Grant:
    """Meter a review at processing start (Doc §7 B1).

    Re-processing an opportunity that has already been metered is free — an
    addendum must never cost a second review, or customers stop uploading
    addenda, which is the exact failure the product exists to prevent.
    """
    if opportunity_id is not None and self._already_metered(workspace_id, opportunity_id):
        return Grant(kind="already_metered")
    ...

def _already_metered(self, workspace_id, opportunity_id) -> bool:
    return self.s.scalar(
        select(UsageEvent.id).where(
            UsageEvent.workspace_id == uuid.UUID(str(workspace_id)),
            UsageEvent.event == "review_started",
            UsageEvent.ref_id == uuid.UUID(str(opportunity_id)),
        ).limit(1)
    ) is not None
```

| Action | Route | Billable |
|---|---|---|
| Run risk review | `POST /risk/opportunities/{id}/run` | **yes** — the metering point |
| Run BOQ checks | `POST /boq/opportunities/{id}/run` | no — same review, already metered |
| Upload document | `POST /ingestion/.../upload` | no — metered at processing |
| Generate artifact | `POST /drafting/.../artifacts` | no |
| Export pack | `GET /export/opportunities/{id}` | no — gated by review, not by money |
| Assistant chat | `POST /assistant/chat` | no in v1 (`assumption:` watch LLM cost, R-016) |

Metering the review and not the export is deliberate: the export gate is a
*quality* control (Doc §11.4) and must never be conflated with a *payment* gate,
or a paying customer who hasn't finished review looks like a payment failure.

### A.4 Race-safety

`specs/modules/billing.md` B2 promises "authorization under a per-org advisory
lock". There is no lock. Two concurrent review starts both read
`free_review_used == False` and both pass.

```python
def authorize_review(self, workspace_id, opportunity_id=None) -> Grant:
    self._lock(workspace_id)          # serialise per workspace
    ...

def _lock(self, workspace_id) -> None:
    """Serialise metering per workspace so concurrent starts cannot both spend
    the single free review (specs/modules/billing.md B2)."""
    if self.s.get_bind().dialect.name != "postgresql":
        return                        # SQLite tests are single-threaded
    key = int(uuid.UUID(str(workspace_id)).int & 0x7FFFFFFFFFFFFFFF)
    self.s.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})
```

`pg_advisory_xact_lock` releases with the transaction, so it needs the metering
read *and* the `mark_free_review_used` write inside one transaction —
`WorkspaceAdmin.mark_free_review_used` currently commits on its own
(`workspaces.py:23`), which breaks the lock. Move the commit up to the caller.

Belt and braces, add the constraint that makes double-spend impossible
regardless:

```sql
CREATE UNIQUE INDEX uq_usage_free_review
    ON usage_events (workspace_id)
    WHERE event = 'free_review_used';
```

### A.5 Events

`specs/modules/billing.md` declares `billing.plan_activated`,
`billing.payment_applied` and `billing.paywall_hit`. None are published. Emit
them — analytics (R-016 §D) needs `paywall_hit` to measure conversion:

```python
ctx.events.publish("billing.paywall_hit", {
    "workspace_id": str(workspace_id), "code": exc.code, "plan": workspace.plan,
})
```

---

## Part B — Apply the watermark (TS-088)

### B.1 Current

```python
# backend/app/modules/billing/plans.py:52
return Grant(kind="free_review_first", watermark=True)
```

```console
$ grep -rn "watermark" backend/app
app/modules/billing/router.py:70:        "watermark": grant.watermark,
app/modules/billing/plans.py:31:    watermark: bool = False
app/modules/billing/plans.py:52:        return Grant(kind="free_first_review", watermark=True)
```

Nothing in `export/render.py` consumes it. The free review therefore produces a
clean, unwatermarked, fully sellable Bid Review Pack.

This matters more here than in most products. Doc §706 deliberately makes the
free review *complete* — "crippled trials die in contractor WhatsApp groups, and
those groups are the GTM". The watermark is the **only** thing separating free
output from paid output. Without it there is no reason to ever pay.

### B.2 Target — watermark decided server-side at export time

The client must not tell the server whether to watermark. Derive it from
workspace state:

```python
# backend/app/modules/billing/service.py

def export_entitlement(self, workspace_id) -> dict:
    """Whether this workspace's exports carry the free-tier watermark (Doc §7).

    Free plan → watermarked, forever, including re-exports of the one free
    review. Any paid plan → clean.
    """
    workspace = self._workspaces().get(workspace_id)
    return {"watermark": bool(workspace and workspace.plan == "free")}
```

Published as `billing.export_entitlement` and consumed by export:

```python
# backend/app/modules/export/service.py

def export(self, workspace_id, opportunity_id, fmt: str) -> tuple[str, str, bytes]:
    if fmt not in FORMATS:
        raise ExportError("bad_format")
    if not self._gate_ok(workspace_id, opportunity_id):
        raise ExportError("review_incomplete")

    meta = {
        "date": date.today().isoformat(),
        "pack": self._pack_version,
        "watermark": self._watermark(workspace_id),      # ← new
    }
    ...

def _watermark(self, workspace_id) -> bool:
    ent = self._billing_entitlement          # registry capability, may be absent
    return bool(ent(self.s, workspace_id).get("watermark")) if ent else False
```

### B.3 Renderer changes

`render.py` already has the right seam — `stamp_line(meta)` is called by all
three renderers.

```python
WATERMARK_TEXT = "FREE REVIEW — TenderShield · not for external issue"


def stamp_line(meta: dict) -> str:
    base = (
        f"Prepared with TenderShield · reviewed and approved on {meta.get('date', '')} "
        f"· pack {meta.get('pack', 'in-works')} · This is document-intelligence "
        f"software, not legal/QS advice — review with a qualified professional."
    )
    return f"{WATERMARK_TEXT} · {base}" if meta.get("watermark") else base
```

A stamp line alone is too easy to delete. Add a visible mark per format:

```python
# XLSX — repeat in a frozen header row and in the page header of every sheet
if meta.get("watermark"):
    ws.oddHeader.center.text = WATERMARK_TEXT
    ws["A1"].font = Font(color="FF999999", bold=True)

# DOCX — diagonal WordArt-style watermark in the section header
if meta.get("watermark"):
    _add_docx_watermark(doc, WATERMARK_TEXT)

# PDF — diagonal grey text on every page via onPage callback
def _stamp_page(canvas, doc_):
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 48)
    canvas.setFillGray(0.87)
    canvas.translate(A4[0] / 2, A4[1] / 2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, "FREE REVIEW")
    canvas.restoreState()

doc.build(flow, onFirstPage=_stamp_page, onLaterPages=_stamp_page)
```

### B.4 Do not watermark the truth

The watermark marks the *document*, never the *content*. Findings, quotes, page
citations and severities are identical between free and paid output. Degrading
content would violate the product invariant that every displayed fact is
quote-verified, and would break the GTM described above.

## Behavior

- **B1** A billable action is authorized before any processing begins; a blocked
  action returns `402` with `{code, upsell}` and performs no work.
- **B2** Re-processing an already-metered opportunity is free.
- **B3** Metering is serialised per workspace; the free review cannot be
  double-spent under concurrency.
- **B4** Paygo grants require a confirmed payment before processing (R-005).
- **B5** Exports from a `free`-plan workspace carry a visible watermark in all
  three formats; paid plans never do.
- **B6** The watermark decision is server-side and derived from workspace plan
  state; no client input affects it.
- **B7** Free and paid exports contain identical findings and citations.
- **B8** `billing.paywall_hit`, `billing.plan_activated` and
  `billing.payment_applied` are published on the event bus.

## Acceptance criteria

- **A1** A `free` workspace that has used its free review gets `402
  free_exhausted` from `POST /risk/opportunities/{id}/run`, and no findings rows
  are written.
- **A2** A `pro` workspace at 10 reviews this month gets `402 quota_exhausted`.
- **A3** Re-running risk on an already-metered opportunity succeeds and creates
  no second `review_started` usage event.
- **A4** Two concurrent first reviews on a `free` workspace produce exactly one
  `review_started` event; one returns `402`.
- **A5** With `TS_ENABLED_MODULES` excluding `billing`, the app boots and
  `POST /risk/.../run` succeeds in dev, and returns `503` when
  `TS_ENV=production`.
- **A6** XLSX/DOCX/PDF exports from a free workspace contain `WATERMARK_TEXT`;
  from a `pro` workspace they do not.
- **A7** The findings list in a free export equals the findings list in a paid
  export for the same opportunity.
- **A8** `billing.paywall_hit` fires once per 402.

## Test sketch

```python
def test_free_review_is_metered_at_the_review_endpoint(client, headers):
    # first run: allowed, watermarked
    r1 = client.post(f"/api/risk/opportunities/{opp}/run", headers=headers)
    assert r1.status_code == 200 and r1.json()["watermark"] is True

    # second opportunity, same workspace: paywalled
    r2 = client.post(f"/api/risk/opportunities/{opp2}/run", headers=headers)
    assert r2.status_code == 402
    assert r2.json()["detail"]["code"] == "free_exhausted"
    assert r2.json()["detail"]["upsell"]["paygo_price_inr_paise"] == 750_000

    # and nothing was processed
    assert client.get(f"/api/findings/opportunities/{opp2}", headers=headers).json()["findings"] == []
```

## Out of scope

- Order creation and payment capture — R-005.
- Seat and storage entitlements — R-009.
- The paywall UI — R-008.

## Assumptions

- `assumption:` The assistant is not metered in v1. Revisit if LLM spend per
  workspace exceeds the review margin (tracked in R-016 §C).
