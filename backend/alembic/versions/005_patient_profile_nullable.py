"""Make patient profile fields nullable to remove mock defaults

Revision ID: 005_patient_profile_nullable
Revises: 004_appointment_urgency_reason
Create Date: 2026-09-05 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_patient_profile_nullable'
down_revision: Union[str, None] = '004_appointment_urgency_reason'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make date_of_birth nullable (was NOT NULL with default 1990-01-01)
    op.alter_column(
        'patients',
        'date_of_birth',
        existing_type=sa.Date(),
        nullable=True,
        existing_server_default=None
    )

    # Make gender nullable (was NOT NULL with default 'M')
    op.alter_column(
        'patients',
        'gender',
        existing_type=sa.String(10),
        nullable=True,
        existing_server_default=None
    )

    # Make emergency_contact_name nullable (was NOT NULL with default 'Emergency Contact')
    op.alter_column(
        'patients',
        'emergency_contact_name',
        existing_type=sa.String(255),
        nullable=True,
        existing_server_default=None
    )

    # Make emergency_contact_phone nullable (was NOT NULL with default '03000000000')
    op.alter_column(
        'patients',
        'emergency_contact_phone',
        existing_type=sa.String(15),
        nullable=True,
        existing_server_default=None
    )


def downgrade() -> None:
    # Restore NOT NULL with defaults
    op.alter_column(
        'patients',
        'emergency_contact_phone',
        existing_type=sa.String(15),
        nullable=False,
        existing_server_default=None
    )

    op.alter_column(
        'patients',
        'emergency_contact_name',
        existing_type=sa.String(255),
        nullable=False,
        existing_server_default=None
    )

    op.alter_column(
        'patients',
        'gender',
        existing_type=sa.String(10),
        nullable=False,
        existing_server_default=None
    )

    op.alter_column(
        'patients',
        'date_of_birth',
        existing_type=sa.Date(),
        nullable=False,
        existing_server_default=None
    )
