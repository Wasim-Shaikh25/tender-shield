from app.core.module import AppContext, ModuleSpec
from app.modules.baseline.router import router
from app.modules.baseline.service import BaselineService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    # Published for future phases (notice countdowns) to consume the frozen
    # graph via capability. Findings/review/ingestion are soft deps resolved
    # lazily — the module degrades (freeze refused) when they are absent.
    reg.provide(
        "baseline.service_factory",
        lambda session: BaselineService(
            session,
            findings_factory=reg.get("findings.store_factory"),
            review_factory=reg.get("review.service_factory"),
            ingestion_factory=reg.get("ingestion.service_factory"),
            publish=ctx.events.publish,
        ),
    )


module = ModuleSpec(
    name="baseline",
    version="0.1.0",
    router=router,
    soft_deps=("findings", "review", "ingestion", "auth"),
    setup=setup,
)
