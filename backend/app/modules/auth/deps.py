"""Auth's cross-module API: a plain authenticate() function + check_role().

Published in the registry (auth.authenticate / auth.check_role) so other
modules consume auth via app.core.deps without importing anything here.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import bind_user_context, bind_workspace_context
from app.core.deps import current_principal, get_session
from app.modules.auth import security as sec
from app.modules.auth.models import Project, WorkspaceMember
from app.modules.auth.rbac import ROLE_RANK, Principal, role_at_least


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
    # so the endpoint's own queries reuse this same bound session. app.user_id
    # is bound once here, for the compound workspaces/workspace_members policy
    # (R-001 §B.7) — it never needs re-binding within the request.
    bind_workspace_context(session, claims["workspace"])
    bind_user_context(session, claims["sub"])
    return Principal(
        user_id=claims["sub"],
        workspace_id=claims["workspace"],
        role=claims["role"],
        is_superadmin=claims.get("is_superadmin", False),
    )


def check_role(role: str, min_role: str) -> bool:
    return role_at_least(role, min_role)


def require_superadmin(principal: Principal = Depends(current_principal)) -> Principal:
    if not principal.is_superadmin:
        raise HTTPException(403, "superadmin_required")
    return principal


def require_workspace_member(min_role: str = "viewer"):
    """Authorize against the workspace named in the PATH, not the token.

    `require(...)` (app.core.deps) checks the role the caller holds in their
    *own* active workspace from the JWT. Any route that also takes a
    workspace_id path parameter must additionally prove membership of THAT
    workspace — the caller's token workspace and the path workspace are not
    the same thing, and conflating them let an admin of workspace A add
    themselves to workspace B (gap R-001 §A.1-A.3, TS-084).

    Superadmins bypass by design (Doc §16 admin console). Non-members get 404,
    not 403 — a 403 confirms the workspace exists, which is itself a leak.
    """

    def guard(
        workspace_id: str,
        session: Session = Depends(get_session),
        principal: Principal = Depends(current_principal),
    ) -> Principal:
        if principal.is_superadmin:
            return principal
        member = session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == uuid.UUID(str(workspace_id)),
                WorkspaceMember.user_id == uuid.UUID(str(principal.user_id)),
            )
        )
        if member is None:
            raise HTTPException(404, "not_found")
        if ROLE_RANK.get(member.role, -1) < ROLE_RANK[min_role]:
            raise HTTPException(403, "insufficient_role")
        # Re-bind RLS to the workspace actually being addressed — it may differ
        # from the workspace baked into the caller's access token.
        bind_workspace_context(session, workspace_id)
        return principal

    return guard


def require_project_member(min_role: str = "viewer"):
    """Same as require_workspace_member, resolved via the project's workspace
    for routes keyed on project_id rather than workspace_id (R-001 §A.3)."""

    def guard(
        project_id: str,
        session: Session = Depends(get_session),
        principal: Principal = Depends(current_principal),
    ) -> Principal:
        project = session.scalar(select(Project).where(Project.id == uuid.UUID(str(project_id))))
        if project is None:
            raise HTTPException(404, "not_found")
        return require_workspace_member(min_role)(
            str(project.workspace_id), session=session, principal=principal
        )

    return guard
