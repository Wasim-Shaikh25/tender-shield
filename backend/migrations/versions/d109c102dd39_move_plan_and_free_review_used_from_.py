"""move plan and free_review_used from workspace to user

Revision ID: d109c102dd39
Revises: ba2b02b4f9ce
Create Date: 2026-07-30 15:42:32.152397
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd109c102dd39'
down_revision: str | None = 'ba2b02b4f9ce'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 1) Add account-level plan columns with defaults so existing rows are valid.
    op.add_column('users', sa.Column('plan', sa.String(), nullable=False, server_default='free'))
    op.add_column(
        'users', sa.Column('free_review_used', sa.Boolean(), nullable=False, server_default='false')
    )

    # 2) Backfill users.plan and users.free_review_used from the user's first owned workspace.
    #    In the account-centric model each user has one billing plan.
    if dialect == 'postgresql':
        op.execute(
            """
            UPDATE users
            SET plan = COALESCE((
                SELECT w.plan FROM workspaces w WHERE w.owner_id = users.id ORDER BY w.created_at LIMIT 1
            ), 'free'),
                free_review_used = COALESCE((
                SELECT w.free_review_used FROM workspaces w WHERE w.owner_id = users.id ORDER BY w.created_at LIMIT 1
            ), false)
            """
        )
    else:
        # SQLite compatible statement using scalar subqueries.
        op.execute(
            """
            UPDATE users
            SET plan = COALESCE((
                SELECT w.plan FROM workspaces w WHERE w.owner_id = users.id ORDER BY w.created_at LIMIT 1
            ), 'free'),
                free_review_used = COALESCE((
                SELECT w.free_review_used FROM workspaces w WHERE w.owner_id = users.id ORDER BY w.created_at LIMIT 1
            ), 0)
            """
        )

    # 3) Drop workspace-level plan columns.
    op.drop_column('workspaces', 'plan')
    op.drop_column('workspaces', 'free_review_used')

    # 4) Recreate plan_history with user_id instead of workspace_id.
    op.execute('DROP TABLE IF EXISTS plan_history_new')
    op.create_table(
        'plan_history_new',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('old_plan', sa.String(), nullable=False),
        sa.Column('new_plan', sa.String(), nullable=False),
        sa.Column('changed_by', sa.Uuid(), nullable=True),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plan_history_new_user_id'), 'plan_history_new', ['user_id'], unique=False)

    # 5) Migrate existing plan_history rows: workspace_id -> workspace owner user_id.
    if dialect == 'postgresql':
        op.execute(
            """
            INSERT INTO plan_history_new (id, user_id, old_plan, new_plan, changed_by, reason, created_at)
            SELECT ph.id, w.owner_id, ph.old_plan, ph.new_plan, ph.changed_by, ph.reason, ph.created_at
            FROM plan_history ph
            LEFT JOIN workspaces w ON w.id = ph.workspace_id
            """
        )
    else:
        op.execute(
            """
            INSERT INTO plan_history_new (id, user_id, old_plan, new_plan, changed_by, reason, created_at)
            SELECT ph.id, w.owner_id, ph.old_plan, ph.new_plan, ph.changed_by, ph.reason, ph.created_at
            FROM plan_history ph
            LEFT JOIN workspaces w ON w.id = ph.workspace_id
            """
        )

    op.drop_table('plan_history')
    op.rename_table('plan_history_new', 'plan_history')

    # 6) On PostgreSQL remove the workspace RLS policy from plan_history.
    if dialect == 'postgresql':
        op.execute('DROP POLICY IF EXISTS workspace_isolation ON plan_history')
        op.execute('ALTER TABLE plan_history DISABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Recreate workspace-scoped plan_history.
    op.execute('DROP TABLE IF EXISTS plan_history_old')
    op.create_table(
        'plan_history_old',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('workspace_id', sa.Uuid(), nullable=False),
        sa.Column('old_plan', sa.String(), nullable=False),
        sa.Column('new_plan', sa.String(), nullable=False),
        sa.Column('changed_by', sa.Uuid(), nullable=True),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plan_history_old_workspace_id'), 'plan_history_old', ['workspace_id'], unique=False)

    if dialect == 'postgresql':
        op.execute(
            """
            INSERT INTO plan_history_old (id, workspace_id, old_plan, new_plan, changed_by, reason, created_at)
            SELECT id, NULL, old_plan, new_plan, changed_by, reason, created_at
            FROM plan_history
            """
        )
    else:
        op.execute(
            """
            INSERT INTO plan_history_old (id, workspace_id, old_plan, new_plan, changed_by, reason, created_at)
            SELECT id, NULL, old_plan, new_plan, changed_by, reason, created_at
            FROM plan_history
            """
        )

    op.drop_table('plan_history')
    op.rename_table('plan_history_old', 'plan_history')

    # SQLite does not rename indexes when a table is renamed, so recreate the
    # expected index. PostgreSQL already renames it automatically; the DROP/CREATE
    # is idempotent and harmless on both.
    op.execute("DROP INDEX IF EXISTS ix_plan_history_old_workspace_id")
    op.create_index(
        op.f("ix_plan_history_workspace_id"), "plan_history", ["workspace_id"], unique=False
    )

    # Re-add workspace-level plan columns.
    op.add_column('workspaces', sa.Column('plan', sa.String(), server_default='free', nullable=False))
    op.add_column(
        'workspaces', sa.Column('free_review_used', sa.Boolean(), server_default='false', nullable=False)
    )
    op.drop_column('users', 'free_review_used')
    op.drop_column('users', 'plan')
