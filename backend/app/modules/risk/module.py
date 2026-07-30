import logging
import os

from app.core.config import Settings
from app.core.module import AppContext, ModuleSpec
from app.modules.risk.classifier import NullClassifier, OpenRouterClassifier
from app.modules.risk.router import router

logger = logging.getLogger(__name__)


def setup(ctx: AppContext) -> None:
    # Real LLM classifier only when a key is present; otherwise the null
    # classifier (absence detection still works deterministically).
    settings = Settings()
    key = (
        settings.openrouter_api_key.get_secret_value()
        if settings.openrouter_api_key
        else os.environ.get("OPENROUTER_API_KEY")
    )
    if key:
        ctx.registry.provide("risk.classifier", OpenRouterClassifier())
    else:
        logger.info("risk: no OpenRouter key — using NullClassifier (LLM judgment off)")
        ctx.registry.provide("risk.classifier", NullClassifier())


module = ModuleSpec(
    name="risk",
    version="0.1.0",
    router=router,
    soft_deps=("rulepacks", "ingestion", "auth", "findings"),
    setup=setup,
)
