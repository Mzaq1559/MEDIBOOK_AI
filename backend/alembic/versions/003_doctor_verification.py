"""Add doctor verification workflow

Revision ID: 003_doctor_verification
Revises: 002_seed_initial_data
Create Date: 2026-09-05 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_doctor_verification'
down_revision: Union[str, None] = '002_seed_initial_data'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add is_verified column to users table (default True for existing users)
    op.add_column(
        'users',
        sa.Column('is_verified', sa.Boolean(), server_default='true', nullable=False)
    )

    # 2. Make clinic_id nullable in doctors table (for pending self-registered doctors)
    op.alter_column(
        'doctors',
        'clinic_id',
        existing_type=sa.Uuid(),
        nullable=True,
        existing_server_default=None
    )

    # 3. Make specialization nullable in doctors table (for pending self-registered doctors)
    op.alter_column(
        'doctors',
        'specialization',
        existing_type=sa.String(length=100),
        nullable=True,
        existing_server_default=None
    )

    # 4. Update FK ondelete behavior for clinic_id from CASCADE to SET NULL
    op.drop_constraint('doctors_clinic_id_fkey', 'doctors', type_='foreignkey')
    op.create_foreign_key(
        'doctors_clinic_id_fkey',
        'doctors',
        'clinics',
        ['clinic_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Restore FK ondelete behavior
    op.drop_constraint('doctors_clinic_id_fkey', 'doctors', type_='foreignkey')
    op.create_foreign_key(
        'doctors_clinic_id_fkey',
        'doctors',
        'clinics',
        ['clinic_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Make specialization NOT NULL again
    op.alter_column(
        'doctors',
        'specialization',
        existing_type=sa.String(length=100),
        nullable=False,
        existing_server_default=None
    )

    # Make clinic_id NOT NULL again
    op.alter_column(
        'doctors',
        'clinic_id',
        existing_type=sa.Uuid(),
        nullable=False,
        existing_server_default=None
    )

    # Remove is_verified column
    op.drop_column('users', 'is_verified')
