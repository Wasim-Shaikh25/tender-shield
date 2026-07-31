import logging
import os

from app.core.config import Settings
from app.core.module import AppContext, ModuleSpec
from app.modules.risk.classifier import NullClassifier, OpenRouterClassifier
from app.modules.risk.router import router
from app.modules.risk.service import RiskService

logger = logging.getLogger(__name__)


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
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

    def service_factory(session):
        return RiskService(
            session,
            ingestion_factory=reg.get("ingestion.service_factory"),
            loader=reg.get("rulepacks.loader"),
            classifier=reg.get("risk.classifier"),
            store_factory=reg.get("findings.store_factory"),
            workspace_factory=reg.get("auth.workspace_factory"),
            settings=settings,
        )

    reg.provide("risk.service_factory", service_factory)
    reg.provide(
        "risk.run_opportunity",
        lambda session, workspace_id, opportunity_id: service_factory(session).run_opportunity(
            workspace_id, opportunity_id
        ),
    )


module = ModuleSpec(
    name="risk",
    version="0.1.0",
    router=router,
    soft_deps=("rulepacks", "ingestion", "auth", "findings"),
    setup=setup,
)
