"""Middleware that enriches the current OpenTelemetry span with request context.

It runs inside the OTel-instrumented request, so `trace.get_current_span()` returns
a real span. It copies principal fields and path parameters (e.g. `ticket_id`) onto
that span as attributes, making Jaeger/Grafana queries like
`user.id = <uuid>` and `ticket.id = <uuid>` possible.
"""

from __future__ import annotations

import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

_SPAN_ATTRS = {
    "user_id": "user.id",
    "workspace_id": "workspace.id",
    "role": "user.role",
    "is_superadmin": "user.is_superadmin",
    "email_verified": "user.email_verified",
    "mobile_verified": "user.mobile_verified",
}

# Path parameters that should be lifted to span attributes for support/debugging.
_ENTITY_PARAMS = {"ticket_id", "opportunity_id", "user_id", "workspace_id"}


def _set_attr(span, key: str, value: Any) -> None:
    if value is None or value == "":
        return
    if isinstance(value, bool):
        span.set_attribute(key, value)
    else:
        span.set_attribute(key, str(value))


class TracingAttributesMiddleware(BaseHTTPMiddleware):
    """Add user/workspace/path entity attributes to the active OTel span."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if span is not None and span.is_recording():
                # Principal set by app.core.deps.current_principal during the route.
                principal = getattr(request.state, "principal", None)
                if principal is not None:
                    for field, attr_name in _SPAN_ATTRS.items():
                        _set_attr(span, attr_name, getattr(principal, field, None))

                # Lift known path parameters (e.g. /tickets/{ticket_id})
                for param in _ENTITY_PARAMS:
                    value = request.path_params.get(param)
                    if value:
                        entity = param.replace("_id", "").replace("_", ".")
                        _set_attr(span, f"{entity}.id", value)

                request_id = getattr(request.state, "request_id", None) or request.headers.get(
                    "x-request-id"
                )
                if request_id:
                    _set_attr(span, "http.request_id", request_id)
        except Exception:
            logger.exception("failed to enrich trace attributes")

        return response
