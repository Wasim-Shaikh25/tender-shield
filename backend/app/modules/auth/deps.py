"""FastAPI dependencies: request-scoped session (with RLS binding) + principal
resolution + RBAC guard. These are what the module publishes to the app."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.db import bind_org_context
from app.modules.auth import security as sec
from app.modules.auth.rbac import Principal, role_at_least


def get_session(request: Request) -> Iterator[Session]:
    factory = request.app.state.ctx.registry.require("db.sessionmaker")
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer_token")
    return header[7:]


def current_principal(
    request: Request, session: Session = Depends(get_session)
) -> Principal:
    keys: sec.KeyPair = request.app.state.ctx.registry.require("auth.keys")
    try:
        claims = sec.decode_access(_bearer(request), keys.public_pem)
    except sec.AuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    # The non-negotiable RLS binding: everything this request queries is scoped
    # to the caller's org (Doc §3.2, §5). FastAPI caches get_session per request,
    # so the endpoint's own queries reuse this same bound session.
    bind_org_context(session, claims["org"])
    return Principal(user_id=claims["sub"], org_id=claims["org"], role=claims["role"])


def require(min_role: str):
    def guard(principal: Principal = Depends(current_principal)) -> Principal:
        if not role_at_least(principal.role, min_role):
            raise HTTPException(403, "insufficient_role")
        return principal

    return guard
