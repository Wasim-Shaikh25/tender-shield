"""Request/response access logging middleware.

Logs one line per HTTP request with method, path, status, duration, user, and
workspace. Optional request/response body logging is gated by TS_LOG_REQUEST_BODIES
and limited to small previews with sensitive-key redaction.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("tendershield.access")

MAX_BODY_LOG_BYTES = 4096
SENSITIVE_KEYS = {"password", "token", "secret", "credit_card", "pan", "api_key"}


def _redact(text: str) -> str:
    for key in SENSITIVE_KEYS:
        text = re.sub(
            rf"(\W?){re.escape(key)}(\W*)(\"?)[^\"\s,}}]{{3,}}",
            rf"\1{key}\2\3***REDACTED***",
            text,
            flags=re.IGNORECASE,
        )
    return text[:MAX_BODY_LOG_BYTES]


def _peek_body(request) -> str:
    # Body is already consumed by the time the middleware finishes; capturing it
    # would require a streaming tee. For now this is a safe no-op.
    return ""


def _principal_attrs(request) -> dict[str, Any]:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        return {}
    return {
        "user_id": str(getattr(principal, "user_id", None) or "-"),
        "workspace_id": str(getattr(principal, "workspace_id", None) or "-"),
        "role": getattr(principal, "role", None) or "-",
    }


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log a structured access line for every HTTP request/response."""

    async def dispatch(self, request, call_next):
        request_id = (
            request.headers.get("x-request-id")
            or request.headers.get("traceparent")
            or "-"
        )
        request.state.request_id = request_id

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        if "x-request-id" not in response.headers:
            response.headers["x-request-id"] = request_id

        attrs = _principal_attrs(request)
        user_id = attrs.get("user_id", "-")
        workspace_id = attrs.get("workspace_id", "-")
        role = attrs.get("role", "-")

        msg = (
            f"{request.method} {request.url.path} {response.status_code} "
            f"{duration_ms}ms user={user_id} workspace={workspace_id} role={role} "
            f"request_id={request_id}"
        )

        settings = getattr(request.app.state, "ctx", None)
        settings_obj = settings.settings if settings else None
        if getattr(settings_obj, "log_request_bodies", False):
            body_preview = _peek_body(request)
            if body_preview:
                msg += f" body_preview={_redact(body_preview)}"

        logger.info(msg)
        return response
