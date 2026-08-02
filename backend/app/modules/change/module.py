import app.modules.change.models  # noqa: F401
from app.core.module import AppContext, ModuleSpec
from app.modules.change.alert_processor import process_notice_alerts
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
            approval_matrix_factory=reg.get("auth.approval_matrix"),
            drafting_factory=reg.get("drafting.service_factory"),
            evidence_factory=reg.get("evidence.service_factory"),
            project_active_fn=reg.get("billing.is_project_active"),
            inbox_domain=ctx.settings.change_inbox_domain,
            publish=ctx.events.publish,
            poll_enabled=ctx.settings.change_signal_polling_enabled,
            schedule_activities_fn=reg.get("integrations.schedule_activities_for_opportunity"),
        )

    reg.provide("change.service_factory", factory)
    reg.provide(
        "change.event_for_id",
        lambda session, workspace_id, event_id: factory(session).get_event_core(
            workspace_id, event_id
        ),
    )
    reg.provide(
        "change.events_for_opportunity",
        lambda session, workspace_id, opportunity_id: factory(session).list_events(
            workspace_id, opportunity_id
        ),
    )
    reg.provide(
        "change.notice_deadline_for_event",
        lambda session, workspace_id, event_id: factory(session).notice_deadline_for_event(
            workspace_id, event_id
        ),
    )

    def _process_notice_alerts(session):
        sender = reg.get("notifications.sender")
        preference_fn = reg.get("notifications.preference_for_user")
        workspace_factory = reg.get("auth.workspace_factory")

        def send_email(to: str, subject: str, body: str) -> None:
            if sender is None:
                return
            message = type(
                "Msg",
                (),
                {"channel": "email", "to": to, "subject": subject, "body": body},
            )()
            sender.send(message)

        return process_notice_alerts(
            session,
            workspace_factory=workspace_factory,
            send_email=send_email if sender else None,
            preference_fn=preference_fn,
        )

    reg.provide("change.process_notice_alerts", _process_notice_alerts)


module = ModuleSpec(
    name="change",
    version="0.1.0",
    router=router,
    soft_deps=(
        "baseline",
        "ingestion",
        "review",
        "findings",
        "auth",
        "drafting",
        "notifications",
        "evidence",
        "billing",
    ),
    setup=setup,
)
