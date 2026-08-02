from app.core.module import AppContext, ModuleSpec
from app.modules.subcontract.router import router
from app.modules.subcontract.service import SubcontractService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry

    def factory(session):
        return SubcontractService(
            session,
            baseline_factory=reg.get("baseline.service_factory"),
            change_factory=reg.get("change.service_factory"),
            publish=ctx.events.publish,
        )

    reg.provide("subcontract.service_factory", factory)
    reg.provide(
        "subcontract.notice_calendar",
        lambda session, workspace_id, subcontract_id: factory(
            session
        ).notice_calendar(workspace_id, subcontract_id),
    )
    reg.provide(
        "subcontract.payment_exposure",
        lambda session, workspace_id, subcontract_id: factory(
            session
        ).payment_exposure(workspace_id, subcontract_id),
    )


module = ModuleSpec(
    name="subcontract",
    version="0.1.0",
    router=router,
    soft_deps=("baseline", "change"),
    setup=setup,
)
