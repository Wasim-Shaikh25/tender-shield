from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.ingestion.service import IngestionService

router = APIRouter()


def _service(request: Request, session: Session) -> IngestionService:
    reg = request.app.state.ctx.registry
    return IngestionService(
        session,
        loader_provider=lambda: reg.get("rulepacks.loader"),
        publish=request.app.state.ctx.events.publish,
    )


class CreateOpportunityBody(BaseModel):
    title: str = Field(min_length=1)
    employer: str | None = None
    employer_family: str | None = None
    jurisdiction: str = "IN"


class RegisterDocumentBody(BaseModel):
    filename: str = Field(min_length=1)
    sample_text: str = ""


@router.get("/opportunities")
def list_opportunities(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    opps = _service(request, session).list_opportunities(principal.org_id)
    return {
        "opportunities": [
            {"id": str(o.id), "title": o.title, "status": o.status} for o in opps
        ]
    }


@router.post("/opportunities")
def create_opportunity(
    body: CreateOpportunityBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    opp = _service(request, session).create_opportunity(
        principal.org_id,
        body.title,
        employer=body.employer,
        employer_family=body.employer_family,
        jurisdiction=body.jurisdiction,
    )
    return {"id": str(opp.id), "title": opp.title, "status": opp.status}


@router.get("/opportunities/{opportunity_id}")
def get_opportunity(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    opp = _service(request, session).get_opportunity(principal.org_id, opportunity_id)
    if not opp:
        raise HTTPException(404, "not_found")
    return {"id": str(opp.id), "title": opp.title, "status": opp.status}


@router.post("/opportunities/{opportunity_id}/documents")
def register_document(
    opportunity_id: str,
    body: RegisterDocumentBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    svc = _service(request, session)
    if not svc.get_opportunity(principal.org_id, opportunity_id):
        raise HTTPException(404, "not_found")
    doc = svc.register_document(
        principal.org_id, opportunity_id, body.filename, body.sample_text,
        uploaded_by=_to_uuid(principal.user_id),
    )
    return {"id": str(doc.id), "filename": doc.filename, "kind": doc.kind}


@router.get("/opportunities/{opportunity_id}/clauses")
def list_clauses(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    clauses = _service(request, session).list_clauses(principal.org_id, opportunity_id)
    return {
        "clauses": [
            {
                "id": str(c.id),
                "clause_ref": c.clause_ref,
                "heading": c.heading,
                "page_from": c.page_from,
                "cross_refs": c.cross_refs,
            }
            for c in clauses
        ]
    }


@router.get("/opportunities/{opportunity_id}/missing-docs")
def missing_docs(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).missing_doc_report(principal.org_id, opportunity_id)


def _to_uuid(value: str):
    import uuid

    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None
