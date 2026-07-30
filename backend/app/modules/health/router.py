from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.storage import StorageError, get_storage

router = APIRouter()
logger = logging.getLogger(__name__)


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


def _check_db(request: Request) -> dict[str, Any]:
    factory = request.app.state.ctx.registry.get("db.sessionmaker")
    if factory is None:
        return {"status": "skipped"}
    session: Session = factory()
    try:
        session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:  # pragma: no cover - exercised by failure tests
        logger.warning("health db check failed: %s", exc)
        return {"status": "failed", "error": str(exc)}
    finally:
        session.close()


def _check_redis(request: Request) -> dict[str, Any]:
    settings = request.app.state.ctx.settings
    if not settings.redis_url:
        return {"status": "skipped"}
    try:
        import redis

        client = redis.from_url(settings.redis_url)
        client.ping()
        return {"status": "ok"}
    except Exception as exc:  # pragma: no cover - exercised by failure tests
        logger.warning("health redis check failed: %s", exc)
        return {"status": "failed", "error": str(exc)}


def _check_storage(request: Request) -> dict[str, Any]:
    settings = request.app.state.ctx.settings
    try:
        _storage = get_storage(settings)
        # A lightweight probe: local storage just needs the directory to exist and
        # be writable; S3 storage instantiation already validates credentials.
        if settings.storage_type == "local":
            import pathlib

            root = pathlib.Path(settings.storage_dir)
            root.mkdir(parents=True, exist_ok=True)
            probe = root / ".health_probe"
            probe.write_bytes(b"ok")
            probe.unlink(missing_ok=True)
        return {"status": "ok"}
    except StorageError as exc:
        logger.warning("health storage check failed: %s", exc)
        return {"status": "failed", "error": str(exc)}
    except Exception as exc:  # pragma: no cover
        logger.warning("health storage check failed: %s", exc)
        return {"status": "failed", "error": str(exc)}


def _check_celery(request: Request) -> dict[str, Any]:
    celery_app = request.app.state.ctx.registry.get("celery.app")
    if celery_app is None:
        return {"status": "skipped"}
    try:
        # In eager/memory mode this is a no-op; with Redis it validates the broker.
        with celery_app.connection() as conn:
            conn.connect()
            conn.release()
        return {"status": "ok"}
    except Exception as exc:  # pragma: no cover - exercised by failure tests
        logger.warning("health celery check failed: %s", exc)
        return {"status": "failed", "error": str(exc)}


def _dependency_report(request: Request) -> dict[str, Any]:
    return {
        "database": _check_db(request),
        "redis": _check_redis(request),
        "storage": _check_storage(request),
        "celery": _check_celery(request),
    }


def _is_healthy(report: dict[str, Any]) -> bool:
    return all(status.get("status") in ("ok", "skipped") for status in report.values())


@router.get("")
def health(request: Request) -> dict:
    """Public health endpoint: minimal status only."""
    return {"status": "ok", "version": "0.1.0"}


@router.get("/live")
def health_live(request: Request) -> Response:
    """Liveness probe — returns 200 as long as the process can respond."""
    return Response(content="ok", media_type="text/plain")


@router.get("/ready")
def health_ready(request: Request) -> Response:
    """Readiness probe — checks all configured dependencies."""
    report = _dependency_report(request)
    healthy = _is_healthy(report)
    code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(
        content=json.dumps({"status": "ok" if healthy else "degraded", "dependencies": report}),
        media_type="application/json",
        status_code=code,
    )


@router.get("/metrics")
def health_metrics(request: Request) -> Response:
    """Prometheus-compatible metrics exposition."""
    from app.core.metrics import expose_metrics

    return Response(content=expose_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8")


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
    deps = _dependency_report(request)
    return {
        "status": "ok" if _is_healthy(deps) else "degraded",
        "modules": [
            {"name": s.name, "version": s.version, "soft_deps": list(s.soft_deps)}
            for s in report.loaded
        ],
        "failed_modules": report.failed,
        "missing_soft_deps": report.missing_soft_deps,
        "capabilities": request.app.state.ctx.registry.names(),
        "dependencies": deps,
    }
