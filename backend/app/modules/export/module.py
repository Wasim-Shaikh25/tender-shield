from app.core.module import AppContext, ModuleSpec
from app.modules.export.router import router
from app.modules.export.service import ExportService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    loader = reg.get("rulepacks.loader")

    def _pack_version(session, workspace_id):
        if loader is None:
            return "in-works"
        return loader.get_pack(
            "in-works",
            session=session,
            workspace_id=workspace_id,
        ).version_tag

    reg.provide(
        "export.service_factory",
        lambda session, workspace_id=None: ExportService(
            session,
            review_factory=reg.get("review.service_factory"),
            findings_factory=reg.get("findings.store_factory"),
            drafting_factory=reg.get("drafting.service_factory"),
            ingestion_factory=reg.get("ingestion.service_factory"),
            workspace_factory=reg.get("auth.workspace_factory"),
            pack_version=_pack_version,
            document_class_permitted_fn=reg.get("auth.document_class_permitted"),
        ),
    )


module = ModuleSpec(
    name="export",
    version="0.1.0",
    router=router,
    soft_deps=("review", "findings", "drafting", "ingestion", "rulepacks", "auth"),
    setup=setup,
)
