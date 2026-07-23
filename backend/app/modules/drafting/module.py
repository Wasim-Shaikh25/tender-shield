from app.core.module import AppContext, ModuleSpec
from app.modules.drafting.router import router
from app.modules.drafting.service import DraftingService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    reg.provide(
        "drafting.service_factory",
        lambda session: DraftingService(session, store_factory=reg.get("findings.store_factory")),
    )


module = ModuleSpec(
    name="drafting",
    version="0.1.0",
    router=router,
    soft_deps=("findings", "ingestion", "review", "auth"),
    setup=setup,
)
