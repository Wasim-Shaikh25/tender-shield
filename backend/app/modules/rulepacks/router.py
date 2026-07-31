from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.rulepacks.correction_service import CorrectionError, CorrectionService

router = APIRouter()


def _loader(request: Request):
    return request.app.state.ctx.registry.require("rulepacks.loader")


def _corrections(request: Request, session: Session) -> CorrectionService:
    reg = request.app.state.ctx.registry
    factory = reg.get("rulepacks.correction_factory")
    if factory:
        return factory(session)
    return CorrectionService(session)


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
