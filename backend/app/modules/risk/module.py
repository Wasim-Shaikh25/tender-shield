import logging
import os

from app.core.module import AppContext, ModuleSpec
from app.modules.risk.classifier import AnthropicClassifier, NullClassifier
from app.modules.risk.router import router

logger = logging.getLogger(__name__)


def setup(ctx: AppContext) -> None:
    # Real LLM classifier only when a key is present; otherwise the null
    # classifier (absence detection still works deterministically).
    if os.environ.get("ANTHROPIC_API_KEY"):
        ctx.registry.provide("risk.classifier", AnthropicClassifier())
    else:
        logger.info("risk: no ANTHROPIC_API_KEY — using NullClassifier (LLM judgment off)")
        ctx.registry.provide("risk.classifier", NullClassifier())


module = ModuleSpec(
    name="risk",
    version="0.1.0",
    router=router,
    soft_deps=("rulepacks", "ingestion", "auth", "findings"),
    setup=setup,
)
