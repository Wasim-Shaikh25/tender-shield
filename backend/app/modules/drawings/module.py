from app.core.module import AppContext, ModuleSpec
from app.modules.drawings.router import router
from app.modules.drawings.service import DrawingService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    reg.provide(
        "drawings.service_factory",
        lambda session: DrawingService(
            session,
            ocr_provider=reg.get("ingestion.ocr"),
        ),
    )


module = ModuleSpec(
    name="drawings",
    version="0.1.0",
    router=router,
    soft_deps=("ingestion",),
    setup=setup,
)
