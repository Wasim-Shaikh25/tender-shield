"""rls hardening: FORCE + WITH CHECK + tables missed by WorkspaceScopedMixin

The original RLS policy (migration e26e85245237) had three defects (R-001 §B,
TS-086): no FORCE ROW LEVEL SECURITY (PostgreSQL exempts the table owner from
RLS, and the application connects as the owner), no WITH CHECK (USING alone
only filters reads, not writes), and `workspaces` / `workspace_members` /
`project_members` were never covered at all because they are not
WorkspaceScopedMixin subclasses (composite PKs / the tenant row itself) and so
never registered in WORKSPACE_SCOPED_TABLES.

Revision ID: ae76edba3a7a
Revises: ca05e77bd02c
Create Date: 2026-07-28 06:32:14.593514
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from app.core.db import (
    EXTRA_RLS_TABLES,
    WORKSPACE_SCOPED_TABLES,
    rls_statements,
    workspace_members_rls_statements,
    workspaces_rls_statements,
)

revision: str = 'ae76edba3a7a'
down_revision: str | None = 'ca05e77bd02c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# workspaces/workspace_members use a compound predicate (bound workspace OR
# caller's own row) — see workspaces_rls_statements/workspace_members_rls_statements
# in app.core.db for why the plain single-workspace predicate breaks
# list_workspaces (R-001 §B.7).
_ALL_TABLES = sorted(WORKSPACE_SCOPED_TABLES) + list(EXTRA_RLS_TABLES) + [
    "workspaces",
    "workspace_members",
]


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in sorted(WORKSPACE_SCOPED_TABLES):
        for stmt in rls_statements(table):
            op.execute(stmt)
    for table, id_column in EXTRA_RLS_TABLES.items():
        for stmt in rls_statements(table, id_column=id_column):
            op.execute(stmt)
    for stmt in workspaces_rls_statements():
        op.execute(stmt)
    for stmt in workspace_members_rls_statements():
        op.execute(stmt)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in _ALL_TABLES:
        op.execute(f"DROP POLICY IF EXISTS workspace_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
