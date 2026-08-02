"""Integrations API (TS-281–TS-287)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.integrations.service import IntegrationsError, IntegrationsService

router = APIRouter()

_ERROR_STATUS = {
    "unknown_adapter": 400,
    "unknown_connector": 400,
    "connector_not_configured": 503,
    "invalid_state": 400,
    "source_not_found": 404,
    "dynamic_config_not_found": 404,
    "no_such_opportunity": 404,
    "ingestion_unavailable": 503,
    "change_unavailable": 503,
    "import_failed": 422,
    "invalid_url": 400,
}


class CreateSourceBody(BaseModel):
    adapter_kind: str = Field(min_length=1)
    name: str = Field(min_length=1)
    opportunity_id: str | None = None
    config: dict | None = None
    rate_limit_calls_per_minute: int | None = None


class ImportPayload(BaseModel):
    payload: dict


class ScheduleImportBody(BaseModel):
    opportunity_id: str
    format: str = "csv"  # csv | ms_project_xml | p6_xer
    content: str
    source_id: str | None = None


def _service(request: Request, session: Session) -> IntegrationsService:
    reg = request.app.state.ctx.registry
    return IntegrationsService(
        session,
        ingestion_factory=reg.get("ingestion.service_factory"),
        change_factory=reg.get("change.service_factory"),
        publish=request.app.state.ctx.events.publish,
        live_connector_polling_enabled=request.app.state.ctx.settings.live_connector_polling_enabled,
    )


def _raise(exc: IntegrationsError):
    raise HTTPException(_ERROR_STATUS.get(exc.code, 400), exc.code) from exc


@router.get("/status")
def status() -> dict:
    return {"module": "integrations", "status": "ready"}


@router.post("/sources")
def create_source(
    body: CreateSourceBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        row = _service(request, session).create_source(
            principal.workspace_id,
            adapter_kind=body.adapter_kind,
            name=body.name,
            created_by=principal.user_id,
            opportunity_id=body.opportunity_id,
            config=body.config,
            rate_limit=body.rate_limit_calls_per_minute,
        )
    except IntegrationsError as exc:
        _raise(exc)
    return {"id": str(row.id), "adapter_kind": row.adapter_kind, "name": row.name}


@router.get("/sources")
def list_sources(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    rows = _service(request, session).list_sources(principal.workspace_id)
    return {"sources": [_service(request, session)._source_dict(r) for r in rows]}


@router.post("/sources/{source_id}/import")
def import_source(
    source_id: str,
    body: ImportPayload,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).import_from_source(
            principal.workspace_id,
            source_id,
            principal.user_id,
            body.payload,
        )
    except IntegrationsError as exc:
        _raise(exc)


@router.get("/sources/{source_id}/jobs")
def list_jobs(
    source_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return {"jobs": _service(request, session).list_jobs(principal.workspace_id, source_id)}
    except IntegrationsError as exc:
        _raise(exc)


@router.get("/sources/{source_id}/documents")
def list_documents(
    source_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        docs = _service(request, session).list_documents(principal.workspace_id, source_id)
        return {"documents": docs}
    except IntegrationsError as exc:
        _raise(exc)


@router.get("/sources/{source_id}/events")
def list_events(
    source_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return {"events": _service(request, session).list_events(principal.workspace_id, source_id)}
    except IntegrationsError as exc:
        _raise(exc)


@router.post("/schedule/import")
def import_schedule(
    body: ScheduleImportBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).import_schedule(
            principal.workspace_id,
            principal.user_id,
            body.opportunity_id,
            {"format": body.format, "content": body.content},
            source_id=body.source_id,
        )
    except IntegrationsError as exc:
        _raise(exc)


@router.get("/schedule/opportunities/{opportunity_id}/activities")
def list_schedule_activities(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return {
        "activities": _service(request, session).list_schedule_activities(
            principal.workspace_id, opportunity_id
        )
    }


@router.post("/schedule/opportunities/{opportunity_id}/snapshot")
def snapshot_schedule(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    return _service(request, session).snapshot_schedule(
        principal.workspace_id, opportunity_id, principal.user_id
    )


@router.post("/schedule/opportunities/{opportunity_id}/upload")
async def upload_schedule(
    request: Request,
    opportunity_id: str,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
    format: str = "csv",  # csv | ms_project_xml | p6_xer | ifc
    file: UploadFile = File(...),
):
    data = await file.read()
    try:
        content = data.decode("utf-8", errors="ignore")
    except Exception as exc:
        raise HTTPException(400, "invalid_schedule_file") from exc
    try:
        return _service(request, session).import_schedule(
            principal.workspace_id,
            principal.user_id,
            opportunity_id,
            {"format": format, "content": content},
        )
    except IntegrationsError as exc:
        _raise(exc)


@router.get("/connectors")
def list_connectors(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    return {"connectors": _service(request, session).list_connectors()}


@router.get("/adapters")
def list_adapters(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    return {"adapters": _service(request, session).list_adapters()}


class OAuthStartBody(BaseModel):
    redirect_uri: str = Field(min_length=1)


@router.post("/sources/{source_id}/oauth")
def start_oauth(
    source_id: str,
    body: OAuthStartBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _service(request, session).oauth_start(
            principal.workspace_id, source_id, body.redirect_uri
        )
    except IntegrationsError as exc:
        _raise(exc)


@router.get("/connectors/{connector_kind}/callback")
def oauth_callback(
    connector_kind: str,
    code: str,
    state: str,
    request: Request,
    session: Session = Depends(get_session),
):
    try:
        return _service(request, session).oauth_callback(connector_kind, code, state)
    except IntegrationsError as exc:
        _raise(exc)


@router.post("/sources/{source_id}/poll")
def poll_source(
    source_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _service(request, session).poll_source(
            principal.workspace_id, source_id, principal.user_id
        )
    except IntegrationsError as exc:
        _raise(exc)


@router.post("/sources/{source_id}/webhook")
def receive_webhook(
    source_id: str,
    payload: dict,
    request: Request,
    session: Session = Depends(get_session),
):
    try:
        return _service(request, session).handle_webhook(source_id, payload)
    except IntegrationsError as exc:
        _raise(exc)


# ---- dynamic REST connector (TS-334) ------------------------------------


@router.get("/dynamic-connectors")
def list_dynamic_connectors(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    return {
        "connectors": _service(request, session).list_dynamic_connectors(
            principal.workspace_id
        )
    }


@router.post("/dynamic-connectors")
def create_dynamic_connector(
    request: Request,
    payload: dict,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _service(request, session).create_dynamic_connector(
            principal.workspace_id, principal.user_id, payload
        )
    except IntegrationsError as exc:
        _raise(exc)


@router.get("/dynamic-connectors/{config_id}")
def get_dynamic_connector(
    config_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).get_dynamic_connector(principal.workspace_id, config_id)
    except IntegrationsError as exc:
        _raise(exc)


@router.put("/dynamic-connectors/{config_id}")
def update_dynamic_connector(
    config_id: str,
    request: Request,
    payload: dict,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _service(request, session).update_dynamic_connector(
            principal.workspace_id, config_id, payload
        )
    except IntegrationsError as exc:
        _raise(exc)


@router.delete("/dynamic-connectors/{config_id}")
def delete_dynamic_connector(
    config_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _service(request, session).delete_dynamic_connector(
            principal.workspace_id, config_id
        )
    except IntegrationsError as exc:
        _raise(exc)


@router.post("/dynamic-connectors/{config_id}/test")
def test_dynamic_connector(
    config_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _service(request, session).test_dynamic_connector(principal.workspace_id, config_id)
    except IntegrationsError as exc:
        _raise(exc)


@router.post("/dynamic-connectors/{config_id}/poll")
def poll_dynamic_connector(
    config_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _service(request, session).poll_dynamic_connector(
            principal.workspace_id, config_id, principal.user_id
        )
    except IntegrationsError as exc:
        _raise(exc)
