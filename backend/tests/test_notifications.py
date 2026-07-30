"""Deadline-alert deduplication and notification preferences."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.modules.auth.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.notifications.models  # noqa: F401
from app.core.db import Base, bind_workspace_context
from app.modules.auth.models import User, Workspace, WorkspaceMember
from app.modules.ingestion.models import Deadline, Opportunity
from app.modules.notifications.module import _alert_day, _already_sent, _preference, _record_sent


def test_alert_day_buckets():
    now = datetime.now(UTC)
    # Add a one-hour buffer so the wall-clock tick inside _alert_day does not flip the bucket.
    assert _alert_day(now + timedelta(days=7, hours=1)) == 7
    assert _alert_day(now + timedelta(days=6, hours=1)) == 7
    assert _alert_day(now + timedelta(days=3, hours=1)) == 3
    assert _alert_day(now + timedelta(days=1, hours=1)) == 1
    assert _alert_day(now + timedelta(hours=1)) == 0
    assert _alert_day(now - timedelta(hours=1)) is None
    assert _alert_day(now + timedelta(days=14, hours=1)) is None


def test_deadline_alert_dedup_and_preferences():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        user = User(
            email="alerts@x.com",
            phone="+919999999999",
            password_hash="*",
            org_name="Alerts Co",
            city="Mumbai",
        )
        session.add(user)
        session.flush()

        ws = Workspace(owner_id=user.id, name="Alerts Co")
        session.add(ws)
        session.flush()
        session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))

        opp = Opportunity(workspace_id=ws.id, title="Bridge")
        session.add(opp)
        session.flush()

        dl = Deadline(
            workspace_id=ws.id,
            opportunity_id=opp.id,
            kind="submission",
            due_at=datetime.now(UTC) + timedelta(days=3),
        )
        session.add(dl)
        session.commit()

        bind_workspace_context(session, ws.id)

        # Default preference allows email alerts.
        pref = _preference(session, str(user.id))
        assert pref.email_deadlines is True

        # First lookup says not sent; after recording, it is.
        user_id = str(user.id)
        ws_id = str(ws.id)
        dl_id = str(dl.id)
        opp_id = str(opp.id)
        assert not _already_sent(session, ws_id, user_id, dl_id, 3)
        _record_sent(session, ws_id, user_id, opp_id, dl_id, 3)
        assert _already_sent(session, ws_id, user_id, dl_id, 3)

        # A user can opt out of deadline emails.
        pref.email_deadlines = False
        session.commit()
        assert not _preference(session, user_id).email_deadlines
    finally:
        session.close()


def test_recorded_alert_respects_workspace_isolation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        user = User(
            email="iso@x.com",
            phone="+919999999998",
            password_hash="*",
            org_name="A",
            city="Pune",
        )
        session.add(user)
        session.flush()

        ws1 = Workspace(owner_id=user.id, name="A")
        ws2 = Workspace(owner_id=user.id, name="B")
        session.add_all([ws1, ws2])
        session.flush()

        opp1 = Opportunity(workspace_id=ws1.id, title="O1")
        session.add(opp1)
        session.flush()
        dl1 = Deadline(
            workspace_id=ws1.id,
            opportunity_id=opp1.id,
            kind="submission",
            due_at=datetime.now(UTC),
        )
        session.add(dl1)
        session.commit()

        uid = str(user.id)
        dl_id = str(dl1.id)
        _record_sent(session, str(ws1.id), uid, str(opp1.id), dl_id, 0)

        # Same (user, deadline, bucket) in a different workspace must not be considered sent.
        assert not _already_sent(session, str(ws2.id), uid, dl_id, 0)
    finally:
        session.close()
