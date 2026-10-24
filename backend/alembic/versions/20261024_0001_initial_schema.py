"""initial schema: PostgreSQL

Revision ID: 0001
Revises: 
Create Date: 2026-10-24 18:26:31.039971
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM('admin', 'user', name='user_role').create(bind, checkfirst=True)
    postgresql.ENUM('RUB', 'USD', 'EUR', name='currency_code').create(bind, checkfirst=True)
    postgresql.ENUM('daily', 'weekly', 'monthly', 'quarterly', 'yearly', name='payment_period').create(bind, checkfirst=True)
    postgresql.ENUM('paid', 'unpaid', name='payment_status').create(bind, checkfirst=True)
    postgresql.ENUM('reminder', 'overdue', name='notification_kind').create(bind, checkfirst=True)

    op.create_table('revoked_tokens',
    sa.Column('jti', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('jti', name=op.f('pk_revoked_tokens'))
    )
    op.create_index(op.f('ix_revoked_tokens_expires_at'), 'revoked_tokens', ['expires_at'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('login', sa.String(length=50), nullable=False),
    sa.Column('password_hash', sa.String(length=100), nullable=False),
    sa.Column('role', postgresql.ENUM('admin', 'user', name='user_role', create_type=False), server_default='user', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('char_length(login) >= 3', name=op.f('ck_users_login_min_length')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    op.create_index('uq_users_login_lower', 'users', [sa.literal_column('lower(login)')], unique=True)
    op.create_index('uq_users_single_active_admin', 'users', ['role'], unique=True, postgresql_where=sa.text("role = 'admin' AND is_active"))
    op.create_table('audit_logs',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('actor', sa.String(length=100), nullable=False),
    sa.Column('action', sa.String(length=50), nullable=False),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_audit_logs_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
    )
    op.create_index('ix_audit_logs_action_created_at', 'audit_logs', ['action', 'created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_table('recurring_payments',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('currency', postgresql.ENUM('RUB', 'USD', 'EUR', name='currency_code', create_type=False), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('period', postgresql.ENUM('daily', 'weekly', 'monthly', 'quarterly', 'yearly', name='payment_period', create_type=False), server_default='monthly', nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.CheckConstraint('amount > 0', name=op.f('ck_recurring_payments_amount_positive')),
    sa.CheckConstraint('char_length(btrim(name)) > 0', name=op.f('ck_recurring_payments_name_not_blank')),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_recurring_payments_created_by_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_recurring_payments'))
    )
    op.create_index(op.f('ix_recurring_payments_created_by_id'), 'recurring_payments', ['created_by_id'], unique=False)
    op.create_table('payment_occurrences',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('recurring_payment_id', sa.Integer(), nullable=False),
    sa.Column('period_index', sa.Integer(), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('currency', postgresql.ENUM('RUB', 'USD', 'EUR', name='currency_code', create_type=False), nullable=False),
    sa.Column('status', postgresql.ENUM('paid', 'unpaid', name='payment_status', create_type=False), server_default='unpaid', nullable=False),
    sa.Column('actual_payment_date', sa.Date(), nullable=True),
    sa.Column('receipt_url', sa.String(length=1000), nullable=True),
    sa.Column('paid_by_id', sa.Integer(), nullable=True),
    sa.Column('paid_by', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(status = 'paid') = (actual_payment_date IS NOT NULL)", name=op.f('ck_payment_occurrences_paid_iff_has_date')),
    sa.CheckConstraint("status = 'paid' OR (paid_by IS NULL AND paid_by_id IS NULL)", name=op.f('ck_payment_occurrences_paid_by_only_if_paid')),
    sa.CheckConstraint('amount > 0', name=op.f('ck_payment_occurrences_amount_positive')),
    sa.CheckConstraint('period_index >= 0', name=op.f('ck_payment_occurrences_period_index_non_negative')),
    sa.ForeignKeyConstraint(['paid_by_id'], ['users.id'], name=op.f('fk_payment_occurrences_paid_by_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['recurring_payment_id'], ['recurring_payments.id'], name=op.f('fk_payment_occurrences_recurring_payment_id_recurring_payments'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payment_occurrences')),
    sa.UniqueConstraint('recurring_payment_id', 'due_date', name=op.f('uq_payment_occurrences_recurring_payment_id_due_date')),
    sa.UniqueConstraint('recurring_payment_id', 'period_index', name=op.f('uq_payment_occurrences_recurring_payment_id_period_index'))
    )
    op.create_index('ix_payment_occurrences_due_date', 'payment_occurrences', ['due_date'], unique=False)
    op.create_index(op.f('ix_payment_occurrences_paid_by_id'), 'payment_occurrences', ['paid_by_id'], unique=False)
    op.create_index('ix_payment_occurrences_unpaid_due', 'payment_occurrences', ['due_date'], unique=False, postgresql_where=sa.text("status = 'unpaid'"))
    op.create_table('payment_notifications',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('occurrence_id', sa.BigInteger(), nullable=False),
    sa.Column('kind', postgresql.ENUM('reminder', 'overdue', name='notification_kind', create_type=False), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('telegram_message_id', sa.BigInteger(), nullable=True),
    sa.ForeignKeyConstraint(['occurrence_id'], ['payment_occurrences.id'], name=op.f('fk_payment_notifications_occurrence_id_payment_occurrences'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payment_notifications')),
    sa.UniqueConstraint('occurrence_id', 'kind', name=op.f('uq_payment_notifications_occurrence_id_kind'))
    )


def downgrade() -> None:
    op.drop_table('payment_notifications')
    op.drop_index('ix_payment_occurrences_unpaid_due', table_name='payment_occurrences', postgresql_where=sa.text("status = 'unpaid'"))
    op.drop_index(op.f('ix_payment_occurrences_paid_by_id'), table_name='payment_occurrences')
    op.drop_index('ix_payment_occurrences_due_date', table_name='payment_occurrences')
    op.drop_table('payment_occurrences')
    op.drop_index(op.f('ix_recurring_payments_created_by_id'), table_name='recurring_payments')
    op.drop_table('recurring_payments')
    op.drop_index(op.f('ix_audit_logs_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')
    op.drop_index('ix_audit_logs_action_created_at', table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_index('uq_users_single_active_admin', table_name='users', postgresql_where=sa.text("role = 'admin' AND is_active"))
    op.drop_index('uq_users_login_lower', table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_revoked_tokens_expires_at'), table_name='revoked_tokens')
    op.drop_table('revoked_tokens')

    postgresql.ENUM(name='notification_kind').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='payment_status').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='payment_period').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='currency_code').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='user_role').drop(op.get_bind(), checkfirst=True)
