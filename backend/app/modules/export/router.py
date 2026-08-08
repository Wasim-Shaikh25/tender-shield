from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import audit as audit_log
from app.core.deps import get_session, require
from app.core.storage import sanitize_filename
from app.modules.export.service import ExportError, ExportService

router = APIRouter()


class ReportTemplateBody(BaseModel):
    name: str = Field(min_length=1)
    report_title: str | None = Field(default=None)
    primary_color: str | None = Field(default=None)
    accent_color: str | None = Field(default=None)
    logo_url: str | None = Field(default=None)
    watermark_text: str | None = Field(default=None)
    footer_text: str | None = Field(default=None)
    is_default: bool = Field(default=False)


def _service(request: Request, session: Session, workspace_id) -> ExportService:
    reg = request.app.state.ctx.registry
    factory = reg.get("export.service_factory")
    if factory:
        return factory(session, workspace_id)
    loader = reg.get("rulepacks.loader")

    def _pack_version(session, workspace_id):
        if loader is None:
            return "in-works"
        return loader.get_pack(
            "in-works",
            session=session,
            workspace_id=workspace_id,
        ).version_tag

    return ExportService(
        session,
        review_factory=reg.get("review.service_factory"),
        findings_factory=reg.get("findings.store_factory"),
        drafting_factory=reg.get("drafting.service_factory"),
        ingestion_factory=reg.get("ingestion.service_factory"),
        workspace_factory=reg.get("auth.workspace_factory"),
        pack_version=_pack_version,
        document_class_permitted_fn=reg.get("auth.document_class_permitted"),
    )


@router.get("/opportunities/{opportunity_id}")
def export_pack(
    opportunity_id: str,
    request: Request,
    format: str = "xlsx",
    template_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        filename, media_type, data = _service(request, session, principal.workspace_id).export(
            principal.workspace_id,
            opportunity_id,
            format,
            template_id=template_id,
            role=principal.role,
        )
    except ExportError as exc:
        status = 403 if exc.code in ("review_incomplete", "document_class_forbidden") else 400
        raise HTTPException(status, exc.code) from exc
    audit_log.log(
        request,
        session,
        workspace_id=principal.workspace_id,
        actor_user_id=principal.user_id,
        action="export.pack_created",
        object_type="opportunity",
        object_id=opportunity_id,
        detail={"format": format, "filename": filename},
    )
    safe = sanitize_filename(filename)
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


@router.get("/templates")
def list_report_templates(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    svc = _service(request, session, principal.workspace_id)
    return {"templates": svc.list_templates(principal.workspace_id)}


@router.post("/templates")
def create_report_template(
    body: ReportTemplateBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    return _service(request, session, principal.workspace_id).create_template(
        principal.workspace_id, body.model_dump(exclude_unset=True)
    )


@router.put("/templates/{template_id}")
def update_report_template(
    template_id: str,
    body: ReportTemplateBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    result = _service(request, session, principal.workspace_id).update_template(
        principal.workspace_id, template_id, body.model_dump(exclude_unset=True)
    )
    if result is None:
        raise HTTPException(404, "not_found")
    return result


@router.delete("/templates/{template_id}")
def delete_report_template(
    template_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    svc = _service(request, session, principal.workspace_id)
    if not svc.delete_template(principal.workspace_id, template_id):
        raise HTTPException(404, "not_found")
    return {"deleted": True}


@router.post("/templates/{template_id}/default")
def set_default_report_template(
    template_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    svc = _service(request, session, principal.workspace_id)
    result = svc.set_default_template(principal.workspace_id, template_id)
    if result is None:
        raise HTTPException(404, "not_found")
    return result


@router.post("/opportunities/{opportunity_id}/email-summary")
def export_email_summary(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    """Generate email-ready summary for an opportunity.

    Returns JSON with subject, body (plaintext + HTML), mailto link, and preview.
    """
    try:
        email_data = _service(request, session, principal.workspace_id).email_summary(
            principal.workspace_id, opportunity_id, role=principal.role
        )
    except ExportError as exc:
        status = 403 if exc.code == "review_incomplete" else 400
        raise HTTPException(status, exc.code) from exc
    audit_log.log(
        request,
        session,
        workspace_id=principal.workspace_id,
        actor_user_id=principal.user_id,
        action="export.email_summary_generated",
        object_type="opportunity",
        object_id=opportunity_id,
    )
    return email_data


class ComparisonBody(BaseModel):
    version_1_date: str
    version_1_findings: list[dict] | None = None
    version_2_date: str | None = None
    version_2_findings: list[dict] | None = None


@router.post("/opportunities/{opportunity_id}/comparison-summary")
def export_comparison_summary(
    opportunity_id: str,
    body: ComparisonBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    """Generate comparison summary between two analysis versions.

    Shows new risks, resolved risks, escalated/de-escalated findings.
    If version_2_findings not provided, uses current findings.
    """
    try:
        comparison_data = _service(request, session, principal.workspace_id).comparison_summary(
            principal.workspace_id,
            opportunity_id,
            body.version_1_date,
            version_1_findings=body.version_1_findings,
            version_2_date=body.version_2_date,
            version_2_findings=body.version_2_findings,
        )
    except ExportError as exc:
        raise HTTPException(400, exc.code) from exc
    audit_log.log(
        request,
        session,
        workspace_id=principal.workspace_id,
        actor_user_id=principal.user_id,
        action="export.comparison_generated",
        object_type="opportunity",
        object_id=opportunity_id,
        detail={"v1_date": body.version_1_date, "v2_date": body.version_2_date},
    )
    return comparison_data
