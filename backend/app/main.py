"""FastAPI application factory: loads enabled modules and wires them up."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import Settings
from app.core.db import make_engine, make_session_factory
from app.core.events import EventBus
from app.core.loader import LoadReport, load_modules
from app.core.module import AppContext
from app.core.registry import ServiceRegistry

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every HTTP response."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        headers = response.headers
        headers["X-Content-Type-Options"] = "nosniff"
        headers["X-Frame-Options"] = "DENY"
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        return response


def _validate_prod_settings(settings: Settings) -> None:
    """Fail fast in production when unsafe defaults are present."""
    if not settings.is_prod():
        return

    errors: list[str] = []
    if not settings.razorpay_webhook_secret:
        errors.append("TS_RAZORPAY_WEBHOOK_SECRET is required in production")
    if not settings.jwt_private_key or not settings.jwt_public_key:
        errors.append("TS_JWT_PRIVATE_KEY and TS_JWT_PUBLIC_KEY are required in production")
    if settings.cors_origins == "*":
        errors.append("TS_CORS_ORIGINS must be explicit in production (no wildcard)")
    if settings.allowed_hosts == "*":
        errors.append("TS_ALLOWED_HOSTS must be explicit in production (no wildcard)")

    # Reject obviously dev/test placeholder secrets.
    bad_secrets = {"dev-razorpay-secret", "secret", "changeme"}
    if settings.razorpay_webhook_secret:
        secret_val = settings.razorpay_webhook_secret.get_secret_value() or ""
        if secret_val.lower() in bad_secrets or len(secret_val) < 16:
            errors.append("TS_RAZORPAY_WEBHOOK_SECRET is too weak/placeholder")

    if errors:
        raise RuntimeError("Production settings unsafe: " + "; ".join(errors))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    _validate_prod_settings(settings)

    ctx = AppContext(settings=settings, registry=ServiceRegistry(), events=EventBus())

    # Shared DB: published as a capability so modules consume the session factory
    # via the registry rather than importing it (keeps them pluggable).
    if settings.database_url:
        engine = make_engine(settings)
        ctx.registry.provide("db.engine", engine)
        ctx.registry.provide("db.sessionmaker", make_session_factory(engine))

    report: LoadReport = load_modules(settings.enabled_module_names())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        for spec in report.loaded:
            if spec.shutdown is not None:
                try:
                    spec.shutdown(ctx)
                except Exception:
                    logger.exception("shutdown failed for module %r", spec.name)

    app = FastAPI(title="TenderShield API", version="0.1.0", lifespan=lifespan)

    # Host/HTTPS hardening in production; TrustedHost is a no-op when allowed_hosts="*".
    if settings.is_prod():
        app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list())

    # CORS: explicit origins are required for cookie-based auth.
    origins = settings.cors_origin_list()
    allow_credentials = settings.cors_supports_credentials()
    if "*" in origins and allow_credentials:
        logger.warning(
            "CORS wildcard with credentials is invalid; setting allow_credentials=False"
        )
        allow_credentials = False
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
        allow_credentials=allow_credentials,
    )

    app.add_middleware(SecurityHeadersMiddleware)

    app.state.ctx = ctx
    app.state.load_report = report

    for spec in report.loaded:
        if spec.setup is not None:
            try:
                spec.setup(ctx)
            except Exception as exc:  # fail-isolated (spec core B3)
                logger.exception("setup failed for module %r", spec.name)
                report.failed[spec.name] = f"setup: {type(exc).__name__}: {exc}"
                continue
        if spec.router is not None:
            app.include_router(spec.router, prefix=f"/api/{spec.name}", tags=[spec.name])

    report.loaded = [s for s in report.loaded if s.name not in report.failed]
    return app
