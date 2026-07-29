"""Celery app factory for async document processing (TS-034).

When no Redis URL is configured the app falls back to eager task execution so
local tests and single-container dev work without a broker.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import Settings


def make_celery_app(settings: Settings | None = None) -> Celery:
    settings = settings or Settings()
    broker = settings.redis_url or "memory://"
    backend = settings.redis_url or "cache+memory://"
    app = Celery(
        "tender_shield",
        broker=broker,
        backend=backend,
    )
    # Strict JSON so task args stay safe; eager mode for dev/tests without Redis.
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_track_started=True,
        task_always_eager=not settings.redis_url,
        task_store_eager_result=True,
    )
    app.autodiscover_tasks(["app.modules.ingestion"])
    return app
