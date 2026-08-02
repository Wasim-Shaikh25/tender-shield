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
    Binds RLS as a side effect via auth.authenticate and stores the principal on
    request.state so middleware can enrich logs/traces without re-decoding the token."""
    authenticate = request.app.state.ctx.registry.get("auth.authenticate")
    if authenticate is None:
        raise HTTPException(503, "auth_unavailable")
    principal = authenticate(request, session)
    request.state.principal = principal
    return principal


def require(min_role: str):
    def guard(request: Request, principal: Any = Depends(current_principal)) -> Any:
        check_role = request.app.state.ctx.registry.get("auth.check_role")
        if check_role is None or not check_role(principal.role, min_role):
            raise HTTPException(403, "insufficient_role")
        return principal

    return guard


def require_superadmin(principal: Any = Depends(current_principal)) -> Any:
    if not getattr(principal, "is_superadmin", False):
        raise HTTPException(403, "superadmin_required")
    return principal


def require_document_class(document_class: str):
    """Return a dependency that enforces document-class ACL for a known class.

    Permissive when no ACL rule exists for the workspace/class. Raises
    403 document_class_forbidden when the principal's role is below min_role.
    """

    def guard(
        request: Request,
        principal: Any = Depends(current_principal),
        session: Session = Depends(get_session),
    ) -> Any:
        permitted_fn = request.app.state.ctx.registry.get("auth.document_class_permitted")
        if permitted_fn is None:
            raise HTTPException(503, "auth_unavailable")
        if not permitted_fn(session, principal.workspace_id, principal.role, document_class):
            raise HTTPException(403, "document_class_forbidden")
        return principal

    return guard


def require_document_access(document_id_param: str = "document_id"):
    """Return a dependency that enforces document-class ACL for a path document.

    Resolves the document's kind via the `ingestion.get_document_kind` capability
    and then checks auth.document_class_permitted. Missing document raises 404.
    """

    def guard(
        request: Request,
        principal: Any = Depends(current_principal),
        session: Session = Depends(get_session),
    ) -> Any:
        document_id = request.path_params.get(document_id_param)
        if not document_id:
            return principal
        get_kind = request.app.state.ctx.registry.get("ingestion.get_document_kind")
        permitted_fn = request.app.state.ctx.registry.get("auth.document_class_permitted")
        if get_kind is None or permitted_fn is None:
            return principal
        kind = get_kind(session, principal.workspace_id, document_id)
        if kind is None:
            raise HTTPException(404, "not_found")
        if not permitted_fn(session, principal.workspace_id, principal.role, kind):
            raise HTTPException(403, "document_class_forbidden")
        return principal

    return guard
