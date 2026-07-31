"""Read-only marketdata routes (TS-195/198/199)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.marketdata.service import MarketDataService

router = APIRouter()


def _service(request: Request, session: Session) -> MarketDataService:
    factory = request.app.state.ctx.registry.get("marketdata.service_factory")
    return factory(session) if factory else MarketDataService(session)


@router.get("")
def status() -> dict:
    return {
        "module": "marketdata",
        "status": "ready",
        "note": "Employer resolution and aggregates active (TS-198/199)",
    }


@router.get("/employers/{family}/profile")
def employer_profile(
    family: str,
    request: Request,
    session: Session = Depends(get_session),
    _principal: Any = Depends(require("viewer")),
):
    return _service(request, session).employer_profile(family)


@router.get("/opportunities/{opportunity_id}/employer-context")
def employer_context(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    from app.core.contracts.employer_context import employer_context_for_opportunity

    ctx = employer_context_for_opportunity(
        request.app.state.ctx.registry,
        session,
        workspace_id=principal.workspace_id,
        opportunity_id=opportunity_id,
    )
    return {"opportunity_id": opportunity_id, "employer_context": ctx}


@router.get("/opportunities/{opportunity_id}/comparables")
def comparables(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).comparable_awards(
        opportunity_id,
        workspace_id=principal.workspace_id,
    )


@router.get("/opportunities/{opportunity_id}/benchmark")
def benchmark(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).price_benchmark(
        opportunity_id,
        workspace_id=principal.workspace_id,
    )
