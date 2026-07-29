"""Async scheduler wrapper. APScheduler is optional; when absent the scheduler
is a no-op stub that still accepts jobs so the app boots without Redis/APScheduler.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self) -> None:
        self._jobs: list[dict[str, Any]] = []
        self._real: Any = None

    def start(self) -> None:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler

            self._real = AsyncIOScheduler()
            for job in self._jobs:
                self._real.add_job(job["func"], trigger=job["trigger"], **job["kwargs"])
            self._real.start()
            logger.info("scheduler started (APScheduler)")
        except ImportError:
            logger.warning("scheduler: APScheduler not installed; jobs are queued in memory only")
        except Exception as exc:
            logger.warning("scheduler failed to start: %s", exc)

    def add_job(
        self,
        func: Callable[..., Any],
        trigger: str = "interval",
        *,
        seconds: int | None = None,
        minutes: int | None = None,
        hours: int | None = None,
        days: int | None = None,
        run_date: datetime | None = None,
        misfire_grace_time: int = 3600,
    ) -> None:
        kwargs: dict[str, Any] = {"misfire_grace_time": misfire_grace_time}
        if seconds is not None:
            kwargs["seconds"] = seconds
        if minutes is not None:
            kwargs["minutes"] = minutes
        if hours is not None:
            kwargs["hours"] = hours
        if days is not None:
            kwargs["days"] = days
        if run_date is not None:
            kwargs["run_date"] = run_date

        if trigger == "interval":
            # sane default so tests don't spin
            if not any(k in kwargs for k in ("seconds", "minutes", "hours", "days")):
                kwargs["minutes"] = 60

        if self._real is not None:
            self._real.add_job(func, trigger=trigger, **kwargs)
        else:
            self._jobs.append({"func": func, "trigger": trigger, "kwargs": kwargs})

    def stop(self) -> None:
        if self._real is not None:
            self._real.shutdown()

    async def run_queued_once(self) -> None:
        """Dev/test helper to fire all queued jobs immediately."""
        for job in self._jobs:
            if asyncio.iscoroutinefunction(job["func"]):
                await job["func"]()
            else:
                job["func"]()
