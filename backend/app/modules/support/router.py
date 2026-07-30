"""Support ticket routes for workspace users and super-admins."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import audit as audit_log
from app.core.config import Settings
from app.core.db import bind_workspace_context
from app.core.deps import current_principal, get_session
from app.core.storage import (
    ALLOWED_UPLOAD_EXTENSIONS,
    ValidationError,
    get_storage,
    sanitize_filename,
)
from app.modules.support.service import SupportError, SupportService

router = APIRouter()

SENTINEL_WS = "00000000-0000-0000-0000-000000000000"


class CreateTicketBody(BaseModel):
    title: str
    body: str
    category: str = "other"


class ReplyBody(BaseModel):
    body: str


class StatusBody(BaseModel):
    status: str


def _service(session: Session) -> SupportService:
    return SupportService(session)


def _require_workspace(principal: Any) -> None:
    if principal.workspace_id == SENTINEL_WS:
        raise HTTPException(400, "workspace_required")


def _ticket_response(ticket):
    return {
        "id": str(ticket.id),
        "workspace_id": str(ticket.workspace_id),
        "user_id": str(ticket.user_id),
        "title": ticket.title,
        "body": ticket.body,
        "category": ticket.category,
        "status": ticket.status,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
    }


def _attachment_response(att):
    return {
        "id": str(att.id),
        "ticket_id": str(att.ticket_id) if att.ticket_id else None,
        "storage_key": att.storage_key,
        "filename": att.filename,
        "content_type": att.content_type,
        "created_at": att.created_at.isoformat() if att.created_at else None,
    }


@router.post("/tickets")
def create_ticket(
    body: CreateTicketBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(current_principal),
):
    _require_workspace(principal)
    ticket = _service(session).create_ticket(
        principal.workspace_id,
        principal.user_id,
        body.title,
        body.body,
        body.category,
    )
    audit_log.log(
        request,
        session,
        workspace_id=principal.workspace_id,
        actor_user_id=principal.user_id,
        action="support.ticket_created",
        object_type="support_ticket",
        object_id=ticket.id,
        detail={"category": ticket.category},
    )
    return _ticket_response(ticket)


@router.get("/tickets")
def list_tickets(
    session: Session = Depends(get_session),
    principal: Any = Depends(current_principal),
):
    _require_workspace(principal)
    tickets = _service(session).list_tickets(
        principal.workspace_id,
        principal.user_id,
        is_superadmin=principal.is_superadmin,
    )
    return [_ticket_response(t) for t in tickets]


@router.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: str,
    session: Session = Depends(get_session),
    principal: Any = Depends(current_principal),
):
    _require_workspace(principal)
    ticket = _service(session).get_ticket(
        ticket_id,
        principal.workspace_id,
        principal.user_id,
        is_superadmin=principal.is_superadmin,
    )
    if ticket is None:
        raise HTTPException(404, "ticket_not_found")
    replies = _service(session).list_replies(
        ticket_id,
        principal.workspace_id,
        principal.user_id,
        is_superadmin=principal.is_superadmin,
    )
    return {
        **_ticket_response(ticket),
        "replies": [
            {
                "id": str(r.id),
                "user_id": str(r.user_id),
                "body": r.body,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in replies
        ],
    }


@router.post("/tickets/{ticket_id}/replies")
def add_reply(
    ticket_id: str,
    body: ReplyBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(current_principal),
):
    _require_workspace(principal)
    try:
        reply = _service(session).add_reply(
            ticket_id,
            principal.workspace_id,
            principal.user_id,
            body.body,
            is_superadmin=principal.is_superadmin,
        )
    except SupportError as exc:
        raise HTTPException(400, exc.code) from exc
    audit_log.log(
        request,
        session,
        workspace_id=principal.workspace_id,
        actor_user_id=principal.user_id,
        action="support.ticket_replied",
        object_type="support_ticket",
        object_id=ticket_id,
    )
    return {
        "id": str(reply.id),
        "ticket_id": str(reply.ticket_id),
        "user_id": str(reply.user_id),
        "body": reply.body,
        "created_at": reply.created_at.isoformat() if reply.created_at else None,
    }


@router.post("/tickets/{ticket_id}/attachments")
async def upload_attachment(
    ticket_id: str,
    file: UploadFile,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(current_principal),
):
    _require_workspace(principal)
    filename = sanitize_filename(file.filename or "attachment")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if f".{ext}" not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(400, "unsupported_file_type")
    data = await file.read()
    settings: Settings = request.app.state.ctx.settings
    storage = get_storage(settings)
    try:
        key = await storage.write(
            f"workspace/{principal.workspace_id}/support/tickets/{ticket_id}/{filename}",
            data,
            file.content_type or "application/octet-stream",
        )
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc
    att = _service(session).add_attachment(
        ticket_id,
        principal.workspace_id,
        principal.user_id,
        key,
        filename,
        file.content_type or "application/octet-stream",
        is_superadmin=principal.is_superadmin,
    )
    audit_log.log(
        request,
        session,
        workspace_id=principal.workspace_id,
        actor_user_id=principal.user_id,
        action="support.attachment_uploaded",
        object_type="support_attachment",
        object_id=att.id,
        detail={"filename": filename},
    )
    return _attachment_response(att)


@router.get("/admin/tickets")
def admin_list_tickets(
    workspace_id: str,
    category: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
    principal: Any = Depends(current_principal),
):
    if not principal.is_superadmin:
        raise HTTPException(403, "superadmin_required")
    bind_workspace_context(session, workspace_id)
    tickets = _service(session).list_tickets(workspace_id, principal.user_id, is_superadmin=True)
    if category:
        tickets = [t for t in tickets if t.category == category]
    if status:
        tickets = [t for t in tickets if t.status == status]
    return [_ticket_response(t) for t in tickets]


@router.get("/admin/tickets/{ticket_id}")
def admin_get_ticket(
    ticket_id: str,
    workspace_id: str,
    session: Session = Depends(get_session),
    principal: Any = Depends(current_principal),
):
    if not principal.is_superadmin:
        raise HTTPException(403, "superadmin_required")
    bind_workspace_context(session, workspace_id)
    ticket = _service(session).get_ticket(
        ticket_id, workspace_id, principal.user_id, is_superadmin=True
    )
    if ticket is None:
        raise HTTPException(404, "ticket_not_found")
    replies = _service(session).list_replies(
        ticket_id, workspace_id, principal.user_id, is_superadmin=True
    )
    return {
        **_ticket_response(ticket),
        "replies": [
            {
                "id": str(r.id),
                "user_id": str(r.user_id),
                "body": r.body,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in replies
        ],
    }


@router.post("/admin/tickets/{ticket_id}/status")
def admin_set_status(
    ticket_id: str,
    workspace_id: str,
    body: StatusBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(current_principal),
):
    if not principal.is_superadmin:
        raise HTTPException(403, "superadmin_required")
    bind_workspace_context(session, workspace_id)
    try:
        ticket = _service(session).set_status(ticket_id, workspace_id, body.status)
    except SupportError as exc:
        raise HTTPException(400, exc.code) from exc
    audit_log.log(
        request,
        session,
        workspace_id=ticket.workspace_id,
        actor_user_id=principal.user_id,
        action="support.ticket_status_changed",
        object_type="support_ticket",
        object_id=ticket.id,
        detail={"status": ticket.status},
    )
    return _ticket_response(ticket)
