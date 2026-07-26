from app.core.module import AppContext, ModuleSpec
from app.modules.export.router import router
from app.modules.export.service import ExportService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    reg.provide(
        "export.service_factory",
        lambda session: ExportService(
            session,
            review_factory=reg.get("review.service_factory"),
            findings_factory=reg.get("findings.store_factory"),
            drafting_factory=reg.get("drafting.service_factory"),
            ingestion_factory=reg.get("ingestion.service_factory"),
            pack_version=reg.get("rulepacks.loader").get_pack("in-works").version_tag
            if reg.get("rulepacks.loader")
            else "in-works",
        ),
    )


module = ModuleSpec(
    name="export",
    version="0.1.0",
    router=router,
    soft_deps=("review", "findings", "drafting", "ingestion", "rulepacks", "auth"),
    setup=setup,
)
