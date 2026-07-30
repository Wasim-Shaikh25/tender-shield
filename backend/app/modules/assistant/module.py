import logging
import os

from app.core.config import Settings
from app.core.module import AppContext, ModuleSpec
from app.modules.assistant.router import router

logger = logging.getLogger(__name__)


def setup(ctx: AppContext) -> None:
    # LLM agent only when a key is present; otherwise the deterministic tools
    # handle the common intents and off-topic questions are refused.
    settings = Settings()
    key = (
        settings.openrouter_api_key.get_secret_value()
        if settings.openrouter_api_key
        else os.environ.get("OPENROUTER_API_KEY")
    )
    if key:
        from app.modules.assistant.agent import OpenRouterAgent

        ctx.registry.provide("assistant.agent", OpenRouterAgent())
    else:
        logger.info("assistant: no OpenRouter key — grounded tools only (no free-form LLM)")


module = ModuleSpec(
    name="assistant",
    version="0.1.0",
    router=router,
    soft_deps=("ingestion", "findings", "rulepacks", "auth"),
    setup=setup,
)
