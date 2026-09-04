"""Seed baseline database data for MediBook AI

Revision ID: 002_seed_initial_data
Revises: 001_initial_schema
Create Date: 2026-08-25 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import uuid

# revision identifiers, used by Alembic.
revision: str = '002_seed_initial_data'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Known UUIDs for reliable foreign key linking
CLINIC_1_ID = "11111111-1111-4111-a111-111111111111"
CLINIC_2_ID = "22222222-2222-4222-a222-222222222222"

USER_PATIENT_ID = "33333333-3333-4333-a333-333333333333"
USER_DOCTOR_ID = "44444444-4444-4444-a444-444444444444"
USER_ADMIN_ID = "55555555-5555-4555-a555-555555555555"

USER_DOC2_ID = "66666666-6666-4666-a666-666666666666"
USER_DOC3_ID = "77777777-7777-4777-a777-777777777777"
USER_PAT2_ID = "88888888-8888-4888-a888-888888888888"
USER_PAT3_ID = "99999999-9999-4999-a999-999999999999"

PATIENT_1_ID = "a3333333-3333-4333-a333-333333333333"
PATIENT_2_ID = "a8888888-8888-4888-a888-888888888888"
PATIENT_3_ID = "a9999999-9999-4999-a999-999999999999"

DOCTOR_1_ID = "b4444444-4444-4444-a444-444444444444"
DOCTOR_2_ID = "b6666666-6666-4666-a666-666666666666"
DOCTOR_3_ID = "b7777777-7777-4777-a777-777777777777"

APPT_TODAY_1 = "c1111111-1111-4111-a111-111111111111"
APPT_TODAY_2 = "c2222222-2222-4222-a222-222222222222"
APPT_TODAY_3 = "c3333333-3333-4333-a333-333333333333"
APPT_PAST_1  = "c4444444-4444-4444-a444-444444444444"
APPT_PAST_2  = "c5555555-5555-4555-a555-555555555555"
APPT_FUTURE_1= "c6666666-6666-4666-a666-666666666666"

PRESC_1_ID = "d1111111-1111-4111-a111-111111111111"
PRESC_2_ID = "d2222222-2222-4222-a222-222222222222"

# Bcrypt password hashes
# HASH_BULKSEED -> PatientPass123!   (used by all seed patients & doctors)
# HASH_ADMIN    -> Admin@123         (used by admin@medibook.com)
HASH_BULKSEED = "$2b$12$t/M7LGsC9Ma.ZfyEHvfxKOF.oNpykecjqsUxiRPJbsmOHxSc5HO66"
HASH_ADMIN    = "$2b$12$dw.NoAyl.UQabUFVSahMEe6GvS0mLVl4enWiNoGAGjKfX0JGGMmf6"


def upgrade() -> None:
    # 1. Clinics
    op.execute(sa.text(f"""
        INSERT INTO clinics (id, name, address, city, phone, email, working_hours_start, working_hours_end, working_days, timezone, is_active)
        VALUES
        ('{CLINIC_1_ID}', 'PrimeCare Hospital & Medical Center', '123 Jail Road, Gulberg', 'Lahore', '04235551234', 'info@primecare.pk', '08:00:00', '18:00:00', 'Mon,Tue,Wed,Thu,Fri,Sat', 'Asia/Karachi', true),
        ('{CLINIC_2_ID}', 'City Health Clinic', '45 Commercial Area, Phase 3 DHA', 'Lahore', '04235555678', 'contact@cityhealth.pk', '09:00:00', '17:00:00', 'Mon,Tue,Wed,Thu,Fri', 'Asia/Karachi', true)
        ON CONFLICT (id) DO NOTHING;
    """))

    # 2. Users (Test credentials: ali.khan@example.com / PatientPass123!, admin@medibook.com / Admin@123)
    op.execute(sa.text(f"""
        INSERT INTO users (id, email, phone, name, password_hash, user_type, is_active)
        VALUES
        ('{USER_PATIENT_ID}', 'ali.khan@example.com', '03001234567', 'Ali Khan', '{HASH_BULKSEED}', 'patient', true),
        ('{USER_DOCTOR_ID}', 'ahmed.khan@primecare.pk', '03007654321', 'Dr. Ahmed Khan', '{HASH_BULKSEED}', 'doctor', true),
        ('{USER_ADMIN_ID}', 'admin@medibook.com', '03009999999', 'System Administrator', '{HASH_ADMIN}', 'admin', true),
        ('{USER_DOC2_ID}', 'fatima.zahra@primecare.pk', '03001112233', 'Dr. Fatima Zahra', '{HASH_BULKSEED}', 'doctor', true),
        ('{USER_DOC3_ID}', 'tariq.mahmood@cityhealth.pk', '03004445566', 'Dr. Tariq Mahmood', '{HASH_BULKSEED}', 'doctor', true),
        ('{USER_PAT2_ID}', 'sara.ahmed@example.com', '03007778899', 'Sara Ahmed', '{HASH_BULKSEED}', 'patient', true),
        ('{USER_PAT3_ID}', 'usman.raza@example.com', '03002223344', 'Usman Raza', '{HASH_BULKSEED}', 'patient', true)
        ON CONFLICT (id) DO UPDATE SET password_hash = EXCLUDED.password_hash;
    """))

    # 3. Patients
    op.execute(sa.text(f"""
        INSERT INTO patients (id, user_id, date_of_birth, gender, blood_type, allergies, medical_conditions, emergency_contact_name, emergency_contact_phone, emergency_contact_relation, preferred_notification, total_appointments, total_no_shows)
        VALUES
        ('{PATIENT_1_ID}', '{USER_PATIENT_ID}', '1992-05-15', 'M', 'O+', '["Penicillin"]', '["Mild Asthma"]', 'Sarah Khan', '03007654321', 'Spouse', 'whatsapp', 3, 0),
        ('{PATIENT_2_ID}', '{USER_PAT2_ID}', '1988-11-20', 'F', 'A+', '[]', '["Hypertension"]', 'Tariq Ahmed', '03001112233', 'Brother', 'whatsapp', 2, 0),
        ('{PATIENT_3_ID}', '{USER_PAT3_ID}', '1995-03-10', 'M', 'B+', '[]', '[]', 'Zainab Raza', '03004445566', 'Mother', 'whatsapp', 1, 0)
        ON CONFLICT (id) DO NOTHING;
    """))

    # 4. Doctors
    op.execute(sa.text(f"""
        INSERT INTO doctors (id, user_id, clinic_id, specialization, qualifications, consultation_fee, bio, is_available, max_patients_per_day, appointment_duration_minutes, languages_spoken, rating, total_appointments)
        VALUES
        ('{DOCTOR_1_ID}', '{USER_DOCTOR_ID}', '{CLINIC_1_ID}', 'Cardiology', '["MBBS", "FCPS (Cardiology)"]', 2500.00, 'Senior Consultant Cardiologist with 12+ years of experience.', true, 20, 30, '["Urdu", "English"]', 4.90, 42),
        ('{DOCTOR_2_ID}', '{USER_DOC2_ID}', '{CLINIC_1_ID}', 'Dermatology', '["MBBS", "MCPS (Dermatology)"]', 2000.00, 'Consultant Dermatologist specializing in clinical & aesthetic care.', true, 16, 30, '["Urdu", "English"]', 4.85, 28),
        ('{DOCTOR_3_ID}', '{USER_DOC3_ID}', '{CLINIC_2_ID}', 'General Medicine', '["MBBS", "MRCP"]', 1800.00, 'General Physician with extensive expertise in chronic disease management.', true, 25, 30, '["Urdu", "English", "Punjabi"]', 4.75, 55)
        ON CONFLICT (id) DO NOTHING;
    """))

    # 5. Appointments
    op.execute(sa.text(f"""
        INSERT INTO appointments (id, clinic_id, doctor_id, patient_id, appointment_time, duration_minutes, status, appointment_type, symptoms_reported, urgency_level, notes, feedback_score, feedback_text, created_at)
        VALUES
        ('{APPT_TODAY_1}', '{CLINIC_1_ID}', '{DOCTOR_1_ID}', '{PATIENT_1_ID}', (CURRENT_DATE + INTERVAL '10 hours'), 30, 'scheduled', 'in_person', 'Chest discomfort after light exercise and mild fatigue', 'normal', NULL, NULL, NULL, (CURRENT_DATE - INTERVAL '1 day')),
        ('{APPT_TODAY_2}', '{CLINIC_1_ID}', '{DOCTOR_1_ID}', '{PATIENT_2_ID}', (CURRENT_DATE + INTERVAL '11 hours 30 minutes'), 30, 'completed', 'in_person', 'Palpitations and shortness of breath', 'high', 'ECG performed, normal sinus rhythm. Advised Holter monitoring.', 5, 'Dr. Ahmed Khan was extremely thorough and reassuring.', (CURRENT_DATE - INTERVAL '2 days')),
        ('{APPT_TODAY_3}', '{CLINIC_1_ID}', '{DOCTOR_1_ID}', '{PATIENT_3_ID}', (CURRENT_DATE + INTERVAL '14 hours'), 30, 'scheduled', 'in_person', 'Routine hypertension follow-up consultation', 'low', NULL, NULL, NULL, (CURRENT_DATE - INTERVAL '3 days')),
        ('{APPT_PAST_1}', '{CLINIC_2_ID}', '{DOCTOR_3_ID}', '{PATIENT_1_ID}', (CURRENT_DATE - INTERVAL '10 days' + INTERVAL '09 hours 30 minutes'), 30, 'completed', 'in_person', 'Persistent dry cough and mild fever', 'normal', 'Acute bronchitis. Prescribed antibiotic course and cough sedative.', 5, 'Very professional doctor and great clinic service!', (CURRENT_DATE - INTERVAL '12 days')),
        ('{APPT_PAST_2}', '{CLINIC_1_ID}', '{DOCTOR_1_ID}', '{PATIENT_1_ID}', (CURRENT_DATE - INTERVAL '20 days' + INTERVAL '15 hours'), 30, 'completed', 'in_person', 'Annual cardiac checkup', 'normal', 'BP 120/80. Lipid profile normal. Continue current lifestyle.', 5, 'Thorough examination and great feedback.', (CURRENT_DATE - INTERVAL '22 days')),
        ('{APPT_FUTURE_1}', '{CLINIC_1_ID}', '{DOCTOR_2_ID}', '{PATIENT_1_ID}', (CURRENT_DATE + INTERVAL '3 days' + INTERVAL '11 hours'), 30, 'scheduled', 'in_person', 'Skin rash on forearms', 'low', NULL, NULL, NULL, CURRENT_DATE)
        ON CONFLICT (id) DO NOTHING;
    """))

    # 6. Prescriptions
    op.execute(sa.text(f"""
        INSERT INTO prescriptions (id, appointment_id, doctor_id, patient_id, medication, dosage, duration, notes, created_at)
        VALUES
        ('{PRESC_1_ID}', '{APPT_TODAY_2}', '{DOCTOR_1_ID}', '{PATIENT_2_ID}', 'Atenolol 50mg', '1 tablet daily', '30 days', 'Take in the morning after breakfast.', CURRENT_TIMESTAMP),
        ('{PRESC_2_ID}', '{APPT_PAST_1}', '{DOCTOR_3_ID}', '{PATIENT_1_ID}', 'Amoxicillin 500mg', '1 capsule thrice daily', '7 days', 'Complete full course of antibiotics.', CURRENT_TIMESTAMP)
        ON CONFLICT (id) DO NOTHING;
    """))

    # 7. Doctor Schedules for Today
    op.execute(sa.text(f"""
        INSERT INTO doctor_schedules (id, doctor_id, date, start_time, end_time, is_holiday, max_patients)
        VALUES
        ('{uuid.uuid4()}', '{DOCTOR_1_ID}', CURRENT_DATE, '08:00:00', '17:00:00', false, 20),
        ('{uuid.uuid4()}', '{DOCTOR_2_ID}', CURRENT_DATE, '09:00:00', '16:00:00', false, 16),
        ('{uuid.uuid4()}', '{DOCTOR_3_ID}', CURRENT_DATE, '09:00:00', '17:00:00', false, 25)
        ON CONFLICT (doctor_id, date) DO NOTHING;
    """))


def downgrade() -> None:
    op.execute(sa.text(f"DELETE FROM prescriptions WHERE id IN ('{PRESC_1_ID}', '{PRESC_2_ID}');"))
    op.execute(sa.text(f"DELETE FROM appointments WHERE id IN ('{APPT_TODAY_1}', '{APPT_TODAY_2}', '{APPT_TODAY_3}', '{APPT_PAST_1}', '{APPT_PAST_2}', '{APPT_FUTURE_1}');"))
    op.execute(sa.text(f"DELETE FROM doctors WHERE id IN ('{DOCTOR_1_ID}', '{DOCTOR_2_ID}', '{DOCTOR_3_ID}');"))
    op.execute(sa.text(f"DELETE FROM patients WHERE id IN ('{PATIENT_1_ID}', '{PATIENT_2_ID}', '{PATIENT_3_ID}');"))
    op.execute(sa.text(f"DELETE FROM users WHERE id IN ('{USER_PATIENT_ID}', '{USER_DOCTOR_ID}', '{USER_ADMIN_ID}', '{USER_DOC2_ID}', '{USER_DOC3_ID}', '{USER_PAT2_ID}', '{USER_PAT3_ID}');"))
    op.execute(sa.text(f"DELETE FROM clinics WHERE id IN ('{CLINIC_1_ID}', '{CLINIC_2_ID}');"))
