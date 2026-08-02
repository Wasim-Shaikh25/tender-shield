import app.modules.claims.models  # noqa: F401
from app.core.module import AppContext, ModuleSpec
from app.modules.claims.router import router
from app.modules.claims.service import ClaimsService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry

    def factory(session):
        return ClaimsService(
            session,
            change_factory=reg.get("change.service_factory"),
            evidence_factory=reg.get("evidence.service_factory"),
            baseline_factory=reg.get("baseline.service_factory"),
            approval_matrix_factory=reg.get("auth.approval_matrix"),
            ingestion_factory=reg.get("ingestion.service_factory"),
            drafting_factory=reg.get("drafting.service_factory"),
            outcomes_factory=reg.get("outcomes.service_factory"),
            analytics_factory=reg.get("analytics.service_factory"),
            publish=ctx.events.publish,
        )

    reg.provide("claims.service_factory", factory)
    reg.provide(
        "claims.chronology_for_claim",
        lambda session, workspace_id, claim_id: factory(session).chronology_for_claim(
            workspace_id, claim_id
        ),
    )
    reg.provide(
        "claims.checklist_for_claim",
        lambda session, workspace_id, claim_id: factory(session).checklist_for_claim(
            workspace_id, claim_id
        ),
    )
    reg.provide(
        "claims.quantum_for_claim",
        lambda session, workspace_id, claim_id: factory(session).quantum_for_claim(
            workspace_id, claim_id
        ),
    )
    reg.provide(
        "claims.delay_register_for_opportunity",
        lambda session, workspace_id, opportunity_id: factory(session).list_delay_events(
            workspace_id, opportunity_id
        ),
    )
    reg.provide(
        "claims.draft_for_claim",
        lambda session, workspace_id, claim_id, kind: factory(session).generate_draft(
            workspace_id, claim_id, kind, created_by=None
        ),
    )
    reg.provide(
        "claims.negotiation_timeline",
        lambda session, workspace_id, claim_id: factory(session).negotiation_timeline(
            workspace_id, claim_id
        ),
    )
    reg.provide(
        "claims.chain_integrity",
        lambda session, workspace_id, claim_id: factory(session).chain_integrity(
            workspace_id, claim_id
        ),
    )
    reg.provide(
        "claims.conflict_check",
        lambda session, workspace_id, claim_id: factory(session).conflict_check(
            workspace_id, claim_id
        ),
    )
    reg.provide(
        "claims.cycle_metrics",
        lambda session, workspace_id, opportunity_id: factory(session).cycle_metrics(
            workspace_id, opportunity_id
        ),
    )


module = ModuleSpec(
    name="claims",
    version="0.1.0",
    router=router,
    soft_deps=(
        "change",
        "evidence",
        "baseline",
        "auth",
        "drafting",
        "outcomes",
        "analytics",
    ),
    setup=setup,
)
