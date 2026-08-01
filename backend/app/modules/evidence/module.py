import app.modules.evidence.models  # noqa: F401
from app.core.module import AppContext, ModuleSpec
from app.modules.evidence.router import router
from app.modules.evidence.service import EvidenceService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry

    def factory(session):
        return EvidenceService(
            session,
            change_event_fn=reg.get("change.event_for_id"),
            publish=ctx.events.publish,
        )

    reg.provide("evidence.service_factory", factory)
    reg.provide(
        "evidence.completeness_for_event",
        lambda session, workspace_id, event_id: factory(session).completeness_for_event(
            workspace_id, event_id
        ),
    )


module = ModuleSpec(
    name="evidence",
    version="0.1.0",
    router=router,
    soft_deps=("change",),
    setup=setup,
)
