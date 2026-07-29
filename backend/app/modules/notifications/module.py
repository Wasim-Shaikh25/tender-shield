from app.core.db import bind_workspace_context
from app.core.module import AppContext, ModuleSpec
from app.modules.notifications.adapters import build_sender
from app.modules.notifications.sender import Message


def setup(ctx: AppContext) -> None:
    # ConsoleSender in dev/test; SES/MSG91 adapters register when credentials are set.
    sender = build_sender(ctx.settings)
    ctx.registry.provide("notifications.sender", sender)

    scheduler = ctx.registry.get("core.scheduler")
    if scheduler is not None:

        def _deadline_alert_tick() -> None:
            """Scan every workspace for deadlines in the next 7 days and alert members."""
            session_maker = ctx.registry.get("db.sessionmaker")
            ingestion_factory = ctx.registry.get("ingestion.service_factory")
            workspace_factory = ctx.registry.get("auth.workspace_factory")
            if not session_maker or not ingestion_factory or not workspace_factory:
                return

            from datetime import UTC, datetime, timedelta

            session = session_maker()
            try:
                admin = workspace_factory(session)
                for workspace in admin.list_all_workspaces():
                    workspace_id = workspace["workspace_id"]
                    bind_workspace_context(session, workspace_id)
                    ingestion = ingestion_factory(session)
                    for opp in ingestion.list_opportunities(workspace_id):
                        for dl in ingestion.list_deadlines(workspace_id, str(opp.id)):
                            due_at = dl.due_at
                            if not due_at or dl.confirmed:
                                continue
                            if due_at.tzinfo is None:
                                due_at = due_at.replace(tzinfo=UTC)
                            if timedelta(0) < (due_at - datetime.now(UTC)) <= timedelta(days=7):
                                for member in admin.list_members(workspace_id):
                                    sender.send(
                                        Message(
                                            channel="email",
                                            to=member["email"],
                                            subject=f"Deadline alert: {opp.title}",
                                            body=(
                                                f"Deadline '{dl.description or dl.kind}' is due at "
                                                f"{due_at.isoformat()} for opportunity "
                                                f"{str(opp.id)}."
                                            ),
                                        )
                                    )
            finally:
                session.close()

        scheduler.add_job(_deadline_alert_tick, "interval", hours=24)


module = ModuleSpec(
    name="notifications",
    version="0.1.0",
    router=None,
    soft_deps=("ingestion",),
    setup=setup,
)
