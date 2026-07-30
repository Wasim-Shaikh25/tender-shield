"""Optional Sentry integration.

Sentry is only enabled when `TS_SENTRY_DSN` is set and the `sentry-sdk` package is
installed. If the package is absent, the feature degrades gracefully with a log.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings

logger = logging.getLogger(__name__)


def init_sentry(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
    except ImportError:  # pragma: no cover - optional dependency
        logger.warning("sentry_sdk not installed; skipping Sentry initialization")
        return

    dsn = settings.sentry_dsn.get_secret_value() if settings.sentry_dsn else ""
    if not dsn:
        return

    environment = settings.sentry_environment or settings.env
    integrations: list[Any] = []
    try:
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        integrations.append(FastApiIntegration(transaction_style="endpoint"))
    except ImportError:
        pass

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=integrations,
    )
    logger.info("Sentry initialized for environment %r", environment)
