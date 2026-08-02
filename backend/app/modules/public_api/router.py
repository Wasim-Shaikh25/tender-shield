"""Public API + e-signature routes (TS-292)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.public_api.service import PublicApiError, PublicApiService

router = APIRouter()

_ERROR_STATUS = {
    "not_found": 404,
}


class CreateKeyBody(BaseModel):
    name: str = Field(min_length=1)
    scopes: list[str] | None = None


class RequestSignatureBody(BaseModel):
    opportunity_id: str = Field(min_length=1)
    recipient_email: str = Field(min_length=1)
    notice_id: str | None = None
    change_event_id: str | None = None
    provider: str = "docusign_stub"


class SignatureCallbackBody(BaseModel):
    external_id: str = Field(min_length=1)
    status: str = Field(min_length=1)


def _service(request: Request, session: Session) -> PublicApiService:
    reg = request.app.state.ctx.registry
    return PublicApiService(
        session,
        change_factory=reg.get("change.service_factory"),
        publish=request.app.state.ctx.events.publish,
    )


def _raise(exc: PublicApiError):
    raise HTTPException(_ERROR_STATUS.get(exc.code, 400), exc.code) from exc


def _api_principal(
    request: Request,
    session: Session = Depends(get_session),
    authorization: str = Header(None),
):
    token = None
    if authorization:
        parts = authorization.split(maxsplit=1)
        if len(parts) == 2 and parts[0].lower() == "apikey":
            token = parts[1].strip()
    if not token:
        raise HTTPException(401, "api_key_required")
    principal = _service(request, session).authenticate(token)
    if principal is None:
        raise HTTPException(401, "invalid_api_key")
    return principal


@router.get("/status")
def status() -> dict:
    return {"module": "public_api", "status": "ready"}


@router.post("/keys")
def create_key(
    body: CreateKeyBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    row, token = _service(request, session).create_key(
        principal.workspace_id,
        principal.user_id,
        name=body.name,
        scopes=body.scopes,
    )
    return {
        "id": str(row.id),
        "name": row.name,
        "plaintext_key": token,
        "scopes": row.scopes,
    }


@router.get("/keys")
def list_keys(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    rows = _service(request, session).list_keys(principal.workspace_id)
    return {"keys": [{"id": str(r.id), "name": r.name, "scopes": r.scopes} for r in rows]}


@router.post("/notices/{notice_id}/request-signature")
def request_signature(
    notice_id: str,
    body: RequestSignatureBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: dict = Depends(_api_principal),
):
    if "write" not in principal.get("scopes", []):
        raise HTTPException(403, "insufficient_scope")
    try:
        row = _service(request, session).request_signature(
            principal["workspace_id"],
            body.opportunity_id,
            recipient_email=body.recipient_email,
            notice_id=notice_id,
            change_event_id=body.change_event_id,
            provider=body.provider,
        )
    except PublicApiError as exc:
        _raise(exc)
    return {
        "id": str(row.id),
        "external_id": row.external_id,
        "status": row.status,
    }


@router.get("/signatures/{request_id}/status")
def signature_status(
    request_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: dict = Depends(_api_principal),
):
    try:
        row = _service(request, session).get_signature_status(
            principal["workspace_id"], request_id
        )
    except PublicApiError as exc:
        _raise(exc)
    return {
        "id": str(row.id),
        "status": row.status,
        "signed_at": row.signed_at.isoformat() if row.signed_at else None,
    }


@router.post("/signatures/callback")
def signature_callback(
    body: SignatureCallbackBody,
    request: Request,
    session: Session = Depends(get_session),
):
    # Webhook callbacks are provider-authenticated by shared secret outside this route.
    try:
        row = _service(request, session).signature_callback(body.external_id, body.status)
    except PublicApiError as exc:
        _raise(exc)
    return {"id": str(row.id), "status": row.status}
