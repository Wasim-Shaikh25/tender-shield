"""Structured logging configuration for TenderShield.

- `tendershield.access` is the per-request access logger. It writes a human-readable
  line to stdout and a JSON line to a rotated file (default `logs/tendershield-access.log`).
- The root logger can also write JSON to `logs/tendershield-app.log` so application
  logs are persisted and searchable alongside access logs.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from typing import Any

ACCESS_LOGGER_NAME = "tendershield.access"

_RESERVED_RECORD_KEYS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "process",
    "processName",
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Format a LogRecord as a single-line JSON object.

    Extra fields attached via `extra={...}` are included in the JSON payload so
    they can be searched in Loki/Grafana.
    """

    def format(self, record: logging.LogRecord) -> str:
        fields: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            fields["exc_info"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_KEYS or key.startswith("_"):
                continue
            fields[key] = value
        return json.dumps(fields, default=str)


def _ensure_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def _add_file_handler(
    logger: logging.Logger,
    path: str,
    max_bytes: int,
    backup_count: int,
    json_format: bool,
) -> None:
    _ensure_dir(path)
    absolute_path = os.path.abspath(path)
    for handler in logger.handlers:
        if (
            isinstance(handler, logging.handlers.RotatingFileHandler)
            and getattr(handler, "baseFilename", "") == absolute_path
        ):
            return
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=max_bytes, backupCount=backup_count
    )
    if json_format:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(handler)


def _add_stdout_handler(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout:
            return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(handler)


def configure_logging(settings) -> None:
    """Set up persistent, structured logging.

    Called once from `create_app`. Safe to call multiple times (idempotent).
    """
    access_logger = logging.getLogger(ACCESS_LOGGER_NAME)
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False
    _add_stdout_handler(access_logger)
    _add_file_handler(
        access_logger,
        settings.log_file,
        settings.log_max_bytes,
        settings.log_backup_count,
        json_format=settings.log_json,
    )

    # Persist all application logs to a separate rotated file at INFO.
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    _add_file_handler(
        root,
        settings.app_log_file,
        settings.log_max_bytes,
        settings.log_backup_count,
        json_format=settings.log_json,
    )
