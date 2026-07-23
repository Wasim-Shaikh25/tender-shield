import logging
import os

from app.core.module import AppContext, ModuleSpec
from app.modules.assistant.router import router

logger = logging.getLogger(__name__)


def setup(ctx: AppContext) -> None:
    # LLM agent only when a key is present; otherwise the deterministic tools
    # handle the common intents and off-topic questions are refused.
    if os.environ.get("ANTHROPIC_API_KEY"):
        from app.modules.assistant.agent import AnthropicAgent

        ctx.registry.provide("assistant.agent", AnthropicAgent())
    else:
        logger.info("assistant: no ANTHROPIC_API_KEY — grounded tools only (no free-form LLM)")


module = ModuleSpec(
    name="assistant",
    version="0.1.0",
    router=router,
    soft_deps=("ingestion", "findings", "rulepacks", "auth"),
    setup=setup,
)
