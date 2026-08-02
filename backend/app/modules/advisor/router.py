"""Advisor Edition API (TS-290, TS-291)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.advisor.service import AdvisorError, AdvisorService

router = APIRouter()

_ERROR_STATUS = {
    "not_found": 404,
}


class CreateClientBody(BaseModel):
    client_workspace_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    billing_rate: str | None = None


class CreateReviewItemBody(BaseModel):
    client_workspace_id: str = Field(min_length=1)
    opportunity_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    assigned_to: str | None = None
    priority: int = 0
    status: str = "pending"
    due_date: date | None = None


class UpdateReviewStatusBody(BaseModel):
    status: str = Field(min_length=1)


class CreateTemplateBody(BaseModel):
    name: str = Field(min_length=1)
    client_workspace_id: str | None = None
    theme: dict | None = None
    header_text: str | None = None
    footer_text: str | None = None


def _service(request: Request, session: Session) -> AdvisorService:
    reg = request.app.state.ctx.registry
    return AdvisorService(
        session,
        billing_factory=reg.get("billing.service_factory"),
        publish=request.app.state.ctx.events.publish,
    )


def _raise(exc: AdvisorError):
    raise HTTPException(_ERROR_STATUS.get(exc.code, 400), exc.code) from exc


@router.get("/status")
def status() -> dict:
    return {"module": "advisor", "status": "ready"}


@router.post("/clients")
def create_client(
    body: CreateClientBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        row = _service(request, session).create_client(
            principal.workspace_id,
            client_workspace_id=body.client_workspace_id,
            name=body.name,
            billing_rate=body.billing_rate,
        )
    except AdvisorError as exc:
        _raise(exc)
    return {"id": str(row.id), "name": row.name}


@router.get("/clients")
def list_clients(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    rows = _service(request, session).list_clients(principal.workspace_id)
    return {"clients": [{"id": str(r.id), "name": r.name} for r in rows]}


@router.get("/clients/{client_id}/usage")
def client_usage(
    client_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).client_usage(principal.workspace_id, client_id)
    except AdvisorError as exc:
        _raise(exc)


@router.post("/review-queue/items")
def create_review_item(
    body: CreateReviewItemBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        row = _service(request, session).create_review_item(
            principal.workspace_id,
            client_workspace_id=body.client_workspace_id,
            opportunity_id=body.opportunity_id,
            title=body.title,
            assigned_to=body.assigned_to,
            priority=body.priority,
            status=body.status,
            due_date=body.due_date,
        )
    except AdvisorError as exc:
        _raise(exc)
    return {"id": str(row.id), "title": row.title}


@router.get("/review-queue")
def list_review_items(
    request: Request,
    status: str | None = None,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    rows = _service(request, session).list_review_items(principal.workspace_id, status=status)
    return {"items": [{"id": str(r.id), "title": r.title, "status": r.status} for r in rows]}


@router.post("/review-queue/{item_id}/status")
def update_review_status(
    item_id: str,
    body: UpdateReviewStatusBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        row = _service(request, session).update_review_item_status(
            principal.workspace_id, item_id, body.status
        )
    except AdvisorError as exc:
        _raise(exc)
    return {"id": str(row.id), "status": row.status}


@router.post("/templates")
def create_template(
    body: CreateTemplateBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    row = _service(request, session).create_template(
        principal.workspace_id,
        name=body.name,
        client_workspace_id=body.client_workspace_id,
        theme=body.theme,
        header_text=body.header_text,
        footer_text=body.footer_text,
    )
    return {"id": str(row.id), "name": row.name}


@router.get("/templates")
def list_templates(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    rows = _service(request, session).list_templates(principal.workspace_id)
    return {"templates": [{"id": str(r.id), "name": r.name} for r in rows]}


@router.get("/templates/{template_id}/config")
def template_config(
    template_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).template_config(principal.workspace_id, template_id)
    except AdvisorError as exc:
        _raise(exc)
