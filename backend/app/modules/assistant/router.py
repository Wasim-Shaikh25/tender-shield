from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.assistant.service import AssistantService

router = APIRouter()


class ChatBody(BaseModel):
    opportunity_id: str
    message: str


def _service(request: Request, session: Session) -> AssistantService:
    reg = request.app.state.ctx.registry
    return AssistantService(
        session,
        ingestion_factory=reg.get("ingestion.service_factory"),
        findings_factory=reg.get("findings.store_factory"),
        loader=reg.get("rulepacks.loader"),
        agent=reg.get("assistant.agent"),
    )


@router.post("/chat")
def chat(
    body: ChatBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).answer(principal.org_id, body.opportunity_id, body.message)
