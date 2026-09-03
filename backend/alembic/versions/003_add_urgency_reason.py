"""Add urgency_reason column to appointments

Revision ID: 003_add_urgency_reason
Revises: 002_seed_initial_data
Create Date: 2026-09-01 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_add_urgency_reason'
down_revision: Union[str, None] = '002_seed_initial_data'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'appointments',
        sa.Column('urgency_reason', sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('appointments', 'urgency_reason')
