"""Shared request dependencies (infra, not a feature module).

These resolve the auth module purely by capability name via the registry, so
ANY module can require authentication/roles without importing auth. If auth is
disabled the capabilities are absent and protected routes return 503 — the app
still boots (spec core B2).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    factory = request.app.state.ctx.registry.require("db.sessionmaker")
    session = factory()
    try:
        yield session
    finally:
        session.close()


def current_principal(request: Request, session: Session = Depends(get_session)) -> Any:
    """Returns the auth module's Principal (structural: has user_id/workspace_id/role).
    Binds RLS as a side effect via auth.authenticate."""
    authenticate = request.app.state.ctx.registry.get("auth.authenticate")
    if authenticate is None:
        raise HTTPException(503, "auth_unavailable")
    return authenticate(request, session)


def require(min_role: str):
    def guard(request: Request, principal: Any = Depends(current_principal)) -> Any:
        check_role = request.app.state.ctx.registry.get("auth.check_role")
        if check_role is None or not check_role(principal.role, min_role):
            raise HTTPException(403, "insufficient_role")
        return principal

    return guard
