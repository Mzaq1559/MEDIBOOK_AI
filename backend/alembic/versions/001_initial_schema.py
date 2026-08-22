"""Initial database schema with all 9 MediBook models

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-22 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=15), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('user_type', sa.String(length=50), nullable=False),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('phone')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_user_type', 'users', ['user_type'], unique=False)
    op.create_index('ix_users_created_at', 'users', ['created_at'], unique=False)

    # 2. clinics table
    op.create_table(
        'clinics',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=15), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('working_hours_start', sa.Time(), nullable=False),
        sa.Column('working_hours_end', sa.Time(), nullable=False),
        sa.Column('working_days', sa.String(length=50), nullable=False),
        sa.Column('timezone', sa.String(length=50), server_default='Asia/Karachi', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_clinics_city', 'clinics', ['city'], unique=False)
    op.create_index('ix_clinics_is_active', 'clinics', ['is_active'], unique=False)

    # 3. doctors table
    op.create_table(
        'doctors',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('clinic_id', sa.Uuid(), nullable=False),
        sa.Column('specialization', sa.String(length=100), nullable=False),
        sa.Column('qualifications', sa.Text(), nullable=False),
        sa.Column('consultation_fee', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('is_available', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('max_patients_per_day', sa.Integer(), server_default='20', nullable=False),
        sa.Column('appointment_duration_minutes', sa.Integer(), server_default='30', nullable=False),
        sa.Column('languages_spoken', sa.Text(), nullable=False),
        sa.Column('rating', sa.Numeric(precision=3, scale=2), server_default='0.0', nullable=False),
        sa.Column('total_appointments', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_doctors_clinic_id', 'doctors', ['clinic_id'], unique=False)
    op.create_index('ix_doctors_specialization', 'doctors', ['specialization'], unique=False)
    op.create_index('ix_doctors_is_available', 'doctors', ['is_available'], unique=False)
    op.create_index('idx_doctor_clinic_available', 'doctors', ['clinic_id', 'is_available'], unique=False)

    # 4. patients table
    op.create_table(
        'patients',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=False),
        sa.Column('gender', sa.String(length=10), nullable=False),
        sa.Column('blood_type', sa.String(length=5), nullable=True),
        sa.Column('allergies', sa.Text(), nullable=True),
        sa.Column('medical_conditions', sa.Text(), nullable=True),
        sa.Column('emergency_contact_name', sa.String(length=255), nullable=False),
        sa.Column('emergency_contact_phone', sa.String(length=15), nullable=False),
        sa.Column('emergency_contact_relation', sa.String(length=50), nullable=True),
        sa.Column('preferred_notification', sa.String(length=20), server_default='whatsapp', nullable=False),
        sa.Column('total_appointments', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_no_shows', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_patients_preferred_notification', 'patients', ['preferred_notification'], unique=False)

    # 5. appointments table
    op.create_table(
        'appointments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('clinic_id', sa.Uuid(), nullable=False),
        sa.Column('doctor_id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=False),
        sa.Column('appointment_time', sa.DateTime(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), server_default='30', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='scheduled', nullable=False),
        sa.Column('appointment_type', sa.String(length=20), server_default='in_person', nullable=False),
        sa.Column('symptoms_reported', sa.Text(), nullable=False),
        sa.Column('urgency_level', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('prescription_id', sa.Uuid(), nullable=True),
        sa.Column('is_walk_in', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('reminder_sent_24h', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('reminder_sent_1h', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('feedback_score', sa.Integer(), nullable=True),
        sa.Column('feedback_text', sa.Text(), nullable=True),
        sa.Column('google_calendar_event_id', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_appointments_clinic_id', 'appointments', ['clinic_id'], unique=False)
    op.create_index('ix_appointments_doctor_id', 'appointments', ['doctor_id'], unique=False)
    op.create_index('ix_appointments_patient_id', 'appointments', ['patient_id'], unique=False)
    op.create_index('ix_appointments_appointment_time', 'appointments', ['appointment_time'], unique=False)
    op.create_index('idx_appt_doc_time', 'appointments', ['doctor_id', 'appointment_time'], unique=False)
    op.create_index('idx_appt_clinic_time', 'appointments', ['clinic_id', 'appointment_time'], unique=False)
    op.create_index('idx_appt_pat_status', 'appointments', ['patient_id', 'status'], unique=False)

    # 6. doctor_schedules table
    op.create_table(
        'doctor_schedules',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('doctor_id', sa.Uuid(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=True),
        sa.Column('end_time', sa.Time(), nullable=True),
        sa.Column('is_holiday', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('holiday_reason', sa.String(length=255), nullable=True),
        sa.Column('break_start', sa.Time(), nullable=True),
        sa.Column('break_end', sa.Time(), nullable=True),
        sa.Column('max_patients', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('doctor_id', 'date', name='uq_doctor_schedule_date')
    )
    op.create_index('ix_doctor_schedules_doctor_id', 'doctor_schedules', ['doctor_id'], unique=False)

    # 7. clinic_holidays table
    op.create_table(
        'clinic_holidays',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('clinic_id', sa.Uuid(), nullable=False),
        sa.Column('holiday_date', sa.Date(), nullable=False),
        sa.Column('holiday_name', sa.String(length=255), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clinic_id', 'holiday_date', name='uq_clinic_holiday_date')
    )
    op.create_index('ix_clinic_holidays_clinic_id', 'clinic_holidays', ['clinic_id'], unique=False)

    # 8. prescriptions table
    op.create_table(
        'prescriptions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('appointment_id', sa.Uuid(), nullable=False),
        sa.Column('doctor_id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=False),
        sa.Column('medications', sa.Text(), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('validity_days', sa.Integer(), server_default='30', nullable=False),
        sa.Column('issued_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('appointment_id')
    )

    # 9. audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('action', sa.String(length=255), nullable=False),
        sa.Column('table_name', sa.String(length=100), nullable=False),
        sa.Column('record_id', sa.Uuid(), nullable=False),
        sa.Column('old_values', sa.JSON(), nullable=True),
        sa.Column('new_values', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'], unique=False)
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'], unique=False)
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('prescriptions')
    op.drop_table('clinic_holidays')
    op.drop_table('doctor_schedules')
    op.drop_table('appointments')
    op.drop_table('patients')
    op.drop_table('doctors')
    op.drop_table('clinics')
    op.drop_table('users')
