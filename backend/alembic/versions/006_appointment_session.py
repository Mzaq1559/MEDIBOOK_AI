"""Add session to appointments table with data backfill and index

Revision ID: 006_appointment_session
Revises: 005_patient_profile_nullable
Create Date: 2026-09-07 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_appointment_session'
down_revision: Union[str, None] = '005_patient_profile_nullable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add column 'session' as nullable
    op.add_column('appointments', sa.Column('session', sa.String(length=20), nullable=True))

    # 2. Backfill existing appointments based on clinic timezone or Asia/Karachi (UTC+5)
    # Stored appointment_time is naive UTC. If local hour < 14 -> 'morning', else -> 'evening'
    try:
        bind = op.get_bind()
        dialect_name = bind.dialect.name if bind else ""
        if dialect_name == "postgresql":
            op.execute("""
                UPDATE appointments a
                SET session = CASE
                    WHEN EXTRACT(HOUR FROM (a.appointment_time AT TIME ZONE 'UTC' AT TIME ZONE COALESCE(c.timezone, 'Asia/Karachi'))) < 14 THEN 'morning'
                    ELSE 'evening'
                END
                FROM clinics c
                WHERE a.clinic_id = c.id AND a.session IS NULL
            """)
            op.execute("""
                UPDATE appointments
                SET session = CASE
                    WHEN EXTRACT(HOUR FROM (appointment_time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Karachi')) < 14 THEN 'morning'
                    ELSE 'evening'
                END
                WHERE session IS NULL
            """)
        elif dialect_name == "sqlite":
            op.execute("""
                UPDATE appointments
                SET session = CASE
                    WHEN CAST(strftime('%H', datetime(appointment_time, '+5 hours')) AS INTEGER) < 14 THEN 'morning'
                    ELSE 'evening'
                END
                WHERE session IS NULL
            """)
        else:
            op.execute("UPDATE appointments SET session = 'morning' WHERE session IS NULL")
    except Exception:
        op.execute("UPDATE appointments SET session = 'morning' WHERE session IS NULL")

    # 3. Alter column to NOT NULL with default 'morning'
    op.alter_column(
        'appointments',
        'session',
        existing_type=sa.String(length=20),
        nullable=False,
        server_default='morning'
    )

    # 4. Create index for fast capacity queries
    op.create_index(
        'idx_appt_doc_date_session',
        'appointments',
        ['doctor_id', 'session', 'appointment_time'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('idx_appt_doc_date_session', table_name='appointments')
    op.drop_column('appointments', 'session')
