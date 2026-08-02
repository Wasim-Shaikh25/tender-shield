from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core import audit as audit_log
from app.core.deps import get_session, require
from app.core.storage import sanitize_filename
from app.modules.export.service import ExportError, ExportService

router = APIRouter()


def _service(request: Request, session: Session) -> ExportService:
    reg = request.app.state.ctx.registry
    factory = reg.get("export.service_factory")
    if factory:
        return factory(session)
    loader = reg.get("rulepacks.loader")
    pack_version = loader.get_pack("in-works").version_tag if loader else "in-works"
    return ExportService(
        session,
        review_factory=reg.get("review.service_factory"),
        findings_factory=reg.get("findings.store_factory"),
        drafting_factory=reg.get("drafting.service_factory"),
        ingestion_factory=reg.get("ingestion.service_factory"),
        workspace_factory=reg.get("auth.workspace_factory"),
        pack_version=pack_version,
    )


@router.get("/opportunities/{opportunity_id}")
def export_pack(
    opportunity_id: str,
    request: Request,
    format: str = "xlsx",
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        filename, media_type, data = _service(request, session).export(
            principal.workspace_id, opportunity_id, format
        )
    except ExportError as exc:
        status = 403 if exc.code == "review_incomplete" else 400
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
