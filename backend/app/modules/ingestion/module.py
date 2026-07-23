from app.core.module import AppContext, ModuleSpec
from app.modules.ingestion.router import router
from app.modules.ingestion.service import IngestionService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    # Published so risk/boq/drafting can resolve opportunities without importing
    # ingestion. rulepacks + auth are soft deps resolved lazily.
    reg.provide(
        "ingestion.service_factory",
        lambda session: IngestionService(
            session,
            loader_provider=lambda: reg.get("rulepacks.loader"),
            publish=ctx.events.publish,
        ),
    )


module = ModuleSpec(
    name="ingestion",
    version="0.1.0",
    router=router,
    soft_deps=("rulepacks", "auth"),
    setup=setup,
)
