"""Per-review cost instrumentation (TS-223).

Answers one question the product cannot price without: **what does one completed
tender review actually cost?** Every LLM call, OCR page, worker-second and stored
byte is attributed to the review that caused it, tagged with the model and
rulepack version in force.

Design notes:

* **Money is in minor units** (paise/cents), never float rupees — `CLAUDE.md` §4.
  Token prices are configured per million tokens in minor units, and per-call cost
  is rounded once, at the end, using banker-free integer arithmetic.
* **Prices are configuration, not code.** There is no built-in price table: rates
  differ per provider, per contract and over time. An unpriced model still records
  its token counts and is reported as unpriced, so cost is never silently
  understated.
* **The meter never breaks a review.** Instrumentation failures are logged and
  swallowed; a missing price or an unparseable usage object degrades to "tokens
  counted, cost unknown".
* **Retrieval-first is a cost property, not just an architecture preference**
  (Strategy Doc §G.3). The token ceiling exists so that a change which starts
  sending whole documents to a model shows up as a failure rather than a bill.
"""

from __future__ import annotations

import contextvars
import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from app.core.metrics import METRICS as metrics

logger = logging.getLogger(__name__)

# Prices are quoted per *million* tokens so the configured integers stay readable.
_PER_MILLION = 1_000_000


@dataclass
class LlmUsage:
    """One metered model call."""

    model: str
    stage: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cost_minor: int | None = None  # None → model has no configured price

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class ReviewCost:
    """Accumulated cost for a single tender review."""

    opportunity_id: str | None = None
    rulepack_version: str | None = None
    calls: list[LlmUsage] = field(default_factory=list)
    ocr_pages: int = 0
    worker_seconds: float = 0.0
    storage_bytes: int = 0
    started_at: float = field(default_factory=time.monotonic)

    # ---- aggregates -----------------------------------------------------

    @property
    def prompt_tokens(self) -> int:
        return sum(c.prompt_tokens for c in self.calls)

    @property
    def completion_tokens(self) -> int:
        return sum(c.completion_tokens for c in self.calls)

    @property
    def cached_tokens(self) -> int:
        return sum(c.cached_tokens for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def llm_cost_minor(self) -> int:
        return sum(c.cost_minor or 0 for c in self.calls)

    @property
    def unpriced_models(self) -> set[str]:
        return {c.model for c in self.calls if c.cost_minor is None}

    @property
    def fully_priced(self) -> bool:
        """False when any call used a model with no configured price."""
        return not self.unpriced_models

    @property
    def wall_seconds(self) -> float:
        return time.monotonic() - self.started_at

    def summary(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "rulepack_version": self.rulepack_version,
            "llm_calls": len(self.calls),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cached_tokens": self.cached_tokens,
            "total_tokens": self.total_tokens,
            "llm_cost_minor": self.llm_cost_minor,
            "fully_priced": self.fully_priced,
            "unpriced_models": sorted(self.unpriced_models),
            "ocr_pages": self.ocr_pages,
            "worker_seconds": round(self.worker_seconds, 3),
            "storage_bytes": self.storage_bytes,
            "wall_seconds": round(self.wall_seconds, 3),
            "by_stage": self.by_stage(),
        }

    def by_stage(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for call in self.calls:
            bucket = out.setdefault(
                call.stage,
                {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_minor": 0},
            )
            bucket["calls"] += 1
            bucket["prompt_tokens"] += call.prompt_tokens
            bucket["completion_tokens"] += call.completion_tokens
            bucket["cost_minor"] += call.cost_minor or 0
        return out


_current: contextvars.ContextVar[ReviewCost | None] = contextvars.ContextVar(
    "ts_review_cost", default=None
)


def current_scope() -> ReviewCost | None:
    """The review currently being metered, if any."""
    return _current.get()


def _price_table() -> dict[str, dict[str, int]]:
    """Parse `TS_LLM_PRICE_TABLE` — JSON mapping model → per-million minor units.

    Example:
        {"anthropic/claude-sonnet-4": {"input": 300, "output": 1500, "cached_input": 30}}

    Returns an empty table (everything unpriced) when unset or unparseable.
    """
    from app.core.config import Settings

    raw = Settings().llm_price_table
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("TS_LLM_PRICE_TABLE is not valid JSON; treating all models as unpriced")
        return {}
    if not isinstance(parsed, dict):
        logger.warning("TS_LLM_PRICE_TABLE must be a JSON object; treating all models as unpriced")
        return {}
    return parsed


def _cost_minor(
    model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int
) -> int | None:
    """Integer minor-unit cost for one call, or None when the model has no price."""
    prices = _price_table().get(model)
    if not isinstance(prices, dict):
        return None
    try:
        per_in = int(prices.get("input", 0))
        per_out = int(prices.get("output", 0))
        per_cached = int(prices.get("cached_input", per_in))
    except (TypeError, ValueError):
        logger.warning("Malformed price entry for model %s; treating as unpriced", model)
        return None

    # Cached tokens are billed at the cached rate and are a subset of prompt tokens.
    fresh_prompt = max(prompt_tokens - cached_tokens, 0)
    total = (
        fresh_prompt * per_in + cached_tokens * per_cached + completion_tokens * per_out
    )
    # One rounding, at the end, away from zero.
    return (total + _PER_MILLION // 2) // _PER_MILLION


def record_llm_usage(
    *,
    model: str,
    stage: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cached_tokens: int = 0,
) -> LlmUsage:
    """Record one model call against the active review (and always against metrics)."""
    usage = LlmUsage(
        model=model,
        stage=stage,
        prompt_tokens=max(int(prompt_tokens or 0), 0),
        completion_tokens=max(int(completion_tokens or 0), 0),
        cached_tokens=max(int(cached_tokens or 0), 0),
    )
    usage.cost_minor = _cost_minor(
        model, usage.prompt_tokens, usage.completion_tokens, usage.cached_tokens
    )

    metrics.inc("ts_llm_calls_total")
    metrics.inc("ts_llm_prompt_tokens_total", usage.prompt_tokens)
    metrics.inc("ts_llm_completion_tokens_total", usage.completion_tokens)
    metrics.inc("ts_llm_cached_tokens_total", usage.cached_tokens)
    if usage.cost_minor is not None:
        metrics.inc("ts_llm_cost_minor_total", usage.cost_minor)
    else:
        metrics.inc("ts_llm_unpriced_calls_total")

    scope = _current.get()
    if scope is not None:
        scope.calls.append(usage)
    return usage


def record_ocr_pages(pages: int) -> None:
    metrics.inc("ts_ocr_pages_total", max(int(pages or 0), 0))
    scope = _current.get()
    if scope is not None:
        scope.ocr_pages += max(int(pages or 0), 0)


def record_worker_seconds(seconds: float) -> None:
    value = max(float(seconds or 0.0), 0.0)
    metrics.observe("ts_worker_seconds", value)
    scope = _current.get()
    if scope is not None:
        scope.worker_seconds += value


def record_storage_bytes(size: int) -> None:
    value = max(int(size or 0), 0)
    metrics.inc("ts_storage_bytes_total", value)
    scope = _current.get()
    if scope is not None:
        scope.storage_bytes += value


@contextmanager
def review_cost_scope(
    *, opportunity_id: str | None = None, rulepack_version: str | None = None
):
    """Meter everything that happens inside this block as one tender review.

    Nesting is allowed but does not stack: the inner scope becomes the active one
    and the outer scope resumes on exit, so a nested sub-pipeline is attributed to
    itself rather than double-counted into its parent.
    """
    scope = ReviewCost(opportunity_id=opportunity_id, rulepack_version=rulepack_version)
    token = _current.set(scope)
    try:
        yield scope
    finally:
        _current.reset(token)
        _emit_review_metrics(scope)


def _emit_review_metrics(scope: ReviewCost) -> None:
    """Emit per-review aggregates. Never raises."""
    try:
        from app.core.config import Settings

        settings = Settings()
        metrics.inc("ts_reviews_metered_total")
        metrics.observe("ts_review_total_tokens", float(scope.total_tokens))
        metrics.observe("ts_review_wall_seconds", scope.wall_seconds)
        if scope.fully_priced:
            # Only fully-priced reviews feed the cost histogram; a partially priced
            # review would understate p50/p95 and make the number a lie.
            metrics.observe("ts_review_cost_minor", float(scope.llm_cost_minor))
        else:
            metrics.inc("ts_review_unpriced_total")

        ceiling = settings.max_tokens_per_review
        if ceiling and scope.total_tokens > ceiling:
            metrics.inc("ts_review_token_ceiling_exceeded_total")
            logger.warning(
                "Review exceeded the token ceiling: %s tokens > %s "
                "(opportunity=%s, rulepack=%s). Retrieval-first may be broken — "
                "check whether whole documents are reaching the model.",
                scope.total_tokens,
                ceiling,
                scope.opportunity_id,
                scope.rulepack_version,
            )

        logger.info("review cost: %s", json.dumps(scope.summary(), default=str))
    except Exception:  # pragma: no cover - instrumentation must never break a review
        logger.exception("cost metering failed; review itself is unaffected")
