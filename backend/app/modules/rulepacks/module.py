from app.core.module import AppContext, ModuleSpec
from app.modules.rulepacks.correction_service import CorrectionService
from app.modules.rulepacks.loader import RulePackLoader
from app.modules.rulepacks.router import router


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    loader = RulePackLoader(ctx.settings.rulepacks_dir or None)
    reg.provide("rulepacks.loader", loader)

    def correction_factory(session):
        return CorrectionService(
            session,
            findings_factory=reg.get("findings.store_factory"),
            ingestion_factory=reg.get("ingestion.service_factory"),
            publish=ctx.events.publish,
        )

    reg.provide("rulepacks.correction_factory", correction_factory)


module = ModuleSpec(
    name="rulepacks",
    version="0.1.0",
    router=router,
    soft_deps=("findings", "ingestion"),
    setup=setup,
)
