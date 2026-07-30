"""Thin audit helper used by routers to emit workspace-level audit events.

Routers call `log(...)` after a successful action. It resolves the
`review.service_factory` capability (if available) and writes an `AuditLog` row.
Keeping this in `app.core` means no module imports another module.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import Request
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def log(
    request: Request,
    session: Session,
    *,
    workspace_id: str | uuid.UUID,
    actor_user_id: str | uuid.UUID | None,
    action: str,
    object_type: str | None = None,
    object_id: str | uuid.UUID | None = None,
    detail: dict | None = None,
) -> None:
    """Record an append-only audit event via the review module's audit capability.

    Failures are logged and swallowed; an audit write must never break a user action.
    Account-level contexts (no real workspace, e.g. login/signup before workspace
    selection) are skipped because audit_log is workspace-scoped.
    """
    try:
        uuid.UUID(str(workspace_id))
    except ValueError:
        return
    factory = request.app.state.ctx.registry.get("review.service_factory")
    if factory is None:
        return
    try:
        svc = factory(session)
        svc.audit(
            workspace_id,
            actor=str(actor_user_id) if actor_user_id else None,
            action=action,
            object_type=object_type,
            object_id=str(object_id) if object_id else None,
            detail=detail or {},
        )
    except Exception:
        logger.exception("audit log failed for action %r", action)
