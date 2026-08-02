from app.core.module import AppContext, ModuleSpec
from app.modules.comparison.router import router
from app.modules.comparison.service import ComparisonService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    reg.provide(
        "comparison.service_factory",
        lambda session: ComparisonService(
            session,
            ingestion_factory=reg.get("ingestion.service_factory"),
            findings_factory=reg.get("findings.store_factory"),
            drafting_factory=reg.get("drafting.service_factory"),
            standards_factory=reg.get("standards.commercial_service_factory"),
        ),
    )


module = ModuleSpec(
    name="comparison",
    version="0.1.0",
    router=router,
    soft_deps=("ingestion", "findings", "drafting", "standards"),
    setup=setup,
)
