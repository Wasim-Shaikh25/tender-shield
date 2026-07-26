from app.core.module import AppContext, ModuleSpec
from app.modules.qualification.router import router
from app.modules.qualification.service import QualificationService


def setup(ctx: AppContext) -> None:
    ctx.registry.provide(
        "qualification.service_factory",
        lambda session: QualificationService(
            session,
            ingestion_factory=ctx.registry.get("ingestion.service_factory"),
            store_factory=ctx.registry.get("findings.store_factory"),
        ),
    )


module = ModuleSpec(
    name="qualification",
    version="0.1.0",
    router=router,
    soft_deps=("ingestion", "findings", "auth"),
    setup=setup,
)
