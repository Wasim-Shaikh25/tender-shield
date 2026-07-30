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

from sqlalchemy import DateTime, Uuid, create_engine, func, text
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


def rls_statements(table: str, user_id_column: str | None = None) -> list[str]:
    """RLS enable + workspace-isolation policy for one table (PostgreSQL only).

    FORCE is required: without it the table owner (the migration role) bypasses
    RLS. WITH CHECK on the same expression prevents cross-tenant writes.
    `nullif(current_setting(..., true), '')::uuid` treats an unset GUC as NULL, which
    makes the predicate `workspace_id = NULL` — i.e. false for every row.

    Membership tables (`workspace_members`, `project_members`) additionally allow a
    row when the row's user_id matches `app.user_id`, so an account-level session
    (no workspace selected) can still read/write the caller's own memberships.
    """
    workspace_guc = "nullif(current_setting('app.workspace_id', true), '')::uuid"
    user_guc = "nullif(current_setting('app.user_id', true), '')::uuid"
    predicate = f"workspace_id = {workspace_guc}"
    if user_id_column:
        predicate = f"({predicate} OR {user_id_column} = {user_guc})"
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        (
            f"CREATE POLICY workspace_isolation ON {table} "
            f"USING ({predicate}) "
            f"WITH CHECK ({predicate})"
        ),
    ]


def bind_workspace_context(
    session: Session,
    workspace_id: uuid.UUID | str,
    user_id: uuid.UUID | str | None = None,
) -> None:
    """SET LOCAL app.workspace_id (and optionally app.user_id) for the current
    transaction — the RLS binding every request must perform before touching
    workspace data (Doc §5, §3.2).

    A no-op on SQLite (tests): SQLite has no RLS, so cross-workspace isolation is
    exercised by dedicated integration tests against PostgreSQL.
    """
    if session.get_bind().dialect.name != "postgresql":
        logger.debug("bind_workspace_context is a no-op on non-PostgreSQL dialects")
        return
    # `SET LOCAL` does not accept bind parameters, so we validate and inline the UUIDs.
    ws = str(uuid.UUID(str(workspace_id)))
    session.execute(text(f"SET LOCAL app.workspace_id = '{ws}'"))
    if user_id is not None:
        uid = str(uuid.UUID(str(user_id)))
        session.execute(text(f"SET LOCAL app.user_id = '{uid}'"))


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
