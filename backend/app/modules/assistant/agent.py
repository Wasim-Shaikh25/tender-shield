"""Injected LLM boundary for free-form assistant questions (Doc §8). Answers
ONLY from tool results (grounded-only); refuses when nothing relevant. Without
an API key the assistant never reaches here (deterministic tools handle the
common intents), so this stays a thin, swappable adapter."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are TenderShield's assistant for tender review. Answer ONLY from the "
    "TOOL RESULTS provided; if nothing relevant is there, say so. Cite every "
    "factual claim with [p<page>]. Legal/commercial conclusions are considerations, "
    "never certainties. Refuse anything unrelated to this workspace's tenders."
)


class AnthropicAgent:
    def __init__(self, model: str = "claude-3-5-sonnet-20241022", max_tokens: int = 700):
        self.model = model
        self.max_tokens = max_tokens

    def answer(self, message: str, context: dict) -> str:
        import anthropic

        client = anthropic.Anthropic()
        try:
            msg = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0,
                system=_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"QUESTION: {message}\n\nTOOL RESULTS (the only facts you may use):\n"
                            f"{json.dumps(context, default=str)}"
                        ),
                    }
                ],
            )
            return msg.content[0].text
        except Exception:
            logger.exception("AnthropicAgent failed")
            return "I couldn't complete that request just now — please try a specific query."
