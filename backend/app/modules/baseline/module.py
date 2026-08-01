from app.core.module import AppContext, ModuleSpec
from app.modules.baseline.router import router
from app.modules.baseline.service import BaselineService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry

    def factory(session):
        return BaselineService(
            session,
            findings_factory=reg.get("findings.store_factory"),
            review_factory=reg.get("review.service_factory"),
            ingestion_factory=reg.get("ingestion.service_factory"),
            segment_clauses_fn=reg.get("ingestion.segment_clauses"),
            loader_provider=lambda: reg.get("rulepacks.loader"),
            standards_factory=reg.get("standards.org_notice_provider"),
            export_factory=reg.get("export.service_factory"),
            approval_matrix_factory=reg.get("auth.approval_matrix"),
            publish=ctx.events.publish,
        )

    reg.provide("baseline.service_factory", factory)
    reg.provide(
        "baseline.watchlist_for_opportunity",
        lambda session, workspace_id, opportunity_id: factory(session).list_watchlist(
            workspace_id, opportunity_id
        ),
    )
    reg.provide(
        "baseline.cost_codes_for_opportunity",
        lambda session, workspace_id, opportunity_id: factory(session).list_cost_codes(
            workspace_id, opportunity_id
        ),
    )


module = ModuleSpec(
    name="baseline",
    version="0.1.0",
    router=router,
    soft_deps=("findings", "review", "ingestion", "rulepacks", "standards", "auth", "export"),
    setup=setup,
)
