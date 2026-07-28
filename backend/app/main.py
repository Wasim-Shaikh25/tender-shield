"""FastAPI application factory: loads enabled modules and wires them up."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings
from app.core.db import install_rls_rebinding, make_engine, make_session_factory
from app.core.events import EventBus
from app.core.loader import LoadReport, load_modules
from app.core.module import AppContext
from app.core.registry import ServiceRegistry

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    ctx = AppContext(settings=settings, registry=ServiceRegistry(), events=EventBus())

    # Shared DB: published as a capability so modules consume the session factory
    # via the registry rather than importing it (keeps them pluggable).
    if settings.database_url:
        engine = make_engine(settings)
        session_factory = make_session_factory(engine)
        install_rls_rebinding(session_factory)  # R-001 §B.5 — survive mid-request commits
        ctx.registry.provide("db.engine", engine)
        ctx.registry.provide("db.sessionmaker", session_factory)

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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_methods=["*"],
        allow_headers=["*"],
    )
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
