"""Express lane public routes (TS-208/209)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session
from app.modules.express.service import (
    ACKNOWLEDGMENT_VERSION,
    EXPRESS_MAX_UPLOAD_BYTES,
    ExpressError,
    ExpressService,
)

router = APIRouter()

_ERROR_STATUS = {
    "acknowledgment_required": 422,
    "workspace_unavailable": 503,
    "session_not_found": 404,
    "upload_too_large": 413,
    "teaser_unavailable": 503,
}


class SessionBody(BaseModel):
    email: EmailStr
    tier: str = Field(default="snapshot", pattern="^(snapshot|risk|bidpack)$")
    acknowledgment: dict = Field(default_factory=dict)
    acknowledgment_version: str = ACKNOWLEDGMENT_VERSION


def _service(request: Request, session: Session) -> ExpressService:
    reg = request.app.state.ctx.registry
    factory = reg.get("express.service_factory")
    if factory:
        return factory(session)
    return ExpressService(
        session,
        create_workspace=reg.get("auth.create_ephemeral_workspace"),
    )


def _raise(exc: ExpressError):
    raise HTTPException(_ERROR_STATUS.get(exc.code, 400), exc.code) from exc


@router.get("")
def status() -> dict:
    return {
        "module": "express",
        "status": "ready",
        "acknowledgment_version": ACKNOWLEDGMENT_VERSION,
        "max_upload_bytes": EXPRESS_MAX_UPLOAD_BYTES,
    }


@router.post("/sessions")
def create_session(
    body: SessionBody,
    request: Request,
    session: Session = Depends(get_session),
):
    client_ip = request.client.host if request.client else None
    try:
        row = _service(request, session).create_session(
            email=body.email,
            tier=body.tier,
            acknowledgment=body.acknowledgment,
            acknowledgment_version=body.acknowledgment_version,
            client_ip=client_ip,
        )
    except ExpressError as exc:
        _raise(exc)
    return {
        "token": row.token,
        "tier": row.tier,
        "state": row.state,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


@router.get("/sessions/{token}")
def fetch_session(token: str, request: Request, session: Session = Depends(get_session)):
    try:
        row = _service(request, session).require_session(token)
    except ExpressError as exc:
        _raise(exc)
    return {
        "token": row.token,
        "email": row.email,
        "tier": row.tier,
        "state": row.state,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


@router.post("/sessions/{token}/documents")
async def upload_document(
    token: str,
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    data = await file.read(EXPRESS_MAX_UPLOAD_BYTES + 1)
    try:
        doc = _service(request, session).upload_document(
            token,
            filename=file.filename or "upload.bin",
            data=data,
        )
    except ExpressError as exc:
        _raise(exc)
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "sha256": doc.sha256,
        "retention_until": doc.retention_until.isoformat() if doc.retention_until else None,
    }


@router.get("/sessions/{token}/teaser")
def get_teaser(token: str, request: Request, session: Session = Depends(get_session)):
    try:
        return _service(request, session).render_teaser(token)
    except ExpressError as exc:
        _raise(exc)
