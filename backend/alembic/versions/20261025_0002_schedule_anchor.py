"""schedule anchor: editing a payment's schedule without touching history

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-25 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'recurring_payments',
        sa.Column('schedule_anchor_index', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )
    op.create_check_constraint(
        op.f('ck_recurring_payments_schedule_anchor_index_non_negative'),
        'recurring_payments',
        'schedule_anchor_index >= 0',
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('ck_recurring_payments_schedule_anchor_index_non_negative'), 'recurring_payments', type_='check'
    )
    op.drop_column('recurring_payments', 'schedule_anchor_index')
