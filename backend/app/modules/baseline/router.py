from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import audit as audit_log
from app.core.deps import get_session, require
from app.core.pagination import PaginationParams, paginated_list_response
from app.core.storage import StorageError, ValidationError, sanitize_filename, validate_and_store
from app.modules.baseline.service import BaselineError, BaselineService
from app.modules.baseline.watchlist import control_dict

router = APIRouter()

_ERROR_STATUS = {
    "review_incomplete": 403,
    "review_unavailable": 503,
    "findings_unavailable": 503,
    "ingestion_unavailable": 503,
    "not_found": 404,
    "opportunity_not_found": 404,
    "no_baseline": 404,
    "need_two_baselines": 409,
    "bad_source": 400,
    "bad_status": 400,
    "export_unavailable": 503,
    "approval_denied": 403,
}


def _service(request: Request, session: Session) -> BaselineService:
    reg = request.app.state.ctx.registry
    return BaselineService(
        session,
        findings_factory=reg.get("findings.store_factory"),
        review_factory=reg.get("review.service_factory"),
        ingestion_factory=reg.get("ingestion.service_factory"),
        segment_clauses_fn=reg.get("ingestion.segment_clauses"),
        loader_provider=lambda: reg.get("rulepacks.loader"),
        standards_factory=reg.get("standards.org_notice_provider"),
        export_factory=reg.get("export.service_factory"),
        approval_matrix_factory=reg.get("auth.approval_matrix"),
        publish=request.app.state.ctx.events.publish,
    )


def _raise(exc: BaselineError):
    raise HTTPException(_ERROR_STATUS.get(exc.code, 400), exc.code) from exc


def _baseline_dict(row) -> dict:
    return {
        "id": str(row.id),
        "version": row.version,
        "source": row.source,
        "content_sha256": row.content_sha256,
        "note": row.note,
        "sealed_at": row.sealed_at.isoformat() if row.sealed_at else None,
        "counts": row.snapshot.get("counts", {}),
    }


class FreezeBody(BaseModel):
    source: str = "tender"  # tender | award
    note: str | None = None


class WatchlistBody(BaseModel):
    owner_user_id: str | None = None
    trigger_text: str | None = None
    review_cadence: str | None = None
    status: str | None = None


class NoticeContactEntry(BaseModel):
    notice_type: str
    party: str = "employer"
    role_label: str | None = None
    authorized_representative: str | None = None
    postal_address: str | None = None
    email: str | None = None
    required_content: list[str] | None = None


class NoticeContactsBody(BaseModel):
    contacts: list[NoticeContactEntry]


class CostCodeEntry(BaseModel):
    id: str | None = None
    parent_id: str | None = None
    code: str
    label: str
    variation_category: str | None = None


class CostCodeMappingEntry(BaseModel):
    id: str | None = None
    cost_code_id: str
    boq_src_row: str | None = None
    finding_id: str | None = None
    description_match: str | None = None


class CostCodesBody(BaseModel):
    codes: list[CostCodeEntry]
    mappings: list[CostCodeMappingEntry] = []


@router.post("/opportunities/{opportunity_id}/freeze")
def freeze(
    opportunity_id: str,
    body: FreezeBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("reviewer")),
):
    try:
        row = _service(request, session).freeze(
            principal.workspace_id,
            opportunity_id,
            source=body.source,
            note=body.note,
            sealer_id=principal.user_id,
        )
    except BaselineError as exc:
        _raise(exc)
    return _baseline_dict(row)


@router.post("/opportunities/{opportunity_id}/award-document")
async def upload_award_document(
    opportunity_id: str,
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    principal: Any = Depends(require("reviewer")),
):
    """Upload a negotiated contract / award letter so the award baseline seals from
    real award text."""
    data = await file.read()
    try:
        stored = await validate_and_store(
            request.app.state.ctx.settings,
            file.filename,
            file.content_type,
            data,
            workspace_id=str(principal.workspace_id),
        )
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(500, str(exc)) from exc
    try:
        doc = _service(request, session).store_award_document(
            principal.workspace_id,
            opportunity_id,
            file.filename,
            data,
            uploaded_by=principal.user_id,
        )
    except BaselineError as exc:
        _raise(exc)
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "chars": len(doc.text),
        "sha256": doc.sha256,
        "s3_key": stored.get("key"),
    }


@router.get("/opportunities/{opportunity_id}/baselines")
def list_baselines(
    opportunity_id: str,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    page: PaginationParams = Depends(),
):
    rows = _service(request, session).list(principal.workspace_id, opportunity_id)
    items = [_baseline_dict(r) for r in rows]
    return {"baselines": paginated_list_response(items, page, response)}


@router.get("/baselines/{baseline_id}")
def get_baseline(
    baseline_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    row = _service(request, session).get(principal.workspace_id, baseline_id)
    if row is None:
        raise HTTPException(404, "not_found")
    return {**_baseline_dict(row), "snapshot": row.snapshot}


@router.get("/baselines/{baseline_id}/verify")
def verify_baseline(
    baseline_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).verify(principal.workspace_id, baseline_id)
    except BaselineError as exc:
        _raise(exc)


@router.get("/opportunities/{opportunity_id}/notice-register")
def notice_register(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).notice_register(principal.workspace_id, opportunity_id)
    except BaselineError as exc:
        _raise(exc)


@router.put("/opportunities/{opportunity_id}/notice-register/contacts")
def update_notice_contacts(
    opportunity_id: str,
    body: NoticeContactsBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        contacts = _service(request, session).upsert_notice_contacts(
            principal.workspace_id,
            opportunity_id,
            [c.model_dump() for c in body.contacts],
            actor_user_id=principal.user_id,
            actor_role=principal.role,
        )
    except BaselineError as exc:
        _raise(exc)
    return {"contacts": contacts}


@router.get("/opportunities/{opportunity_id}/cost-codes")
def list_cost_codes(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).list_cost_codes(principal.workspace_id, opportunity_id)
    except BaselineError as exc:
        _raise(exc)


@router.post("/opportunities/{opportunity_id}/cost-codes")
def upsert_cost_codes(
    opportunity_id: str,
    body: CostCodesBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).upsert_cost_codes(
            principal.workspace_id,
            opportunity_id,
            codes=[c.model_dump() for c in body.codes],
            mappings=[m.model_dump() for m in body.mappings],
            actor_role=principal.role,
        )
    except BaselineError as exc:
        _raise(exc)


@router.get("/opportunities/{opportunity_id}/compare/award")
def compare_award(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).compare_award(principal.workspace_id, opportunity_id)
    except BaselineError as exc:
        _raise(exc)


@router.get("/opportunities/{opportunity_id}/compare")
def compare(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).compare(principal.workspace_id, opportunity_id)
    except BaselineError as exc:
        _raise(exc)


@router.get("/opportunities/{opportunity_id}/watchlist")
def watchlist(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return {
        "controls": _service(request, session).list_watchlist(
            principal.workspace_id, opportunity_id
        )
    }


@router.put("/watchlist/{control_id}")
def update_watchlist(
    control_id: str,
    body: WatchlistBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        row = _service(request, session).update_watchlist(
            principal.workspace_id,
            control_id,
            owner_user_id=body.owner_user_id,
            trigger_text=body.trigger_text,
            review_cadence=body.review_cadence,
            status=body.status,
            actor_role=principal.role,
        )
    except BaselineError as exc:
        _raise(exc)
    return control_dict(row)


@router.get("/opportunities/{opportunity_id}/handover")
def handover(
    opportunity_id: str,
    view: str | None = None,
    request: Request = None,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).handover(
            principal.workspace_id, opportunity_id, view=view
        )
    except BaselineError as exc:
        _raise(exc)


@router.get("/opportunities/{opportunity_id}/handover/export")
def handover_export(
    opportunity_id: str,
    format: str = "docx",
    view: str | None = None,
    request: Request = None,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    """Download the sealed handover pack as a DOCX/PDF/XLSX file."""
    try:
        filename, media_type, data = _service(request, session).export_handover(
            principal.workspace_id, opportunity_id, format, view=view
        )
    except BaselineError as exc:
        _raise(exc)
    audit_log.log(
        request,
        session,
        workspace_id=principal.workspace_id,
        actor_user_id=principal.user_id,
        action="export.handover_created",
        object_type="opportunity",
        object_id=opportunity_id,
        detail={"format": format, "filename": filename, "view": view or "full"},
    )
    safe = sanitize_filename(filename)
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )
