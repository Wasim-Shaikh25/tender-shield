from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require, require_superadmin
from app.modules.rulepacks.admin_service import RulePackAdminError, RulePackAdminService
from app.modules.rulepacks.correction_service import CorrectionError, CorrectionService

router = APIRouter()


class ApplyPacksPayload(BaseModel):
    pack_ids: list[str] = Field(min_length=1, max_length=10)


def _loader(request: Request):
    return request.app.state.ctx.registry.require("rulepacks.loader")


def _admin(request: Request, session: Session) -> RulePackAdminService:
    reg = request.app.state.ctx.registry
    factory = reg.get("rulepacks.admin_factory")
    if factory:
        return factory(session)
    raise HTTPException(503, "rulepack_admin_unavailable")


def _corrections(request: Request, session: Session) -> CorrectionService:
    reg = request.app.state.ctx.registry
    factory = reg.get("rulepacks.correction_factory")
    if factory:
        return factory(session)
    return CorrectionService(session)


def _raise_admin(exc: RulePackAdminError):
    status = 404 if exc.code == "not_found" else 400
    raise HTTPException(status, exc.code) from exc


def _raise_correction(exc: CorrectionError):
    status = 404 if exc.code == "not_found" else 400
    raise HTTPException(status, exc.code) from exc


@router.get("")
def list_packs(request: Request, principal: Any = Depends(require("viewer"))) -> dict:
    _ = principal
    loader = _loader(request)
    packs = []
    for pack_id in loader.list_packs():
        pack = loader.get_pack(pack_id)
        packs.append(
            {
                "id": pack.meta.id,
                "version": pack.meta.version,
                "jurisdiction": pack.meta.jurisdiction,
                "patterns": len(pack.patterns),
                "load_errors": pack.load_errors,
            }
        )
    return {"packs": packs}


@router.get("/{pack_id}/patterns")
def list_patterns(
    pack_id: str,
    request: Request,
    validated_only: bool = False,
    principal: Any = Depends(require("viewer")),
) -> dict:
    _ = principal
    loader = _loader(request)
    if pack_id not in loader.list_packs():
        raise HTTPException(404, "unknown pack")
    patterns = loader.list_patterns(pack_id, validated_only=validated_only)
    return {
        "pack": loader.get_pack(pack_id).version_tag,
        "patterns": [
            {
                "id": p.id,
                "category": p.category,
                "title": p.title,
                "confidence": p.confidence,
                "source": p.source,
            }
            for p in patterns
        ],
    }


@router.get("/admin/packs")
def list_db_packs(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    workspace = str(principal.workspace_id) if principal.workspace_id else None
    packs = _admin(request, session).list_packs(
        workspace_id=workspace, include_global=True
    )
    return {"packs": [_admin(request, session).to_summary(p) for p in packs]}


@router.post("/admin/packs")
async def upload_pack(
    request: Request,
    session: Session = Depends(get_session),
    scope: str = Form(default="workspace"),
    archive: UploadFile = File(...),
    principal: Any = Depends(require("admin")),
):
    if scope == "global":
        require_superadmin(principal)
    try:
        data = await archive.read()
        row = await _admin(request, session).upload_pack(
            data,
            archive.filename or "rulepack.zip",
            scope=scope,
            workspace_id=principal.workspace_id,
            user_id=principal.user_id,
        )
    except RulePackAdminError as exc:
        _raise_admin(exc)
    return _admin(request, session).to_summary(row)


@router.post("/admin/packs/{rulepack_id}/activate")
def activate_pack(
    rulepack_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        row = _admin(request, session).activate_pack(rulepack_id, principal.user_id)
    except RulePackAdminError as exc:
        _raise_admin(exc)
    return _admin(request, session).to_summary(row)


@router.delete("/admin/packs/{rulepack_id}")
def delete_pack(
    rulepack_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        _admin(request, session).delete_pack(rulepack_id)
    except RulePackAdminError as exc:
        _raise_admin(exc)
    return {"ok": True}


@router.get("/admin/packs/{rulepack_id}/files")
def list_pack_files(
    rulepack_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        files = _admin(request, session).get_pack_files(rulepack_id)
    except RulePackAdminError as exc:
        _raise_admin(exc)
    return {
        "files": [
            {
                "id": str(f.id),
                "path": f.path,
                "size": f.size,
                "mime_type": f.mime_type,
            }
            for f in files
        ]
    }


@router.get("/opportunities/{opportunity_id}/packs")
def get_opportunity_packs(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    svc = _admin(request, session)
    packs = svc.get_opportunity_packs(opportunity_id)
    return {"packs": [svc.to_summary(p) for p in packs]}


@router.post("/opportunities/{opportunity_id}/packs")
def apply_opportunity_packs(
    opportunity_id: str,
    payload: ApplyPacksPayload,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        _admin(request, session).apply_packs_to_opportunity(
            opportunity_id,
            principal.workspace_id,
            payload.pack_ids,
            principal.user_id,
        )
    except RulePackAdminError as exc:
        _raise_admin(exc)
    return get_opportunity_packs(
        opportunity_id, request, session=session, principal=principal
    )


@router.post("/corrections/scan")
def scan_corrections(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _corrections(request, session).scan(principal.workspace_id)
    except CorrectionError as exc:
        _raise_correction(exc)


@router.get("/corrections/proposals")
def list_correction_proposals(
    request: Request,
    session: Session = Depends(get_session),
    status: str | None = None,
    principal: Any = Depends(require("viewer")),
):
    return {
        "proposals": _corrections(request, session).list_proposals(
            principal.workspace_id, status=status
        )
    }


@router.post("/corrections/proposals/{proposal_id}/dismiss")
def dismiss_correction_proposal(
    proposal_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _corrections(request, session).dismiss(
            principal.workspace_id,
            proposal_id,
            reviewer_id=principal.user_id,
        )
    except CorrectionError as exc:
        _raise_correction(exc)
