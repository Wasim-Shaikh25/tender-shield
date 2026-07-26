from app.core.module import AppContext, ModuleSpec
from app.modules.analytics.router import router
from app.modules.analytics.service import AnalyticsService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    reg.provide(
        "analytics.service_factory",
        lambda session: AnalyticsService(
            session,
            findings_factory=reg.get("findings.store_factory"),
            ingestion_factory=reg.get("ingestion.service_factory"),
        ),
    )


module = ModuleSpec(
    name="analytics",
    version="0.1.0",
    router=router,
    soft_deps=("findings", "ingestion"),
    setup=setup,
)
