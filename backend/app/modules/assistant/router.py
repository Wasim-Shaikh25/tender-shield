from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import log as audit_log
from app.core.deps import get_session, require, require_superadmin
from app.modules.assistant.service import AssistantService

router = APIRouter()


class ChatBody(BaseModel):
    opportunity_id: str
    message: str


class SessionBody(BaseModel):
    opportunity_id: str = Field(min_length=1)
    title: str | None = None


class StreamBody(BaseModel):
    message: str = Field(min_length=1)


class AdminChatBody(BaseModel):
    workspace_id: str = Field(min_length=1)
    opportunity_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


def _identity(principal) -> dict:
    return {
        "user_id": str(principal.user_id),
        "workspace_id": str(principal.workspace_id),
        "role": principal.role,
        "is_superadmin": getattr(principal, "is_superadmin", False),
    }


def _service(request: Request, session: Session) -> AssistantService:
    reg = request.app.state.ctx.registry
    return AssistantService(
        session,
        ingestion_factory=reg.get("ingestion.service_factory"),
        findings_factory=reg.get("findings.store_factory"),
        loader=reg.get("rulepacks.loader"),
        agent=reg.get("assistant.agent"),
        workspace_factory=reg.get("auth.workspace_factory"),
        plan_dashboard_factory=reg.get("analytics.plan_dashboard"),
    )


def _session_json(s) -> dict:
    return {
        "id": str(s.id),
        "opportunity_id": str(s.opportunity_id),
        "title": s.title,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _message_json(m) -> dict:
    return {
        "id": str(m.id),
        "role": m.role,
        "content": m.content,
        "type": m.message_type,
        "dashboard": m.dashboard,
        "grounded": m.grounded,
        "source": m.source,
        "citations": m.citations,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.post("/chat")
def chat(
    body: ChatBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    """Transient single-turn chat (no session persistence)."""
    return _service(request, session).answer(
        principal.workspace_id, body.opportunity_id, body.message, identity=_identity(principal)
    )


@router.post("/sessions")
def create_session(
    body: SessionBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    s = _service(request, session).create_session(
        principal.workspace_id, body.opportunity_id, body.title
    )
    return _session_json(s)


@router.get("/sessions")
def list_sessions(
    request: Request,
    opportunity_id: str | None = None,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    sessions = _service(request, session).list_sessions(principal.workspace_id, opportunity_id)
    return {"sessions": [_session_json(s) for s in sessions]}


@router.get("/sessions/{session_id}/messages")
def get_messages(
    session_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    msgs = _service(request, session).get_messages(principal.workspace_id, session_id)
    return {"messages": [_message_json(m) for m in msgs]}


def _resolve_session(svc: AssistantService, session_id: str, workspace_id):
    sess = svc.get_session(workspace_id, session_id)
    if not sess:
        raise HTTPException(404, "session_not_found")
    return sess


@router.post("/sessions/{session_id}/chat")
def session_chat(
    session_id: str,
    body: StreamBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    svc = _service(request, session)
    sess = _resolve_session(svc, session_id, principal.workspace_id)
    return svc.answer_and_store(
        principal.workspace_id,
        session_id,
        str(sess.opportunity_id),
        body.message,
        identity=_identity(principal),
    )


@router.post("/sessions/{session_id}/stream")
def stream_chat(
    session_id: str,
    body: StreamBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    svc = _service(request, session)
    sess = _resolve_session(svc, session_id, principal.workspace_id)
    return StreamingResponse(
        svc.answer_stream(
            principal.workspace_id,
            session_id,
            str(sess.opportunity_id),
            body.message,
            identity=_identity(principal),
        ),
        media_type="text/event-stream",
    )


@router.post("/admin/chat")
def admin_chat(
    body: AdminChatBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require_superadmin),
):
    """Super-admin research chat: explicit workspace/opportunity, no session stored."""
    svc = _service(request, session)
    identity = _identity(principal)
    answer = svc.admin_answer(
        body.workspace_id,
        body.opportunity_id,
        body.message,
        identity=identity,
    )
    audit_log(
        request,
        session,
        workspace_id=body.workspace_id,
        actor_user_id=principal.user_id,
        action="assistant.admin_query",
        object_type="opportunity",
        object_id=body.opportunity_id,
        detail={"message_preview": body.message[:200]},
    )
    return answer
