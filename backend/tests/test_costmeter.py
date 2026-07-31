"""Tests for per-review cost instrumentation (TS-223).

Covers the cost arithmetic (integer minor units, never float), review-scoped
attribution, honest handling of unpriced models, the metering wrapper on the LLM
client, and the token ceiling that guards the retrieval-first cost property.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.core import costmeter
from app.core.costmeter import (
    ReviewCost,
    current_scope,
    record_llm_usage,
    record_ocr_pages,
    record_storage_bytes,
    record_worker_seconds,
    review_cost_scope,
)
from app.core.llm import MeteredClient

MODEL = "test/model-a"
PRICES = json.dumps(
    {MODEL: {"input": 300, "output": 1500, "cached_input": 30}}  # minor units per 1M tokens
)


@pytest.fixture
def priced(monkeypatch):
    monkeypatch.setenv("TS_LLM_PRICE_TABLE", PRICES)
    yield


# ---------------------------------------------------------------- cost maths


def test_cost_is_integer_minor_units(priced):
    with review_cost_scope(opportunity_id="opp-1") as scope:
        record_llm_usage(
            model=MODEL, stage="risk.classify", prompt_tokens=1_000_000, completion_tokens=0
        )
    assert scope.llm_cost_minor == 300
    assert isinstance(scope.llm_cost_minor, int)


def test_output_tokens_priced_separately(priced):
    with review_cost_scope() as scope:
        record_llm_usage(
            model=MODEL, stage="s", prompt_tokens=1_000_000, completion_tokens=1_000_000
        )
    assert scope.llm_cost_minor == 300 + 1500


def test_cached_tokens_billed_at_cached_rate(priced):
    """Cached tokens are a subset of prompt tokens and cost less."""
    with review_cost_scope() as scope:
        record_llm_usage(
            model=MODEL,
            stage="s",
            prompt_tokens=1_000_000,
            completion_tokens=0,
            cached_tokens=1_000_000,
        )
    assert scope.llm_cost_minor == 30


def test_unpriced_model_counts_tokens_but_not_cost():
    """An unpriced model must never be silently costed at zero."""
    with review_cost_scope() as scope:
        record_llm_usage(model="unknown/model", stage="s", prompt_tokens=5_000)
    assert scope.total_tokens == 5_000
    assert scope.fully_priced is False
    assert scope.unpriced_models == {"unknown/model"}


def test_malformed_price_table_degrades_to_unpriced(monkeypatch):
    monkeypatch.setenv("TS_LLM_PRICE_TABLE", "{not json")
    with review_cost_scope() as scope:
        record_llm_usage(model=MODEL, stage="s", prompt_tokens=1_000)
    assert scope.fully_priced is False


def test_negative_token_counts_are_clamped(priced):
    with review_cost_scope() as scope:
        record_llm_usage(model=MODEL, stage="s", prompt_tokens=-5, completion_tokens=-1)
    assert scope.total_tokens == 0


# ------------------------------------------------------------ review scoping


def test_usage_outside_a_scope_does_not_raise():
    assert current_scope() is None
    usage = record_llm_usage(model=MODEL, stage="s", prompt_tokens=10)
    assert usage.prompt_tokens == 10


def test_scope_aggregates_all_cost_drivers(priced):
    with review_cost_scope(opportunity_id="opp-9", rulepack_version="2026.07.1") as scope:
        record_llm_usage(model=MODEL, stage="risk.classify", prompt_tokens=2_000)
        record_llm_usage(model=MODEL, stage="assistant.chat", prompt_tokens=1_000)
        record_ocr_pages(12)
        record_worker_seconds(3.5)
        record_storage_bytes(2048)

    summary = scope.summary()
    assert summary["opportunity_id"] == "opp-9"
    assert summary["rulepack_version"] == "2026.07.1"
    assert summary["llm_calls"] == 2
    assert summary["prompt_tokens"] == 3_000
    assert summary["ocr_pages"] == 12
    assert summary["worker_seconds"] == 3.5
    assert summary["storage_bytes"] == 2048


def test_by_stage_attribution(priced):
    with review_cost_scope() as scope:
        record_llm_usage(model=MODEL, stage="risk.classify", prompt_tokens=1_000)
        record_llm_usage(model=MODEL, stage="risk.classify", prompt_tokens=1_000)
        record_llm_usage(model=MODEL, stage="analytics.plan", prompt_tokens=500)

    by_stage = scope.by_stage()
    assert by_stage["risk.classify"]["calls"] == 2
    assert by_stage["risk.classify"]["prompt_tokens"] == 2_000
    assert by_stage["analytics.plan"]["calls"] == 1


def test_nested_scopes_do_not_double_count(priced):
    with review_cost_scope(opportunity_id="outer") as outer:
        record_llm_usage(model=MODEL, stage="s", prompt_tokens=100)
        with review_cost_scope(opportunity_id="inner") as inner:
            record_llm_usage(model=MODEL, stage="s", prompt_tokens=900)
        record_llm_usage(model=MODEL, stage="s", prompt_tokens=100)

    assert inner.total_tokens == 900
    assert outer.total_tokens == 200  # inner work is attributed to inner only


def test_scope_closes_even_when_the_body_raises(priced):
    with pytest.raises(ValueError):
        with review_cost_scope():
            record_llm_usage(model=MODEL, stage="s", prompt_tokens=10)
            raise ValueError("boom")
    assert current_scope() is None


# --------------------------------------------------- metered client wrapper


class _FakeCompletions:
    def __init__(self, usage):
        self._usage = usage
        self.seen: list[dict] = []

    def create(self, **kwargs):
        self.seen.append(kwargs)
        return SimpleNamespace(usage=self._usage, model=kwargs.get("model"))


class _FakeChat:
    def __init__(self, usage):
        self.completions = _FakeCompletions(usage)


class _FakeClient:
    def __init__(self, usage):
        self.chat = _FakeChat(usage)
        self.other_attribute = "passthrough"


def test_metered_client_records_usage(priced):
    usage = SimpleNamespace(
        prompt_tokens=1_000,
        completion_tokens=200,
        prompt_tokens_details=SimpleNamespace(cached_tokens=400),
    )
    client = MeteredClient(_FakeClient(usage), stage="risk.classify")

    with review_cost_scope() as scope:
        client.chat.completions.create(model=MODEL, messages=[])

    assert scope.calls[0].prompt_tokens == 1_000
    assert scope.calls[0].completion_tokens == 200
    assert scope.calls[0].cached_tokens == 400
    assert scope.calls[0].stage == "risk.classify"


def test_metered_client_passes_other_attributes_through(priced):
    client = MeteredClient(_FakeClient(None), stage="s")
    assert client.other_attribute == "passthrough"


def test_metering_failure_never_breaks_the_call(priced):
    """A response whose usage object explodes must still be returned."""

    class Exploding:
        @property
        def prompt_tokens(self):
            raise RuntimeError("provider changed the shape")

    client = MeteredClient(_FakeClient(Exploding()), stage="s")
    with review_cost_scope() as scope:
        response = client.chat.completions.create(model=MODEL, messages=[])

    assert response is not None
    assert scope.calls == []


def test_response_without_usage_is_tolerated(priced):
    client = MeteredClient(_FakeClient(None), stage="s")
    with review_cost_scope() as scope:
        client.chat.completions.create(model=MODEL, messages=[])
    assert scope.calls == []


# ------------------------------------------- retrieval-first cost guardrail


def test_token_ceiling_flags_a_runaway_review(priced, monkeypatch, caplog):
    """Cost must scale with pattern count, not document length (Strategy §G.3).

    If a change starts sending whole documents to the model, this is where it
    surfaces — as a warning and a metric, not as a bill.
    """
    monkeypatch.setenv("TS_MAX_TOKENS_PER_REVIEW", "1000")
    with caplog.at_level("WARNING"):
        with review_cost_scope(opportunity_id="opp-runaway"):
            record_llm_usage(model=MODEL, stage="risk.classify", prompt_tokens=50_000)

    assert any("token ceiling" in r.message.lower() for r in caplog.records)


def test_token_ceiling_silent_when_within_budget(priced, monkeypatch, caplog):
    monkeypatch.setenv("TS_MAX_TOKENS_PER_REVIEW", "1000000")
    with caplog.at_level("WARNING"):
        with review_cost_scope():
            record_llm_usage(model=MODEL, stage="risk.classify", prompt_tokens=5_000)

    assert not any("token ceiling" in r.message.lower() for r in caplog.records)


def test_ceiling_of_zero_disables_the_check(priced, monkeypatch, caplog):
    monkeypatch.setenv("TS_MAX_TOKENS_PER_REVIEW", "0")
    with caplog.at_level("WARNING"):
        with review_cost_scope():
            record_llm_usage(model=MODEL, stage="s", prompt_tokens=10_000_000)

    assert not any("token ceiling" in r.message.lower() for r in caplog.records)


def test_partially_priced_review_is_excluded_from_the_cost_histogram(priced, monkeypatch):
    """A partially priced review would understate p50/p95, so it must not be observed."""
    observed: list[tuple[str, float]] = []
    monkeypatch.setattr(
        costmeter.metrics, "observe", lambda name, value: observed.append((name, value))
    )

    with review_cost_scope():
        record_llm_usage(model=MODEL, stage="s", prompt_tokens=1_000)
        record_llm_usage(model="unpriced/model", stage="s", prompt_tokens=1_000)

    assert not any(name == "ts_review_cost_minor" for name, _ in observed)


def test_fully_priced_review_feeds_the_cost_histogram(priced, monkeypatch):
    observed: list[tuple[str, float]] = []
    monkeypatch.setattr(
        costmeter.metrics, "observe", lambda name, value: observed.append((name, value))
    )

    with review_cost_scope():
        record_llm_usage(model=MODEL, stage="s", prompt_tokens=1_000_000)

    assert ("ts_review_cost_minor", 300.0) in observed


def test_empty_review_reports_zero_not_none():
    scope = ReviewCost()
    assert scope.total_tokens == 0
    assert scope.llm_cost_minor == 0
    assert scope.fully_priced is True
