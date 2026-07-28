"""RLS isolation against a REAL PostgreSQL server (R-001 §B, TS-086).

bind_workspace_context is a documented no-op on SQLite, so the isolation
guarantee these tests check was never exercised anywhere before this file —
every other test in this suite runs on SQLite. Requires a reachable Postgres;
set TS_TEST_DATABASE_URL or rely on the default below. Skipped unless run
with `-m postgres` (see pyproject.toml addopts).

Two real bugs were found writing these tests, both fixed in app.core.db before
this file went green (worth keeping in mind when reading it):

1. `SET LOCAL app.workspace_id = :param` is a PostgreSQL syntax error — SET
   only accepts a literal, never a bind parameter. Fixed with set_config(),
   which is a normal function call and does accept parameters.
2. A plain single-workspace predicate on workspaces/workspace_members breaks
   list_workspaces (a user's own memberships legitimately span workspaces).
   Fixed with a compound predicate: visible if it's the bound workspace, OR
   it's the caller's own row (see workspaces_rls_statements /
   workspace_members_rls_statements in app.core.db).
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import sessionmaker

import app.modules.auth.models as auth_models  # noqa: F401 — register on Base.metadata
import app.modules.ingestion.models as ingestion_models  # noqa: F401
from app.core.db import (
    EXTRA_RLS_TABLES,
    WORKSPACE_SCOPED_TABLES,
    Base,
    bind_user_context,
    bind_workspace_context,
    install_rls_rebinding,
    rls_statements,
    workspace_members_rls_statements,
    workspaces_rls_statements,
)
from app.modules.auth.models import User, Workspace, WorkspaceMember
from app.modules.ingestion.models import Opportunity

pytestmark = pytest.mark.postgres

PG_URL = os.environ.get(
    "TS_TEST_DATABASE_URL",
    "postgresql+psycopg://tendershield:tendershield@localhost:5432/tendershield_test",
)


def _drop_cross_table_policy_dependency(engine) -> None:
    """workspaces' RLS policy subquery references workspace_members, so
    Base.metadata.drop_all's FK-only ordering can try to drop workspace_members
    while that policy still depends on it (DependentObjectsStillExist). Strip
    the policy first to break the dependency before dropping tables.

    Must run before EVERY drop_all, not just teardown: this fixture also runs
    against a database a prior CI step already migrated with `alembic upgrade
    head`, which creates the same policy — so the very first drop_all in
    fixture setup can hit this too, not only the one at teardown.
    """
    with engine.begin() as conn:
        exists = conn.execute(text("SELECT to_regclass('public.workspaces')")).scalar()
        if exists:
            conn.execute(text("DROP POLICY IF EXISTS workspace_isolation ON workspaces"))


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(PG_URL, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"PostgreSQL not reachable at {PG_URL}: {exc}")

    _drop_cross_table_policy_dependency(engine)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for table in sorted(WORKSPACE_SCOPED_TABLES):
            for stmt in rls_statements(table):
                conn.execute(text(stmt))
        for table, id_column in EXTRA_RLS_TABLES.items():
            for stmt in rls_statements(table, id_column=id_column):
                conn.execute(text(stmt))
        for stmt in workspaces_rls_statements():
            conn.execute(text(stmt))
        for stmt in workspace_members_rls_statements():
            conn.execute(text(stmt))
    yield engine
    _drop_cross_table_policy_dependency(engine)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session_factory(pg_engine):
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False, future=True)
    install_rls_rebinding(factory)
    return factory


def _make_user(pg_engine, user_id=None) -> uuid.UUID:
    """users carries no RLS policy (it isn't workspace-scoped), so a plain
    engine connection is fine here — this mirrors production exactly."""
    user_id = user_id or uuid.uuid4()
    with pg_engine.begin() as conn:
        conn.execute(
            insert(User),
            [{
                "id": user_id, "email": f"{user_id}@example.com",
                "email_verified": False, "is_superadmin": False, "mfa_method": "totp",
            }],
        )
    return user_id


def _make_workspace(session_factory, *, owner_id, name) -> uuid.UUID:
    """Mirrors AuthService._create_workspace_and_owner: bind to the new
    workspace's own id before inserting it, exactly as production must
    (R-001 §B.7 note in app.core.db) — there is no workspace to bind to until
    this call creates one."""
    ws_id = uuid.uuid4()
    s = session_factory()
    try:
        bind_workspace_context(s, ws_id)
        bind_user_context(s, owner_id)
        s.add(Workspace(id=ws_id, owner_id=owner_id, name=name, country="IN"))
        s.flush()
        s.add(WorkspaceMember(workspace_id=ws_id, user_id=owner_id, role="owner"))
        s.commit()
    finally:
        s.close()
    return ws_id


def _add_member(session_factory, *, workspace_id, user_id, role="viewer") -> None:
    """Mirrors add_workspace_member: the caller's session is already bound to
    the target workspace (via require_workspace_member, R-001 §A) before this
    write happens."""
    s = session_factory()
    try:
        bind_workspace_context(s, workspace_id)
        s.add(WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role))
        s.commit()
    finally:
        s.close()


@pytest.fixture
def two_workspaces(pg_engine, session_factory):
    owner_a, owner_b = _make_user(pg_engine), _make_user(pg_engine)
    ws_a = _make_workspace(session_factory, owner_id=owner_a, name="Workspace A")
    ws_b = _make_workspace(session_factory, owner_id=owner_b, name="Workspace B")

    opp_a, opp_b = uuid.uuid4(), uuid.uuid4()
    s = session_factory()
    try:
        bind_workspace_context(s, ws_a)
        s.add(Opportunity(id=opp_a, workspace_id=ws_a, title="A's tender"))
        s.commit()
    finally:
        s.close()
    s = session_factory()
    try:
        bind_workspace_context(s, ws_b)
        s.add(Opportunity(id=opp_b, workspace_id=ws_b, title="B's tender"))
        s.commit()
    finally:
        s.close()

    return {
        "ws_a": ws_a, "ws_b": ws_b, "owner_a": owner_a, "owner_b": owner_b,
        "opp_a": opp_a, "opp_b": opp_b,
    }


# ---- ordinary single-workspace tables (opportunities) ---------------------


def test_bound_session_sees_only_its_own_workspace(session_factory, two_workspaces):
    s = session_factory()
    try:
        bind_workspace_context(s, two_workspaces["ws_a"])
        rows = s.scalars(select(Opportunity)).all()
        assert [r.title for r in rows] == ["A's tender"]
    finally:
        s.close()


def test_unbound_session_sees_no_rows(session_factory, two_workspaces):
    """Fail closed: a session that never bound a workspace must see nothing,
    never another tenant's rows (R-001 §B — NULLIF(..., true) yields NULL)."""
    s = session_factory()
    try:
        rows = s.scalars(select(Opportunity)).all()
        assert rows == []
    finally:
        s.close()


def test_with_check_blocks_cross_workspace_insert(session_factory, two_workspaces):
    """USING alone only filters reads. Without WITH CHECK a session bound to A
    could still INSERT a row carrying B's workspace_id (R-001 §B.1)."""
    s = session_factory()
    try:
        bind_workspace_context(s, two_workspaces["ws_a"])
        s.add(
            Opportunity(
                id=uuid.uuid4(),
                workspace_id=two_workspaces["ws_b"],  # wrong workspace on purpose
                title="smuggled row",
            )
        )
        with pytest.raises(ProgrammingError):
            s.flush()
    finally:
        s.rollback()
        s.close()


def test_rls_binding_survives_a_mid_request_commit(session_factory, two_workspaces):
    """The binding is transaction-scoped; services in this codebase commit
    more than once per request. Without the after_commit rebinding listener,
    the second query below would see zero rows once FORCE is enabled — a bug
    that reads as 'my data disappeared' (R-001 §B.5)."""
    s = session_factory()
    try:
        bind_workspace_context(s, two_workspaces["ws_a"])
        assert len(s.scalars(select(Opportunity)).all()) == 1

        s.add(
            Opportunity(id=uuid.uuid4(), workspace_id=two_workspaces["ws_a"], title="second doc")
        )
        s.commit()  # mid-request commit, exactly like AuthService/BillingService do

        rows = s.scalars(select(Opportunity)).all()
        assert {r.title for r in rows} == {"A's tender", "second doc"}
    finally:
        s.close()


# ---- workspaces / workspace_members: compound policy -----------------------


def test_workspace_row_visible_when_bound(session_factory, two_workspaces):
    s = session_factory()
    try:
        bind_workspace_context(s, two_workspaces["ws_a"])
        bind_user_context(s, two_workspaces["owner_a"])
        rows = s.scalars(select(Workspace)).all()
        assert [r.name for r in rows] == ["Workspace A"]
    finally:
        s.close()


def test_member_list_hidden_for_a_workspace_the_caller_is_not_in(
    session_factory, two_workspaces
):
    """This is the exact leak TS-084/TS-086 close: reading another workspace's
    member list. Bound to A, as someone who is only a member of A, B's members
    stay invisible even by direct query."""
    s = session_factory()
    try:
        bind_workspace_context(s, two_workspaces["ws_a"])
        bind_user_context(s, two_workspaces["owner_a"])
        rows = s.scalars(select(WorkspaceMember)).all()
        assert {r.workspace_id for r in rows} == {two_workspaces["ws_a"]}
    finally:
        s.close()


def test_own_membership_visible_across_workspaces_regardless_of_binding(
    pg_engine, session_factory, two_workspaces
):
    """The reason for the compound predicate: list_workspaces must show a user
    every workspace they belong to. A user who is a member of BOTH A and B
    must see both membership rows even while the session is bound to just A
    (R-001 §B.7) — a plain single-workspace predicate would hide B's row and
    silently break the "my workspaces" list."""
    consultant = _make_user(pg_engine)
    _add_member(session_factory, workspace_id=two_workspaces["ws_a"], user_id=consultant)
    _add_member(session_factory, workspace_id=two_workspaces["ws_b"], user_id=consultant)

    s = session_factory()
    try:
        bind_workspace_context(s, two_workspaces["ws_a"])
        bind_user_context(s, consultant)
        rows = s.scalars(select(WorkspaceMember).where(WorkspaceMember.user_id == consultant)).all()
        assert {r.workspace_id for r in rows} == {two_workspaces["ws_a"], two_workspaces["ws_b"]}
    finally:
        s.close()


def test_workspaces_table_visible_via_membership_not_just_binding(
    pg_engine, session_factory, two_workspaces
):
    """Same reasoning as above, for the workspaces table itself: list_workspaces
    joins Workspace x WorkspaceMember, so both need the compound predicate or
    the join silently drops every workspace except the bound one."""
    consultant = _make_user(pg_engine)
    _add_member(session_factory, workspace_id=two_workspaces["ws_a"], user_id=consultant)
    _add_member(session_factory, workspace_id=two_workspaces["ws_b"], user_id=consultant)

    s = session_factory()
    try:
        bind_workspace_context(s, two_workspaces["ws_a"])
        bind_user_context(s, consultant)
        rows = s.scalars(select(Workspace)).all()
        assert {r.name for r in rows} == {"Workspace A", "Workspace B"}
    finally:
        s.close()


def test_cannot_see_another_users_membership_in_a_foreign_workspace(
    session_factory, two_workspaces
):
    """The compound predicate's OR must not become a bypass: a caller who is
    NOT a member of B, and whose session is bound to A, must not see B's
    members just because the policy has an OR in it."""
    s = session_factory()
    try:
        bind_workspace_context(s, two_workspaces["ws_a"])
        bind_user_context(s, two_workspaces["owner_a"])  # owner of A only
        rows = s.scalars(
            select(WorkspaceMember).where(WorkspaceMember.workspace_id == two_workspaces["ws_b"])
        ).all()
        assert rows == []
    finally:
        s.close()
