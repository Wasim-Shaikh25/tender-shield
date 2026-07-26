from app.core.module import AppContext, ModuleSpec
from app.modules.timeline.router import router
from app.modules.timeline.service import TimelineService


def setup(ctx: AppContext) -> None:
    ctx.registry.provide(
        "timeline.service_factory",
        lambda session: TimelineService(
            session,
            ingestion_factory=ctx.registry.get("ingestion.service_factory"),
        ),
    )


module = ModuleSpec(
    name="timeline",
    version="0.1.0",
    router=router,
    soft_deps=("ingestion", "auth"),
    setup=setup,
)
