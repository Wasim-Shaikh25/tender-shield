from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

router = APIRouter()


def _optional_principal(request: Request) -> Any | None:
    """Return the authenticated principal if auth is loaded and a valid token
    is supplied; otherwise None. This lets the health details endpoint degrade
    gracefully when the auth module is not enabled (e.g. isolated loader tests).
    """
    authenticate = request.app.state.ctx.registry.get("auth.authenticate")
    if authenticate is None:
        return None
    factory = request.app.state.ctx.registry.get("db.sessionmaker")
    if factory is None:
        return None
    session: Session = factory()
    try:
        return authenticate(request, session)
    except Exception:
        return None
    finally:
        session.close()


@router.get("")
def health(request: Request) -> dict:
    """Public health endpoint: minimal status only."""
    return {"status": "ok", "version": "0.1.0"}


@router.get("/details")
def health_details(
    request: Request,
    principal: Any = Depends(_optional_principal),
) -> dict:
    """Detailed health/capability report.

    In production the auth module is always loaded, so this requires a valid
    super-admin token. When auth is disabled (isolated loader tests) it falls
    back to public access so module-loading tests still work.
    """
    settings = request.app.state.ctx.settings
    auth_loaded = request.app.state.ctx.registry.get("auth.authenticate") is not None
    if settings.is_prod() and auth_loaded and not getattr(principal, "is_superadmin", False):
        raise HTTPException(403, "superadmin_required")

    report = request.app.state.load_report
    return {
        "status": "ok",
        "modules": [
            {"name": s.name, "version": s.version, "soft_deps": list(s.soft_deps)}
            for s in report.loaded
        ],
        "failed_modules": report.failed,
        "missing_soft_deps": report.missing_soft_deps,
        "capabilities": request.app.state.ctx.registry.names(),
    }
