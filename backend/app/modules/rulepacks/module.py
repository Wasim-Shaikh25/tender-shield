from app.core.module import AppContext, ModuleSpec
from app.core.storage import get_storage
from app.modules.rulepacks.admin_service import RulePackAdminService
from app.modules.rulepacks.correction_service import CorrectionService
from app.modules.rulepacks.loader import RulePackLoader
from app.modules.rulepacks.rag_service import RagSuggestionService
from app.modules.rulepacks.router import router


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    loader = RulePackLoader(ctx.settings.rulepacks_dir or None)
    session_factory = reg.get("db.sessionmaker")
    if session_factory:
        loader.set_session_factory(session_factory)
    reg.provide("rulepacks.loader", loader)

    storage = get_storage(ctx.settings)

    def admin_factory(session):
        return RulePackAdminService(
            session,
            settings=ctx.settings,
            loader=loader,
            storage=storage,
        )

    reg.provide("rulepacks.admin_factory", admin_factory)

    def correction_factory(session):
        return CorrectionService(
            session,
            findings_factory=reg.get("findings.store_factory"),
            ingestion_factory=reg.get("ingestion.service_factory"),
            publish=ctx.events.publish,
        )

    reg.provide("rulepacks.correction_factory", correction_factory)

    def rag_factory(session):
        return RagSuggestionService(
            session,
            settings=ctx.settings,
            storage=storage,
            ingestion_factory=reg.get("ingestion.service_factory"),
            publish=ctx.events.publish,
        )

    reg.provide("rulepacks.rag_factory", rag_factory)


module = ModuleSpec(
    name="rulepacks",
    version="0.1.0",
    router=router,
    soft_deps=("findings", "ingestion"),
    setup=setup,
)
