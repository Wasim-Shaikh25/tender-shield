"""Auth's cross-module API: a plain authenticate() function + check_role().

Published in the registry (auth.authenticate / auth.check_role) so other
modules consume auth via app.core.deps without importing anything here.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.db import bind_workspace_context
from app.core.deps import current_principal
from app.modules.auth import security as sec
from app.modules.auth.rbac import Principal, role_at_least


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer_token")
    return header[7:]


def authenticate(request: Request, session: Session) -> Principal:
    keys: sec.KeyPair = request.app.state.ctx.registry.require("auth.keys")
    try:
        claims = sec.decode_access(_bearer(request), keys.public_pem)
    except sec.AuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    # The non-negotiable RLS binding: this request's queries are scoped to the
    # caller's workspace (Doc §3.2, §5). FastAPI caches get_session per request,
    # so the endpoint's own queries reuse this same bound session.
    bind_workspace_context(session, claims["workspace"], user_id=claims["sub"])
    settings = request.app.state.ctx.settings
    mobile_verified = claims.get("mobile_verified", False)
    if settings and not settings.auth_mobile_verification_enabled:
        mobile_verified = True
    return Principal(
        user_id=claims["sub"],
        workspace_id=claims["workspace"],
        role=claims["role"],
        is_superadmin=claims.get("is_superadmin", False),
        email_verified=claims.get("email_verified", False),
        mobile_verified=mobile_verified,
    )


def check_role(role: str, min_role: str) -> bool:
    return role_at_least(role, min_role)


def require_superadmin(principal: Principal = Depends(current_principal)) -> Principal:
    if not principal.is_superadmin:
        raise HTTPException(403, "superadmin_required")
    return principal
