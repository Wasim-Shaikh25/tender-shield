"""Express lane public routes (TS-208 scaffold)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session
from app.modules.express.service import ExpressService

router = APIRouter()


class SessionBody(BaseModel):
    email: EmailStr
    tier: str = Field(default="snapshot", pattern="^(snapshot|risk|bidpack)$")
    acknowledgment: dict = Field(default_factory=dict)
    workspace_id: str


def _service(session: Session) -> ExpressService:
    return ExpressService(session)


@router.get("")
def status() -> dict:
    return {
        "module": "express",
        "status": "scaffold",
        "note": "Anonymous pay-per-report lane (TS-209+)",
    }


@router.post("/sessions")
def create_session(body: SessionBody, session: Session = Depends(get_session)):
    """Scaffold endpoint — creates a session row backed by the supplied workspace."""
    row = _service(session).create_session(
        email=body.email,
        tier=body.tier,
        acknowledgment=body.acknowledgment,
        workspace_id=body.workspace_id,
    )
    return {
        "token": row.token,
        "tier": row.tier,
        "state": row.state,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


@router.get("/sessions/{token}")
def get_session(token: str, session: Session = Depends(get_session)):
    row = _service(session).get_by_token(token)
    if row is None:
        raise HTTPException(404, "session_not_found")
    return {
        "token": row.token,
        "email": row.email,
        "tier": row.tier,
        "state": row.state,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }
