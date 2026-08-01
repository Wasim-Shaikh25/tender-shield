import app.modules.change.models  # noqa: F401
from app.core.module import AppContext, ModuleSpec
from app.modules.change.router import router
from app.modules.change.service import ChangeService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry

    def factory(session):
        return ChangeService(
            session,
            baseline_factory=reg.get("baseline.service_factory"),
            ingestion_factory=reg.get("ingestion.service_factory"),
            review_factory=reg.get("review.service_factory"),
            segment_clauses_fn=reg.get("ingestion.segment_clauses"),
            diff_clauses_fn=reg.get("baseline.diff_clauses"),
            findings_factory=reg.get("findings.store_factory"),
            cost_codes_fn=reg.get("baseline.cost_codes_for_opportunity"),
            publish=ctx.events.publish,
        )

    reg.provide("change.service_factory", factory)
    reg.provide(
        "change.events_for_opportunity",
        lambda session, workspace_id, opportunity_id: factory(session).list_events(
            workspace_id, opportunity_id
        ),
    )


module = ModuleSpec(
    name="change",
    version="0.1.0",
    router=router,
    soft_deps=("baseline", "ingestion", "review", "findings"),
    setup=setup,
)
