"""move billing usage payment invoice webhook to user account

Revision ID: c7dac720f0e6
Revises: d109c102dd39
Create Date: 2026-07-30 16:04:02.086050
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c7dac720f0e6'
down_revision: str | None = 'd109c102dd39'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_BigId = sa.BigInteger().with_variant(sa.Integer(), 'sqlite')
_Dt = sa.DateTime(timezone=True)
_Now = sa.text('(CURRENT_TIMESTAMP)')


def _uuid_col():
    """Return a uuid-compatible column type for both Postgres and SQLite."""
    return sa.Uuid()


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ------------------------------------------------------------------
    # 1) Move workspace billing profile fields to the user account.
    # ------------------------------------------------------------------
    op.add_column('users', sa.Column('billing_provider', sa.String(), nullable=True))
    op.add_column('users', sa.Column('billing_settings', sa.JSON(), nullable=True))

    if dialect == 'postgresql':
        op.execute("""
            UPDATE users
            SET billing_provider = (
                SELECT w.billing_provider FROM workspaces w WHERE w.owner_id = users.id LIMIT 1
            ),
                billing_settings = (
                SELECT w.billing_settings FROM workspaces w WHERE w.owner_id = users.id LIMIT 1
            )
        """)
    else:
        # SQLite stores JSON as TEXT and the JSON column may be read as a string.
        op.execute("""
            UPDATE users
            SET billing_provider = (
                SELECT w.billing_provider FROM workspaces w WHERE w.owner_id = users.id LIMIT 1
            ),
                billing_settings = (
                SELECT w.billing_settings FROM workspaces w WHERE w.owner_id = users.id LIMIT 1
            )
        """)

    op.drop_column('workspaces', 'billing_provider')
    op.drop_column('workspaces', 'billing_settings')

    # ------------------------------------------------------------------
    # 2) usage_events: workspace_id becomes nullable for attribution only;
    #    user_id is the account owner and is non-null.
    # ------------------------------------------------------------------
    op.create_table(
        'usage_events_new',
        sa.Column('id', _BigId, autoincrement=True, nullable=False),
        sa.Column('user_id', _uuid_col(), nullable=True),
        sa.Column('workspace_id', _uuid_col(), nullable=True),
        sa.Column('event', sa.String(), nullable=False),
        sa.Column('qty', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('ref_id', _uuid_col(), nullable=True),
        sa.Column('created_at', _Dt, server_default=_Now, nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_usage_events_new_user_id'), 'usage_events_new', ['user_id'], unique=False)
    op.create_index(op.f('ix_usage_events_new_workspace_id'), 'usage_events_new', ['workspace_id'], unique=False)

    if dialect == 'postgresql':
        op.execute("""
            INSERT INTO usage_events_new (id, user_id, workspace_id, event, qty, ref_id, created_at)
            SELECT ue.id, COALESCE(w.owner_id, '00000000000000000000000000000000'::uuid),
                   ue.workspace_id, ue.event, ue.qty, ue.ref_id, ue.created_at
            FROM usage_events ue
            LEFT JOIN workspaces w ON w.id = ue.workspace_id
        """)
    else:
        op.execute("""
            INSERT INTO usage_events_new (id, user_id, workspace_id, event, qty, ref_id, created_at)
            SELECT ue.id, COALESCE(w.owner_id, '00000000000000000000000000000000'),
                   ue.workspace_id, ue.event, ue.qty, ue.ref_id, ue.created_at
            FROM usage_events ue
            LEFT JOIN workspaces w ON w.id = ue.workspace_id
        """)

    op.drop_table('usage_events')
    op.rename_table('usage_events_new', 'usage_events')
    with op.batch_alter_table('usage_events') as batch_op:
        batch_op.alter_column('user_id', nullable=False)

    # ------------------------------------------------------------------
    # 3) payment_log: user_id is the account owner, workspace_id optional.
    # ------------------------------------------------------------------
    op.create_table(
        'payment_log_new',
        sa.Column('id', _BigId, autoincrement=True, nullable=False),
        sa.Column('user_id', _uuid_col(), nullable=True),
        sa.Column('workspace_id', _uuid_col(), nullable=True),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('provider_event_id', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('amount_minor', sa.BigInteger(), nullable=True),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('raw', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('at', _Dt, server_default=_Now, nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payment_log_new_user_id'), 'payment_log_new', ['user_id'], unique=False)
    op.create_index(op.f('ix_payment_log_new_workspace_id'), 'payment_log_new', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_payment_log_new_provider_event_id'), 'payment_log_new', ['provider_event_id'], unique=False)

    if dialect == 'postgresql':
        op.execute("""
            INSERT INTO payment_log_new (id, user_id, workspace_id, provider, provider_event_id,
                                         event_type, amount_minor, currency, status, raw, at)
            SELECT pl.id, COALESCE(w.owner_id, '00000000000000000000000000000000'::uuid),
                   pl.workspace_id, pl.provider, pl.provider_event_id, pl.event_type,
                   pl.amount_minor, pl.currency, pl.status, pl.raw, pl.at
            FROM payment_log pl
            LEFT JOIN workspaces w ON w.id = pl.workspace_id
        """)
    else:
        op.execute("""
            INSERT INTO payment_log_new (id, user_id, workspace_id, provider, provider_event_id,
                                         event_type, amount_minor, currency, status, raw, at)
            SELECT pl.id, COALESCE(w.owner_id, '00000000000000000000000000000000'),
                   pl.workspace_id, pl.provider, pl.provider_event_id, pl.event_type,
                   pl.amount_minor, pl.currency, pl.status, pl.raw, pl.at
            FROM payment_log pl
            LEFT JOIN workspaces w ON w.id = pl.workspace_id
        """)

    op.drop_table('payment_log')
    op.rename_table('payment_log_new', 'payment_log')

    # ------------------------------------------------------------------
    # 4) invoices: user_id is the account owner, workspace_id optional.
    # ------------------------------------------------------------------
    op.create_table(
        'invoices_new',
        sa.Column('id', _BigId, autoincrement=True, nullable=False),
        sa.Column('user_id', _uuid_col(), nullable=True),
        sa.Column('workspace_id', _uuid_col(), nullable=True),
        sa.Column('invoice_number', sa.String(), nullable=False, unique=True),
        sa.Column('amount_minor', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False, server_default='INR'),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('provider_invoice_id', sa.String(), nullable=True),
        sa.Column('raw', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('paid_at', _Dt, nullable=True),
        sa.Column('created_at', _Dt, server_default=_Now, nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invoices_new_user_id'), 'invoices_new', ['user_id'], unique=False)
    op.create_index(op.f('ix_invoices_new_workspace_id'), 'invoices_new', ['workspace_id'], unique=False)

    if dialect == 'postgresql':
        op.execute("""
            INSERT INTO invoices_new (id, user_id, workspace_id, invoice_number, amount_minor,
                                      currency, status, provider, provider_invoice_id, raw, paid_at, created_at)
            SELECT inv.id, COALESCE(w.owner_id, '00000000000000000000000000000000'::uuid),
                   inv.workspace_id, inv.invoice_number, inv.amount_minor, inv.currency,
                   inv.status, inv.provider, inv.provider_invoice_id, inv.raw, inv.paid_at, inv.created_at
            FROM invoices inv
            LEFT JOIN workspaces w ON w.id = inv.workspace_id
        """)
    else:
        op.execute("""
            INSERT INTO invoices_new (id, user_id, workspace_id, invoice_number, amount_minor,
                                      currency, status, provider, provider_invoice_id, raw, paid_at, created_at)
            SELECT inv.id, COALESCE(w.owner_id, '00000000000000000000000000000000'),
                   inv.workspace_id, inv.invoice_number, inv.amount_minor, inv.currency,
                   inv.status, inv.provider, inv.provider_invoice_id, inv.raw, inv.paid_at, inv.created_at
            FROM invoices inv
            LEFT JOIN workspaces w ON w.id = inv.workspace_id
        """)

    op.drop_table('invoices')
    op.rename_table('invoices_new', 'invoices')
    with op.batch_alter_table('invoices') as batch_op:
        batch_op.alter_column('user_id', nullable=False)

    # ------------------------------------------------------------------
    # 5) webhook_events: global idempotency ledger, no workspace_id.
    # ------------------------------------------------------------------
    op.create_table(
        'webhook_events_new',
        sa.Column('id', _BigId, autoincrement=True, nullable=False),
        sa.Column('user_id', _uuid_col(), nullable=True),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('provider_event_id', sa.String(), nullable=False),
        sa.Column('processed_at', _Dt, server_default=_Now, nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_event_id', name='uq_webhook_provider_event_id')
    )
    op.create_index(op.f('ix_webhook_events_new_user_id'), 'webhook_events_new', ['user_id'], unique=False)

    if dialect == 'postgresql':
        op.execute("""
            INSERT INTO webhook_events_new (id, user_id, provider, provider_event_id, processed_at)
            SELECT wh.id, w.owner_id, wh.provider, wh.provider_event_id, wh.processed_at
            FROM webhook_events wh
            LEFT JOIN workspaces w ON w.id = wh.workspace_id
        """)
    else:
        op.execute("""
            INSERT INTO webhook_events_new (id, user_id, provider, provider_event_id, processed_at)
            SELECT wh.id, w.owner_id, wh.provider, wh.provider_event_id, wh.processed_at
            FROM webhook_events wh
            LEFT JOIN workspaces w ON w.id = wh.workspace_id
        """)

    op.drop_table('webhook_events')
    op.rename_table('webhook_events_new', 'webhook_events')

    # ------------------------------------------------------------------
    # 6) PostgreSQL: drop RLS policies for the tables that are no longer
    #    workspace-scoped. SQLite does not support RLS.
    # ------------------------------------------------------------------
    if dialect == 'postgresql':
        for table in ('usage_events', 'payment_log', 'invoices', 'webhook_events'):
            op.execute(f"DROP POLICY IF EXISTS workspace_isolation ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Re-enable RLS policies on PostgreSQL.
    if dialect == 'postgresql':
        for table in ('usage_events', 'payment_log', 'invoices', 'webhook_events'):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY workspace_isolation ON {table} "
                f"USING (workspace_id = nullif(current_setting('app.current_workspace_id', true), '')::uuid) "
                f"WITH CHECK (workspace_id = nullif(current_setting('app.current_workspace_id', true), '')::uuid)"
            )

    # Move billing profile fields back to workspaces.
    op.add_column('workspaces', sa.Column('billing_settings', sa.JSON(), nullable=True))
    op.add_column('workspaces', sa.Column('billing_provider', sa.String(), nullable=True))

    if dialect == 'postgresql':
        op.execute("""
            UPDATE workspaces
            SET billing_provider = u.billing_provider,
                billing_settings = u.billing_settings
            FROM users u
            WHERE workspaces.owner_id = u.id
        """)
    else:
        op.execute("""
            UPDATE workspaces
            SET billing_provider = (
                SELECT u.billing_provider FROM users u WHERE u.id = workspaces.owner_id
            ),
                billing_settings = (
                SELECT u.billing_settings FROM users u WHERE u.id = workspaces.owner_id
            )
        """)

    op.drop_column('users', 'billing_settings')
    op.drop_column('users', 'billing_provider')

    # Recreate workspace-scoped tables. Data migration back is best-effort; the
    # new columns are nullable so we can copy without failing.

    # usage_events
    op.create_table(
        'usage_events_old',
        sa.Column('id', _BigId, autoincrement=True, nullable=False),
        sa.Column('workspace_id', _uuid_col(), nullable=False),
        sa.Column('event', sa.String(), nullable=False),
        sa.Column('qty', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('ref_id', _uuid_col(), nullable=True),
        sa.Column('created_at', _Dt, server_default=_Now, nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_usage_events_old_workspace_id'), 'usage_events_old', ['workspace_id'], unique=False)
    op.execute("""
        INSERT INTO usage_events_old (id, workspace_id, event, qty, ref_id, created_at)
        SELECT id, COALESCE(workspace_id, user_id, '00000000000000000000000000000000'),
               event, qty, ref_id, created_at FROM usage_events
    """)
    op.drop_table('usage_events')
    op.rename_table('usage_events_old', 'usage_events')
    # SQLite does not rename indexes with the table; recreate expected names.
    op.execute("DROP INDEX IF EXISTS ix_usage_events_old_workspace_id")
    op.create_index(
        op.f("ix_usage_events_workspace_id"), "usage_events", ["workspace_id"], unique=False
    )

    # payment_log
    op.create_table(
        'payment_log_old',
        sa.Column('id', _BigId, autoincrement=True, nullable=False),
        sa.Column('workspace_id', _uuid_col(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('provider_event_id', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('amount_minor', sa.BigInteger(), nullable=True),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('raw', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('at', _Dt, server_default=_Now, nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payment_log_old_workspace_id'), 'payment_log_old', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_payment_log_old_provider_event_id'), 'payment_log_old', ['provider_event_id'], unique=False)
    op.execute("""
        INSERT INTO payment_log_old (id, workspace_id, provider, provider_event_id,
                                     event_type, amount_minor, currency, status, raw, at)
        SELECT id, COALESCE(workspace_id, user_id, '00000000000000000000000000000000'),
               provider, provider_event_id, event_type,
               amount_minor, currency, status, raw, at FROM payment_log
    """)
    op.drop_table('payment_log')
    op.rename_table('payment_log_old', 'payment_log')
    op.execute("DROP INDEX IF EXISTS ix_payment_log_old_workspace_id")
    op.create_index(
        op.f("ix_payment_log_workspace_id"), "payment_log", ["workspace_id"], unique=False
    )
    op.execute("DROP INDEX IF EXISTS ix_payment_log_old_provider_event_id")
    op.create_index(
        op.f("ix_payment_log_provider_event_id"),
        "payment_log",
        ["provider_event_id"],
        unique=False,
    )

    # invoices
    op.create_table(
        'invoices_old',
        sa.Column('id', _BigId, autoincrement=True, nullable=False),
        sa.Column('workspace_id', _uuid_col(), nullable=False),
        sa.Column('invoice_number', sa.String(), nullable=False, unique=True),
        sa.Column('amount_minor', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False, server_default='INR'),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('provider_invoice_id', sa.String(), nullable=True),
        sa.Column('raw', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('paid_at', _Dt, nullable=True),
        sa.Column('created_at', _Dt, server_default=_Now, nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invoices_old_workspace_id'), 'invoices_old', ['workspace_id'], unique=False)
    op.execute("""
        INSERT INTO invoices_old (id, workspace_id, invoice_number, amount_minor, currency,
                                  status, provider, provider_invoice_id, raw, paid_at, created_at)
        SELECT id, COALESCE(workspace_id, user_id, '00000000000000000000000000000000'),
               invoice_number, amount_minor, currency,
               status, provider, provider_invoice_id, raw, paid_at, created_at FROM invoices
    """)
    op.drop_table('invoices')
    op.rename_table('invoices_old', 'invoices')
    op.execute("DROP INDEX IF EXISTS ix_invoices_old_workspace_id")
    op.create_index(
        op.f("ix_invoices_workspace_id"), "invoices", ["workspace_id"], unique=False
    )

    # webhook_events
    op.create_table(
        'webhook_events_old',
        sa.Column('id', _BigId, autoincrement=True, nullable=False),
        sa.Column('workspace_id', _uuid_col(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('provider_event_id', sa.String(), nullable=False),
        sa.Column('processed_at', _Dt, server_default=_Now, nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_event_id')
    )
    op.create_index(op.f('ix_webhook_events_old_workspace_id'), 'webhook_events_old', ['workspace_id'], unique=False)
    op.execute("""
        INSERT INTO webhook_events_old (id, workspace_id, provider, provider_event_id, processed_at)
        SELECT id, COALESCE(user_id, '00000000000000000000000000000000'),
               provider, provider_event_id, processed_at FROM webhook_events
    """)
    op.drop_table('webhook_events')
    op.rename_table('webhook_events_old', 'webhook_events')
    op.execute("DROP INDEX IF EXISTS ix_webhook_events_old_workspace_id")
    op.create_index(
        op.f("ix_webhook_events_workspace_id"), "webhook_events", ["workspace_id"], unique=False
    )
