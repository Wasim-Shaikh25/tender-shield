"""Database foundation: declarative base, engine/session factory, RLS helpers.

Table ownership lives with the modules (specs/data-model.md); this file owns the
shared machinery only. Workspace-scoped tables mix in WorkspaceScopedMixin so the
RLS migration can enumerate them, and every request binds its workspace via
bind_workspace_context (Doc §3.2, §5 — the RLS binding is non-negotiable).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Uuid, create_engine, event, func, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    declared_attr,
    mapped_column,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from app.core.config import Settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# Tables that must carry a workspace-isolation RLS policy (Doc §3.2 — non-negotiable).
# Populated as WorkspaceScopedMixin subclasses are defined by their owning modules.
WORKSPACE_SCOPED_TABLES: set[str] = set()

# Tables that carry a workspace-scoping column but are NOT WorkspaceScopedMixin
# subclasses — composite primary keys (project_members) or the tenant/directory
# tables themselves (workspaces, workspace_members). WORKSPACE_SCOPED_TABLES is
# populated only by the mixin's __tablename__ hook, so these were silently
# absent from every RLS policy ever generated (gap R-001 §B.3, TS-086) — kept
# explicit here so that can't happen again.
#
# workspaces/workspace_members are handled separately (see
# WORKSPACES_RLS_STATEMENTS / WORKSPACE_MEMBERS_RLS_STATEMENTS below): a plain
# single-workspace predicate breaks list_workspaces, which must show a user
# every workspace they belong to, not just whichever one is bound to the
# current session.
EXTRA_RLS_TABLES: dict[str, str] = {
    "project_members": "workspace_id",
}


class WorkspaceScopedMixin:
    """Adds workspace_id and registers the table for RLS policy generation."""

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805 - SQLAlchemy convention
        name = getattr(cls, "_tablename_", None) or cls.__name__.lower()
        WORKSPACE_SCOPED_TABLES.add(name)
        return name


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def _rls_enable(table: str, predicate: str) -> list[str]:
    """FORCE is required: without it PostgreSQL exempts the table's OWNER from
    RLS, and the application connects as the role that ran the migrations —
    i.e. the owner — in every deployment shipped so far. Without FORCE the
    policy below is silently inert (R-001 §B.1, TS-086).

    WITH CHECK is required so a write cannot place/move a row into another
    workspace; USING alone only filters reads.
    """
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        f"DROP POLICY IF EXISTS workspace_isolation ON {table}",
        f"CREATE POLICY workspace_isolation ON {table} "
        f"USING ({predicate}) WITH CHECK ({predicate})",
    ]


def rls_statements(table: str, *, id_column: str = "workspace_id") -> list[str]:
    """RLS enable + workspace-isolation policy for one table (PostgreSQL only).

    current_setting(..., true) returns NULL instead of raising when unbound, so
    an unbound session sees zero rows (fails closed) rather than erroring.
    """
    predicate = f"{id_column} = NULLIF(current_setting('app.workspace_id', true), '')::uuid"
    return _rls_enable(table, predicate)


def workspace_members_rls_statements() -> list[str]:
    """Compound policy for workspace_members (PostgreSQL only, R-001 §B.7).

    A plain `workspace_id = bound` predicate — same as every other
    workspace-scoped table — breaks `list_workspaces`, which must show a user
    every workspace they belong to, not just whichever one happens to be bound
    to the current session. So a row is visible if EITHER it belongs to the
    currently bound workspace (ordinary isolation — this is what makes
    /workspaces/{id}/members correct once TS-084's guard re-binds to the
    verified target workspace) OR it is the caller's own membership row
    (`user_id = app.user_id`), regardless of which workspace is bound.

    This still blocks the original leak: another user's membership row in a
    workspace the caller hasn't been authorized into matches neither branch.
    """
    predicate = (
        "(workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid "
        "OR user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)"
    )
    return _rls_enable("workspace_members", predicate)


def workspaces_rls_statements() -> list[str]:
    """Compound policy for workspaces (PostgreSQL only, R-001 §B.7) — same
    reasoning as workspace_members_rls_statements: a row is visible if it IS
    the bound workspace, or the caller is a member of it per
    workspace_members (which carries its own, independently-enforced RLS)."""
    predicate = (
        "(id = NULLIF(current_setting('app.workspace_id', true), '')::uuid "
        "OR id IN (SELECT workspace_id FROM workspace_members "
        "WHERE user_id = NULLIF(current_setting('app.user_id', true), '')::uuid))"
    )
    return _rls_enable("workspaces", predicate)


# set_config(), not `SET LOCAL <name> = :param`: PostgreSQL's SET command only
# accepts a literal, not a bind parameter — `SET LOCAL app.workspace_id = $1`
# is a syntax error. set_config() is a normal function call and its third
# argument (is_local=true) gives the exact same transaction-scoped lifetime as
# SET LOCAL. This was a live bug in the original binding code, caught only by
# testing bind_workspace_context against a real PostgreSQL server for the
# first time (R-001 §B — the isolation guarantee had never been exercised
# because it is a documented no-op on SQLite, which is all CI ran before).
_SET_WORKSPACE_SQL = text("SELECT set_config('app.workspace_id', :workspace_id, true)")
_SET_USER_SQL = text("SELECT set_config('app.user_id', :user_id, true)")


def bind_workspace_context(session: Session, workspace_id: uuid.UUID | str) -> None:
    """Bind app.workspace_id for the current transaction — the RLS binding every
    request must perform before touching workspace data (Doc §5, §3.2).

    A no-op on SQLite (tests): SQLite has no RLS, so cross-workspace isolation is
    exercised by dedicated integration tests against PostgreSQL.

    Remembers the workspace on the session (session.info) so it can be
    re-applied after a mid-request commit — the binding is transaction-scoped,
    and several services (billing, auth) commit more than once per request,
    which would otherwise silently unbind RLS partway through a request once
    FORCE is enabled (R-001 §B.5).

    May be called more than once per request (e.g. require_workspace_member
    re-binds to a path workspace that differs from the token's active
    workspace) — each call only changes app.workspace_id, never app.user_id.
    """
    session.info["workspace_id"] = str(workspace_id)
    if session.get_bind().dialect.name != "postgresql":
        logger.debug("bind_workspace_context is a no-op on non-PostgreSQL dialects")
        return
    session.execute(_SET_WORKSPACE_SQL, {"workspace_id": str(workspace_id)})


def bind_user_context(session: Session, user_id: uuid.UUID | str) -> None:
    """Bind app.user_id for the current transaction. Set once per request, at
    authenticate() time — the caller's identity does not change when a request
    later re-binds app.workspace_id to a different (verified) workspace.

    Needed only by the compound RLS policies on workspaces/workspace_members
    (R-001 §B.7): a user's OWN membership rows must stay visible across every
    workspace they belong to, not just whichever one is currently bound,
    or list_workspaces breaks under RLS. Tables using the plain single-column
    policy from rls_statements() never reference app.user_id.
    """
    session.info["user_id"] = str(user_id)
    if session.get_bind().dialect.name != "postgresql":
        return
    session.execute(_SET_USER_SQL, {"user_id": str(user_id)})


def install_rls_rebinding(session_factory: sessionmaker[Session]) -> None:
    """Re-apply the app.workspace_id / app.user_id bindings at the start of
    every new transaction on sessions from this factory (R-001 §B.5). A
    session bound mid-request via bind_workspace_context/bind_user_context
    loses that binding the moment any code in the request path calls
    session.commit() — the binding is transaction-scoped, and with FORCE ROW
    LEVEL SECURITY enabled an unbound session sees zero rows for the rest of
    the request, which reads as "my data disappeared".

    Uses after_begin, not after_commit: per SQLAlchemy's own docs, the Session
    has no active transaction when after_commit fires and cannot emit SQL from
    within it (confirmed the hard way — it raises "session is in committed
    state"). after_begin is the documented hook for populating per-transaction
    session state and fires exactly when a new transaction starts, which is
    precisely the moment after a commit that needs re-binding.
    """

    @event.listens_for(session_factory, "after_begin")
    def _rebind_after_begin(session: Session, transaction, connection) -> None:
        if connection.dialect.name != "postgresql":
            return
        workspace_id = session.info.get("workspace_id")
        if workspace_id is not None:
            connection.execute(_SET_WORKSPACE_SQL, {"workspace_id": workspace_id})
        user_id = session.info.get("user_id")
        if user_id is not None:
            connection.execute(_SET_USER_SQL, {"user_id": user_id})


def make_engine(settings: Settings) -> Engine:
    url = settings.database_url
    if url.startswith("sqlite"):
        # In-memory / single-file SQLite for tests: share one connection so the
        # schema created in a fixture is visible to the app under test.
        return create_engine(
            url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool if ":memory:" in url else None,
        )
    return create_engine(url, future=True, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
