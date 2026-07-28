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


def meter(event: str):
    """Gate a billable action through the billing capability (Doc §7, R-004 §A).

    Resolved by name so no module imports billing (CLAUDE.md §2) — risk/boq/
    export must not import app.modules.billing. `billing.service_factory` is
    the capability billing already publishes for exactly this purpose
    (billing/module.py's own comment says "consumed by risk/ingestion before
    starting a review" — nothing consumed it until this dependency existed).

    When billing is disabled: dev/test proceeds unmetered (so the app still
    boots with any module subset, spec core B2); production refuses with 503,
    because a disabled billing module must never silently become a free tier.

    Reads `opportunity_id` from the route's path params (if present) so a
    review can be metered once per opportunity, not once per call — re-running
    an already-metered opportunity (e.g. after an addendum) is free.
    """

    def guard(
        request: Request,
        session: Session = Depends(get_session),
        principal: Any = Depends(current_principal),
    ) -> Any:
        factory = request.app.state.ctx.registry.get("billing.service_factory")
        if factory is None:
            if request.app.state.ctx.settings.env == "production":
                raise HTTPException(503, "billing_unavailable")
            return None
        opportunity_id = request.path_params.get("opportunity_id")
        try:
            return factory(session).authorize_review(principal.workspace_id, opportunity_id)
        except Exception as exc:  # PaywallError, resolved structurally (no billing import)
            code = getattr(exc, "code", None)
            if code is None:
                raise
            events = getattr(request.app.state.ctx, "events", None)
            if events is not None:
                events.publish(
                    "billing.paywall_hit",
                    {"workspace_id": str(principal.workspace_id), "code": code, "event": event},
                )
            upsell = getattr(exc, "upsell", {})
            raise HTTPException(402, detail={"code": code, "upsell": upsell}) from exc

    return guard
