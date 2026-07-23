from app.core.module import AppContext, ModuleSpec
from app.modules.boq.router import router
from app.modules.boq.service import BoqEngine


def setup(ctx: AppContext) -> None:
    # rulepacks is a SOFT dependency resolved lazily at call time, so setup
    # order is irrelevant and a disabled rulepacks module degrades gracefully.
    ctx.registry.provide(
        "boq.engine",
        BoqEngine(loader_provider=lambda: ctx.registry.get("rulepacks.loader")),
    )


module = ModuleSpec(
    name="boq",
    version="0.1.0",
    router=router,
    soft_deps=("rulepacks", "findings", "ingestion"),
    setup=setup,
)
