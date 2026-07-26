from app.core.module import AppContext, ModuleSpec
from app.modules.crossref.router import router
from app.modules.crossref.service import CrossRefService


def setup(ctx: AppContext) -> None:
    ctx.registry.provide(
        "crossref.service_factory",
        lambda session: CrossRefService(
            session, ingestion_factory=ctx.registry.get("ingestion.service_factory")
        ),
    )


module = ModuleSpec(
    name="crossref",
    version="0.1.0",
    router=router,
    soft_deps=("ingestion", "auth"),
    setup=setup,
)
