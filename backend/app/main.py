"""FastAPI application factory: loads enabled modules and wires them up."""

from __future__ import annotations

import logging
import mimetypes
import pathlib as _pathlib
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.celery import make_celery_app
from app.core.config import Settings
from app.core.db import make_engine, make_session_factory
from app.core.deps import require
from app.core.events import EventBus
from app.core.loader import LoadReport, load_modules
from app.core.logging_middleware import AccessLogMiddleware
from app.core.metrics import MetricsMiddleware
from app.core.module import AppContext
from app.core.ratelimit import default_rate_limiter
from app.core.registry import ServiceRegistry
from app.core.scheduler import Scheduler
from app.core.sentry import init_sentry
from app.core.storage import StorageError, get_storage, sanitize_filename
from app.core.tracing import init_tracing
from app.core.tracing_middleware import TracingAttributesMiddleware

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


def _validate_jwt_keypair(settings: Settings) -> str | None:
    """Return an error string if the configured JWT keypair is missing,
    malformed, or does not match."""
    if not settings.jwt_private_key or not settings.jwt_public_key:
        return "TS_JWT_PRIVATE_KEY and TS_JWT_PUBLIC_KEY are required in production"
    try:
        from cryptography.hazmat.primitives import serialization

        priv_pem = settings.jwt_private_key.get_secret_value().encode()
        pub_pem = settings.jwt_public_key.get_secret_value().encode()
        priv = serialization.load_pem_private_key(priv_pem, password=None)
        pub = serialization.load_pem_public_key(pub_pem)
        if priv.public_key().public_numbers() != pub.public_numbers():
            return "TS_JWT_PRIVATE_KEY and TS_JWT_PUBLIC_KEY do not form a matching pair"
    except Exception:
        return "TS_JWT_PRIVATE_KEY / TS_JWT_PUBLIC_KEY is not a valid RSA keypair"
    return None


def _validate_prod_settings(settings: Settings) -> None:
    """Fail fast in production when unsafe defaults are present."""
    if not settings.is_prod():
        return

    errors: list[str] = []

    jwt_error = _validate_jwt_keypair(settings)
    if jwt_error:
        errors.append(jwt_error)

    if not settings.cors_origin_list() or "*" in settings.cors_origin_list():
        errors.append("TS_CORS_ORIGINS must be explicit in production (no wildcard)")
    if not settings.allowed_host_list() or "*" in settings.allowed_host_list():
        errors.append("TS_ALLOWED_HOSTS must be explicit in production (no wildcard)")

    if not settings.redis_url:
        errors.append("TS_REDIS_URL is required in production")

    # Cookie policy: SameSite=None requires Secure; SameSite must be lax/strict/none.
    samesite = settings.cookie_samesite.lower()
    if samesite not in {"lax", "strict", "none"}:
        errors.append("TS_COOKIE_SAMESITE must be 'lax', 'strict', or 'none'")
    elif samesite == "none" and not settings.cookie_is_secure():
        errors.append("TS_COOKIE_SAMESITE='none' requires Secure cookies in production")

    # Notifications: at least one sender must be configured.
    ses_ok = bool(
        settings.email_from
        and settings.ses_region
        and settings.ses_access_key_id
        and settings.ses_secret_access_key
    )
    msg91_ok = bool(settings.msg91_auth_key and settings.msg91_sender_id)
    if not ses_ok and not msg91_ok:
        errors.append(
            "At least one notification sender is required in production (SES or MSG91)"
        )

    # Billing: whichever payment provider is configured must have its webhook secret.
    if settings.razorpay_key_id or settings.razorpay_key_secret:
        if not settings.razorpay_webhook_secret:
            errors.append("TS_RAZORPAY_WEBHOOK_SECRET is required when Razorpay is configured")
    if settings.stripe_secret_key:
        if not settings.stripe_webhook_secret:
            errors.append("TS_STRIPE_WEBHOOK_SECRET is required when Stripe is configured")
        if not settings.app_url:
            errors.append("TS_APP_URL is required when Stripe is configured")
    # A production deployment must have at least one payment provider configured.
    if not (settings.razorpay_key_id or settings.stripe_secret_key):
        errors.append(
            "At least one payment provider (Razorpay or Stripe) is required in production"
        )

    # Reject obviously dev/test placeholder secrets and short secrets.
    bad_secrets = {"dev-razorpay-secret", "secret", "changeme"}
    for secret_name, secret in (
        ("TS_RAZORPAY_WEBHOOK_SECRET", settings.razorpay_webhook_secret),
        ("TS_STRIPE_WEBHOOK_SECRET", settings.stripe_webhook_secret),
    ):
        if secret:
            secret_val = secret.get_secret_value() or ""
            if secret_val.lower() in bad_secrets or len(secret_val) < 16:
                errors.append(f"{secret_name} is too weak/placeholder")

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

    # Rate limiter: memory by default, Redis when TS_REDIS_URL is set.
    ctx.registry.provide("core.rate_limiter", default_rate_limiter(settings))

    # Scheduler: in-memory stub unless APScheduler is installed and Redis is available.
    scheduler = Scheduler()
    ctx.registry.provide("core.scheduler", scheduler)

    # Celery: async page-streamed document processing (TS-034).
    celery_app = make_celery_app(settings)
    ctx.registry.provide("celery.app", celery_app)

    report: LoadReport = load_modules(settings.enabled_module_names())

    # Sentry is optional; when no DSN is configured this is a no-op.
    init_sentry(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler.start()
        yield
        scheduler.stop()
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

    # Metrics are recorded for every request and exposed at /api/health/metrics.
    if settings.metrics_enabled:
        app.add_middleware(MetricsMiddleware)

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

    @app.get("/api/files/{key:path}")
    async def download_file(
        key: str,
        request: Request,
        principal=Depends(require("viewer")),
    ):
        # Local-storage URLs are generated as /api/files/{stored_key} where the key
        # is workspace-scoped. Enforce that callers can only fetch their own files.
        expected_prefix = f"workspace/{principal.workspace_id}/"
        if not key.startswith(expected_prefix):
            raise HTTPException(404, "not_found")
        storage = get_storage(request.app.state.ctx.settings)
        try:
            data = await storage.read(key)
        except StorageError:
            raise HTTPException(404, "not_found") from None
        filename = sanitize_filename(_pathlib.Path(key).name)
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        # Escape quotes inside the filename to prevent header injection.
        escaped = filename.replace("\\", "\\\\").replace('"', '\\"')
        return StreamingResponse(
            iter([data]),
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{escaped}"'},
        )

    # Access logging and trace enrichment run *inside* the OTel span, so they are
    # registered before init_tracing instruments the app.
    if settings.access_log_enabled:
        app.add_middleware(AccessLogMiddleware)
    app.add_middleware(TracingAttributesMiddleware)

    # OpenTelemetry tracing is opt-in via TS_OTEL_ENABLED; instrument after
    # all routers and middleware are registered.
    init_tracing(app, settings)

    report.loaded = [s for s in report.loaded if s.name not in report.failed]
    return app
