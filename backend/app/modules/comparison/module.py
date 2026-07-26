from app.core.module import AppContext, ModuleSpec
from app.modules.comparison.router import router


def setup(ctx: AppContext) -> None:
    pass


module = ModuleSpec(
    name="comparison",
    version="0.1.0",
    router=router,
    soft_deps=("ingestion", "findings", "drafting"),
    setup=setup,
)
