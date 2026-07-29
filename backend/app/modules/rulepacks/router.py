from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.deps import require

router = APIRouter()


def _loader(request: Request):
    return request.app.state.ctx.registry.require("rulepacks.loader")


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
