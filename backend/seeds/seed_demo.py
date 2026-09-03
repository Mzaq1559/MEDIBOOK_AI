"""
Seed script — populates the database with demo data for hackathon/judging.

Standard login credentials:
  Admin:       admin@medibook.ai      / Admin@1234!
  Doctor 1:    dr.ahmed@medibook.ai   / Doctor@1234!
  Doctor 2:    dr.sara@medibook.ai    / Doctor@1234!
  Patient 1:   ali.khan@medibook.ai   / Patient@1234!
  Patient 2:   fatima.b@medibook.ai   / Patient@1234!

Run standalone: python seeds/seed_demo.py
Run via Docker: called from docker-compose entrypoint
"""

import os
import sys
import uuid
import json
import time
import logging
from datetime import date, datetime, timedelta, time as t

# ── ensure backend package is on path ─────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("seed")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://medibook:password123@localhost:5432/medibook_db",
)

# ── helpers ───────────────────────────────────────────────────────────────────

def _hash(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")


def _wait_for_db(engine, retries: int = 15, delay: int = 3) -> None:
    for i in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as exc:
            log.warning(f"DB not ready ({i+1}/{retries}): {exc}")
            time.sleep(delay)
    raise RuntimeError("Could not connect to the database after multiple retries.")


# ── IDs (fixed so re-runs are idempotent) ─────────────────────────────────────
CLINIC_ID   = uuid.UUID("00000000-0000-0000-0000-000000000001")

U_ADMIN     = uuid.UUID("00000000-0000-0000-0001-000000000001")
U_DOCTOR1   = uuid.UUID("00000000-0000-0000-0001-000000000002")
U_DOCTOR2   = uuid.UUID("00000000-0000-0000-0001-000000000003")
U_PATIENT1  = uuid.UUID("00000000-0000-0000-0001-000000000004")
U_PATIENT2  = uuid.UUID("00000000-0000-0000-0001-000000000005")

D_DOCTOR1   = uuid.UUID("00000000-0000-0000-0002-000000000001")
D_DOCTOR2   = uuid.UUID("00000000-0000-0000-0002-000000000002")

P_PATIENT1  = uuid.UUID("00000000-0000-0000-0003-000000000001")
P_PATIENT2  = uuid.UUID("00000000-0000-0000-0003-000000000002")

NOW = datetime.utcnow()


# ── seed data ─────────────────────────────────────────────────────────────────

def seed(session) -> None:

    # ── 1. Clinic ──────────────────────────────────────────────────────────
    existing_clinic = session.execute(
        text("SELECT id FROM clinics WHERE id = :id"), {"id": str(CLINIC_ID)}
    ).fetchone()

    if not existing_clinic:
        session.execute(text("""
            INSERT INTO clinics
                (id, name, address, city, phone, email,
                 working_hours_start, working_hours_end,
                 working_days, timezone, is_active, created_at, updated_at)
            VALUES
                (:id, :name, :address, :city, :phone, :email,
                 :whs, :whe, :wd, :tz, true, :now, :now)
        """), {
            "id":      str(CLINIC_ID),
            "name":    "MediBook Clinic",
            "address": "Plot 5, Blue Area, Islamabad",
            "city":    "Islamabad",
            "phone":   "0519876543",
            "email":   "clinic@medibook.ai",
            "whs":     "09:00:00",
            "whe":     "17:00:00",
            "wd":      "Mon,Tue,Wed,Thu,Fri",
            "tz":      "Asia/Karachi",
            "now":     NOW,
        })
        log.info("Created clinic: MediBook Clinic")
    else:
        log.info("Clinic already exists, skipping.")

    # ── 2. Users ───────────────────────────────────────────────────────────
    users = [
        {
            "id":            str(U_ADMIN),
            "email":         "admin@medibook.ai",
            "phone":         "03001000001",
            "name":          "Super Admin",
            "password_hash": _hash("Admin@1234!"),
            "user_type":     "admin",
        },
        {
            "id":            str(U_DOCTOR1),
            "email":         "dr.ahmed@medibook.ai",
            "phone":         "03001000002",
            "name":          "Dr. Ahmed Khan",
            "password_hash": _hash("Doctor@1234!"),
            "user_type":     "doctor",
        },
        {
            "id":            str(U_DOCTOR2),
            "email":         "dr.sara@medibook.ai",
            "phone":         "03001000003",
            "name":          "Dr. Sara Malik",
            "password_hash": _hash("Doctor@1234!"),
            "user_type":     "doctor",
        },
        {
            "id":            str(U_PATIENT1),
            "email":         "ali.khan@medibook.ai",
            "phone":         "03001000004",
            "name":          "Ali Khan",
            "password_hash": _hash("Patient@1234!"),
            "user_type":     "patient",
        },
        {
            "id":            str(U_PATIENT2),
            "email":         "fatima.b@medibook.ai",
            "phone":         "03001000005",
            "name":          "Fatima Baig",
            "password_hash": _hash("Patient@1234!"),
            "user_type":     "patient",
        },
    ]

    for u in users:
        exists = session.execute(
            text("SELECT id FROM users WHERE id = :id"), {"id": u["id"]}
        ).fetchone()
        if not exists:
            session.execute(text("""
                INSERT INTO users
                    (id, email, phone, name, password_hash, user_type,
                     is_active, created_at, updated_at)
                VALUES
                    (:id, :email, :phone, :name, :password_hash, :user_type,
                     true, :now, :now)
            """), {**u, "now": NOW})
            log.info(f"Created user: {u['email']}")
        else:
            log.info(f"User {u['email']} already exists, skipping.")

    # ── 3. Doctors ─────────────────────────────────────────────────────────
    doctors = [
        {
            "id":             str(D_DOCTOR1),
            "user_id":        str(U_DOCTOR1),
            "clinic_id":      str(CLINIC_ID),
            "specialization": "General Physician",
            "qualifications": json.dumps(["MBBS", "FCPS"]),
            "consultation_fee": "2000.00",
            "bio":            "Experienced general physician with 10+ years in primary care.",
            "max_patients":   20,
            "duration_min":   30,
            "languages":      json.dumps(["Urdu", "English"]),
        },
        {
            "id":             str(D_DOCTOR2),
            "user_id":        str(U_DOCTOR2),
            "clinic_id":      str(CLINIC_ID),
            "specialization": "Cardiologist",
            "qualifications": json.dumps(["MBBS", "MD Cardiology"]),
            "consultation_fee": "3500.00",
            "bio":            "Specialist cardiologist focused on preventive cardiac care.",
            "max_patients":   15,
            "duration_min":   45,
            "languages":      json.dumps(["Urdu", "English"]),
        },
    ]

    for d in doctors:
        exists = session.execute(
            text("SELECT id FROM doctors WHERE id = :id"), {"id": d["id"]}
        ).fetchone()
        if not exists:
            session.execute(text("""
                INSERT INTO doctors
                    (id, user_id, clinic_id, specialization, qualifications,
                     consultation_fee, bio, is_available,
                     max_patients_per_day, appointment_duration_minutes,
                     languages_spoken, rating, total_appointments,
                     created_at, updated_at)
                VALUES
                    (:id, :user_id, :clinic_id, :specialization, :qualifications,
                     :consultation_fee, :bio, true,
                     :max_patients, :duration_min,
                     :languages, 4.5, 0,
                     :now, :now)
            """), {**d, "now": NOW})
            log.info(f"Created doctor: {d['specialization']}")
        else:
            log.info(f"Doctor {d['id']} already exists, skipping.")

    # ── 4. Doctor Schedules (next 14 days, Mon-Fri) ────────────────────────
    doctor_ids = [str(D_DOCTOR1), str(D_DOCTOR2)]
    for doctor_id in doctor_ids:
        for offset in range(14):
            sched_date = date.today() + timedelta(days=offset)
            if sched_date.weekday() >= 5:   # skip Sat/Sun
                continue
            exists = session.execute(text("""
                SELECT id FROM doctor_schedules
                WHERE doctor_id = :did AND date = :date
            """), {"did": doctor_id, "date": sched_date}).fetchone()
            if not exists:
                session.execute(text("""
                    INSERT INTO doctor_schedules
                        (id, doctor_id, date, start_time, end_time,
                         is_holiday, break_start, break_end,
                         max_patients, created_at, updated_at)
                    VALUES
                        (:id, :did, :date, '09:00:00', '17:00:00',
                         false, '13:00:00', '14:00:00',
                         20, :now, :now)
                """), {
                    "id":   str(uuid.uuid4()),
                    "did":  doctor_id,
                    "date": sched_date,
                    "now":  NOW,
                })
    log.info("Doctor schedules seeded (next 14 weekdays).")

    # ── 5. Patients ────────────────────────────────────────────────────────
    patients = [
        {
            "id":             str(P_PATIENT1),
            "user_id":        str(U_PATIENT1),
            "dob":            date(1990, 3, 15),
            "gender":         "M",
            "blood_type":     "O+",
            "allergies":      json.dumps(["Penicillin"]),
            "conditions":     json.dumps(["Hypertension"]),
            "ec_name":        "Zara Khan",
            "ec_phone":       "03009000001",
            "ec_relation":    "Sister",
        },
        {
            "id":             str(P_PATIENT2),
            "user_id":        str(U_PATIENT2),
            "dob":            date(1995, 7, 22),
            "gender":         "F",
            "blood_type":     "A+",
            "allergies":      json.dumps([]),
            "conditions":     json.dumps(["Diabetes Type 2"]),
            "ec_name":        "Khalid Baig",
            "ec_phone":       "03009000002",
            "ec_relation":    "Father",
        },
    ]

    for p in patients:
        exists = session.execute(
            text("SELECT id FROM patients WHERE id = :id"), {"id": p["id"]}
        ).fetchone()
        if not exists:
            session.execute(text("""
                INSERT INTO patients
                    (id, user_id, date_of_birth, gender, blood_type,
                     allergies, medical_conditions,
                     emergency_contact_name, emergency_contact_phone,
                     emergency_contact_relation,
                     preferred_notification, total_appointments, total_no_shows,
                     created_at, updated_at)
                VALUES
                    (:id, :user_id, :dob, :gender, :blood_type,
                     :allergies, :conditions,
                     :ec_name, :ec_phone, :ec_relation,
                     'email', 0, 0, :now, :now)
            """), {**p, "now": NOW})
            log.info(f"Created patient: {p['id']}")
        else:
            log.info(f"Patient {p['id']} already exists, skipping.")

    # ── 6. Sample appointments (past + upcoming) ────────────────────────────
    appts = [
        # completed — yesterday
        {
            "id":           str(uuid.UUID("00000000-0000-0000-0004-000000000001")),
            "doctor_id":    str(D_DOCTOR1),
            "patient_id":   str(P_PATIENT1),
            "appt_time":    NOW - timedelta(days=1),
            "status":       "completed",
            "symptoms":     "Fever and headache",
            "urgency":      "normal",
        },
        # upcoming — tomorrow
        {
            "id":           str(uuid.UUID("00000000-0000-0000-0004-000000000002")),
            "doctor_id":    str(D_DOCTOR1),
            "patient_id":   str(P_PATIENT1),
            "appt_time":    NOW + timedelta(days=1),
            "status":       "scheduled",
            "symptoms":     "Follow-up checkup",
            "urgency":      "low",
        },
        # upcoming — day after tomorrow (cardiology)
        {
            "id":           str(uuid.UUID("00000000-0000-0000-0004-000000000003")),
            "doctor_id":    str(D_DOCTOR2),
            "patient_id":   str(P_PATIENT2),
            "appt_time":    NOW + timedelta(days=2),
            "status":       "scheduled",
            "symptoms":     "Chest discomfort and shortness of breath",
            "urgency":      "high",
        },
    ]

    for a in appts:
        exists = session.execute(
            text("SELECT id FROM appointments WHERE id = :id"), {"id": a["id"]}
        ).fetchone()
        if not exists:
            session.execute(text("""
                INSERT INTO appointments
                    (id, clinic_id, doctor_id, patient_id, appointment_time,
                     duration_minutes, status, appointment_type,
                     symptoms_reported, urgency_level,
                     is_walk_in, reminder_sent_24h, reminder_sent_1h,
                     created_at, updated_at)
                VALUES
                    (:id, :clinic_id, :doctor_id, :patient_id, :appt_time,
                     30, :status, 'in_person',
                     :symptoms, :urgency,
                     false, false, false,
                     :now, :now)
            """), {**a, "clinic_id": str(CLINIC_ID), "now": NOW})
            log.info(f"Created appointment: {a['status']} – {a['symptoms'][:40]}")
        else:
            log.info(f"Appointment {a['id']} already exists, skipping.")

    session.commit()
    log.info("✅  Seed complete.")


# ── entrypoint ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    _wait_for_db(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        seed(session)
