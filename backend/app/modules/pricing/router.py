"""API routes for `pricing` (TS-201, spec §Public interface).

`GET /loading` per the spec's stated method — since neither `Finding.facts` nor
`Opportunity.contract_value_minor` are persisted yet (see `loading.py`'s
docstring, and the follow-up filed as a Phase 16 task), the caller supplies
both as query parameters for now. Rate benchmarking is `POST`, not the spec's
literal `GET`: it carries a BOQ CSV body, and a GET request body is unreliable
across HTTP clients/proxies — the same reasoning `boq/router.py`'s own
`run_boq` already applies.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.pricing.cashflow import CashflowInputs
from app.modules.pricing.service import PricingError, PricingService

router = APIRouter()


def _service(request: Request, session: Session) -> PricingService:
    reg = request.app.state.ctx.registry
    return PricingService(
        session,
        findings_factory=reg.get("findings.store_factory"),
        rulepacks_loader_provider=lambda: reg.get("rulepacks.loader"),
        boq_engine_provider=lambda: reg.get("boq.engine"),
        review_factory=reg.get("review.service_factory"),
    )


@router.get("/opportunities/{opportunity_id}/loading")
def get_loading(
    opportunity_id: str,
    request: Request,
    contract_value_minor: int,
    currency: str = "INR",
    facts: str | None = None,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    facts_by_finding: dict[str, dict] = {}
    if facts:
        try:
            facts_by_finding = json.loads(facts)
        except json.JSONDecodeError as exc:
            raise HTTPException(400, "invalid_facts_json") from exc
    try:
        loadings = _service(request, session).get_loadings(
            principal.workspace_id,
            opportunity_id,
            contract_value_minor=contract_value_minor,
            currency=currency,
            facts_by_finding=facts_by_finding,
        )
    except PricingError as exc:
        raise HTTPException(409, exc.code) from exc
    return {"loadings": loadings}


class RateBenchmarkBody(BaseModel):
    csv: str = Field(..., max_length=10_000_000)
    authority: str | None = None
    year: str | None = None


@router.post("/opportunities/{opportunity_id}/rate-benchmark")
def rate_benchmark(
    opportunity_id: str,
    body: RateBenchmarkBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        result = _service(request, session).get_rate_benchmark(
            principal.workspace_id,
            opportunity_id,
            body.csv,
            authority=body.authority,
            year=body.year,
        )
    except PricingError as exc:
        raise HTTPException(409, exc.code) from exc
    except ValueError as exc:
        raise HTTPException(400, f"bad_boq: {exc}") from exc
    return result


class CashflowBody(BaseModel):
    contract_value_minor: int
    duration_months: int
    cost_of_capital_pa: float
    currency: str = "INR"
    payment_days: int | None = None
    retention_pct: float | None = None
    retention_release_month: int | None = None
    mobilization_advance_pct: float | None = None
    mobilization_recovery_months: int | None = None
    milestone_billing_minor: dict[int, int] | None = None


@router.post("/opportunities/{opportunity_id}/cashflow")
def cashflow(
    opportunity_id: str,
    body: CashflowBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    inputs = CashflowInputs(
        contract_value_minor=body.contract_value_minor,
        duration_months=body.duration_months,
        cost_of_capital_pa=body.cost_of_capital_pa,
        payment_days=body.payment_days,
        retention_pct=body.retention_pct,
        retention_release_month=body.retention_release_month,
        mobilization_advance_pct=body.mobilization_advance_pct,
        mobilization_recovery_months=body.mobilization_recovery_months,
        milestone_billing_minor=body.milestone_billing_minor,
    )
    try:
        result = _service(request, session).run_cashflow_for_opportunity(
            principal.workspace_id, opportunity_id, inputs, currency=body.currency
        )
    except PricingError as exc:
        raise HTTPException(409, exc.code) from exc
    return result
