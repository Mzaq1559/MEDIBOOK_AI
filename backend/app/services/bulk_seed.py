"""Bulk test-data seeder for MediBook AI.

Generates clinics, doctors, patients, and appointments at scale.
All rows are tagged via @bulkseed.medibook.test emails so re-runs safely
replace prior bulk data without touching admin or manually created accounts.
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional

from faker import Faker
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.database import Base, SessionLocal, engine
from app.models.appointment import Appointment
from app.models.clinic import Clinic
from app.models.clinic_holiday import ClinicHoliday
from app.models.doctor import Doctor
from app.models.doctor_schedule import DoctorSchedule
from app.models.patient import Patient
from app.models.user import User

BULK_SEED_EMAIL_DOMAIN = "bulkseed.medibook.test"
BULK_SEED_PASSWORD = "BulkSeed123!"

# Specializations the AI triage service can recommend (symptom_triage.py).
AI_TRIAGE_SPECIALIZATIONS = ("Cardiologist", "Dermatologist", "ENT Specialist")

SPECIALIZATIONS = [
    "Cardiologist",
    "Dermatologist",
    "ENT Specialist",
    "General Physician",
    "Pediatrician",
    "Orthopedic",
    "Gynecologist",
    "Psychiatrist",
]

# At least 2 doctors per specialization; AI triage specs get 3.
DOCTORS_PER_SPECIALIZATION = {
    "Cardiologist": 3,
    "Dermatologist": 3,
    "ENT Specialist": 3,
    "General Physician": 2,
    "Pediatrician": 2,
    "Orthopedic": 2,
    "Gynecologist": 2,
    "Psychiatrist": 2,
}

CLINIC_TEMPLATES = [
    {
        "name": "Al-Shifa Medical Center",
        "city": "Islamabad",
        "address": "Plot 12, Blue Area, Jinnah Avenue, Islamabad",
        "slug": "alshifa-isb",
    },
    {
        "name": "City Care Clinic",
        "city": "Rawalpindi",
        "address": "Shop 4, Saddar Bazaar, Rawalpindi Cantt",
        "slug": "citycare-rwp",
    },
    {
        "name": "Taxila Family Health Clinic",
        "city": "Taxila",
        "address": "Main GT Road, Near Taxila Museum, Taxila",
        "slug": "taxila-family",
    },
]

SPECIALIZATION_SYMPTOMS: dict[str, list[str]] = {
    "Cardiologist": [
        "Chest tightness and mild palpitation after climbing stairs.",
        "Shortness of breath and irregular heartbeat for the past week.",
        "Persistent high blood pressure readings at home.",
        "Angina-like chest discomfort during physical activity.",
    ],
    "Dermatologist": [
        "Itchy red rash spreading on forearms and neck.",
        "Persistent acne breakout on face and back.",
        "Dry eczema patches on elbows with mild itching.",
        "New mole with irregular borders — wants dermatology review.",
    ],
    "ENT Specialist": [
        "Sore throat, nasal congestion, and sinus pressure for 5 days.",
        "Ear pain with reduced hearing in the left ear.",
        "Chronic cough and post-nasal drip after a cold.",
        "Tinnitus and blocked nose affecting sleep.",
    ],
    "General Physician": [
        "General fatigue, mild fever, and body aches for 3 days.",
        "Recurring headaches and occasional dizziness.",
        "Routine check-up for diabetes and blood pressure monitoring.",
        "Upset stomach, nausea, and loss of appetite.",
    ],
    "Pediatrician": [
        "Child has high fever and sore throat for 2 days.",
        "Toddler with persistent cough and runny nose.",
        "Growth and vaccination follow-up for 4-year-old.",
        "Child complaining of ear pain after swimming.",
    ],
    "Orthopedic": [
        "Knee pain and swelling after a sports injury.",
        "Lower back pain radiating to the left leg.",
        "Shoulder stiffness and pain when lifting arm.",
        "Ankle sprain with difficulty walking.",
    ],
    "Gynecologist": [
        "Irregular menstrual cycles and pelvic discomfort.",
        "Routine prenatal check-up at 12 weeks.",
        "Menstrual cramps worsening over last few months.",
        "Follow-up for PCOS management.",
    ],
    "Psychiatrist": [
        "Persistent anxiety and difficulty sleeping for several weeks.",
        "Low mood, loss of interest, and fatigue.",
        "Panic attacks with racing heart and sweating.",
        "Stress-related burnout and trouble concentrating.",
    ],
}

QUALIFICATIONS_BY_SPEC: dict[str, list[str]] = {
    "Cardiologist": ["MBBS", "FCPS Cardiology", "MRCP"],
    "Dermatologist": ["MBBS", "FCPS Dermatology"],
    "ENT Specialist": ["MBBS", "MS Otolaryngology"],
    "General Physician": ["MBBS", "FCPS Medicine"],
    "Pediatrician": ["MBBS", "FCPS Pediatrics"],
    "Orthopedic": ["MBBS", "FCPS Orthopedics"],
    "Gynecologist": ["MBBS", "FCPS Gynecology"],
    "Psychiatrist": ["MBBS", "FCPS Psychiatry"],
}

BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
ALLERGIES_POOL = ["Penicillin", "Aspirin", "Peanuts", "Dust", "Pollen", "Sulfa drugs", "Latex"]
CONDITIONS_POOL = ["Hypertension", "Diabetes", "Asthma", "Hypothyroidism", "Migraine", "GERD"]
RELATIONS = ["Spouse", "Brother", "Sister", "Father", "Mother", "Son", "Daughter", "Friend"]
LANGUAGE_OPTIONS = [
    ["Urdu", "English"],
    ["Urdu", "English", "Punjabi"],
    ["Urdu", "English", "Pashto"],
    ["Urdu"],
    ["English", "Urdu"],
]

MALE_FIRST = [
    "Ahmed", "Ali", "Usman", "Hassan", "Bilal", "Omar", "Zain", "Hamza", "Tariq", "Imran",
    "Faisal", "Kamran", "Nadeem", "Saeed", "Rashid", "Asad", "Waqas", "Shahid", "Farhan", "Adnan",
]
FEMALE_FIRST = [
    "Fatima", "Ayesha", "Sara", "Hina", "Sana", "Maria", "Nadia", "Rabia", "Amna", "Zara",
    "Saima", "Kiran", "Bushra", "Samina", "Farah", "Mehwish", "Sidra", "Noreen", "Shazia", "Laiba",
]
LAST_NAMES = [
    "Khan", "Malik", "Ahmed", "Hussain", "Ali", "Sheikh", "Raza", "Iqbal", "Butt", "Chaudhry",
    "Mirza", "Siddiqui", "Tariq", "Akram", "Baig", "Hashmi", "Qureshi", "Shah", "Abbasi", "Javed",
]

faker = Faker("en_PK")
Faker.seed(42)
random.seed(42)


def _bulk_email(local: str) -> str:
    return f"{local}@{BULK_SEED_EMAIL_DOMAIN}"


def _pakistani_phone(used: set[str]) -> str:
    """Generate unique 03XXXXXXXXX phone numbers."""
    for _ in range(500):
        prefix = random.choice(["030", "031", "032", "033", "034", "035"])
        phone = prefix + "".join(str(random.randint(0, 9)) for _ in range(8))
        if phone not in used:
            used.add(phone)
            return phone
    raise RuntimeError("Could not generate unique phone number")


def _random_name(gender: str) -> str:
    if gender == "F":
        return f"{random.choice(FEMALE_FIRST)} {random.choice(LAST_NAMES)}"
    return f"{random.choice(MALE_FIRST)} {random.choice(LAST_NAMES)}"


def _doctor_display_name(name: str) -> str:
    return name if name.startswith("Dr.") else f"Dr. {name}"


def _weekday_dates(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _slot_times(duration: int = 30) -> list[time]:
    """9:00–17:00 with lunch break 13:00–14:00."""
    slots: list[time] = []
    start_minutes = 9 * 60
    end_minutes = 17 * 60
    lunch_start = 13 * 60
    lunch_end = 14 * 60
    current = start_minutes
    while current + duration <= end_minutes:
        if not (current >= lunch_start and current < lunch_end):
            slots.append(time(current // 60, current % 60))
        current += duration
    return slots


def clear_bulk_seed_data(db: Session) -> dict:
    """Remove all prior bulk-seeded rows (scoped by email domain)."""
    bulk_clinics = db.query(Clinic).filter(Clinic.email.like(f"%@{BULK_SEED_EMAIL_DOMAIN}")).all()
    bulk_clinic_ids = [c.id for c in bulk_clinics]

    bulk_users = db.query(User).filter(User.email.like(f"%@{BULK_SEED_EMAIL_DOMAIN}")).all()
    bulk_user_ids = [u.id for u in bulk_users]

    bulk_doctors = db.query(Doctor).filter(Doctor.user_id.in_(bulk_user_ids)).all() if bulk_user_ids else []
    bulk_doctor_ids = [d.id for d in bulk_doctors]

    bulk_patients = db.query(Patient).filter(Patient.user_id.in_(bulk_user_ids)).all() if bulk_user_ids else []
    bulk_patient_ids = [p.id for p in bulk_patients]

    appt_filters = []
    if bulk_clinic_ids:
        appt_filters.append(Appointment.clinic_id.in_(bulk_clinic_ids))
    if bulk_doctor_ids:
        appt_filters.append(Appointment.doctor_id.in_(bulk_doctor_ids))
    if bulk_patient_ids:
        appt_filters.append(Appointment.patient_id.in_(bulk_patient_ids))

    deleted = {"appointments": 0, "schedules": 0, "holidays": 0, "doctors": 0, "patients": 0, "users": 0, "clinics": 0}

    if appt_filters:
        deleted["appointments"] = (
            db.query(Appointment)
            .filter(or_(*appt_filters))
            .delete(synchronize_session=False)
        )

    if bulk_doctor_ids:
        deleted["schedules"] = (
            db.query(DoctorSchedule)
            .filter(DoctorSchedule.doctor_id.in_(bulk_doctor_ids))
            .delete(synchronize_session=False)
        )

    if bulk_clinic_ids:
        deleted["holidays"] = (
            db.query(ClinicHoliday)
            .filter(ClinicHoliday.clinic_id.in_(bulk_clinic_ids))
            .delete(synchronize_session=False)
        )

    if bulk_doctor_ids:
        deleted["doctors"] = (
            db.query(Doctor)
            .filter(Doctor.id.in_(bulk_doctor_ids))
            .delete(synchronize_session=False)
        )

    if bulk_patient_ids:
        deleted["patients"] = (
            db.query(Patient)
            .filter(Patient.id.in_(bulk_patient_ids))
            .delete(synchronize_session=False)
        )

    if bulk_user_ids:
        deleted["users"] = (
            db.query(User)
            .filter(User.id.in_(bulk_user_ids))
            .delete(synchronize_session=False)
        )

    if bulk_clinic_ids:
        deleted["clinics"] = (
            db.query(Clinic)
            .filter(Clinic.id.in_(bulk_clinic_ids))
            .delete(synchronize_session=False)
        )

    db.commit()
    return deleted


def seed_bulk_test_data(db: Optional[Session] = None) -> dict:
    """Generate realistic bulk test data. Safe to re-run."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        target_bind = db.get_bind() if db else engine
        Base.metadata.create_all(bind=target_bind)

        print("--> Clearing previous bulk-seed data (if any)...")
        cleared = clear_bulk_seed_data(db)
        if any(cleared.values()):
            print(f"    Cleared: {cleared}")

        print("--> Seeding bulk test data...")
        used_phones: set[str] = set()
        password_hash = get_password_hash(BULK_SEED_PASSWORD)
        now = datetime.utcnow()
        today = date.today()

        # --- Clinics ---
        clinics: list[Clinic] = []
        for tmpl in CLINIC_TEMPLATES:
            clinic = Clinic(
                id=uuid.uuid4(),
                name=tmpl["name"],
                address=tmpl["address"],
                city=tmpl["city"],
                phone=_pakistani_phone(used_phones),
                email=_bulk_email(f"contact.{tmpl['slug']}"),
                working_hours_start=time(9, 0),
                working_hours_end=time(17, 0),
                working_days="Mon,Tue,Wed,Thu,Fri",
                timezone="Asia/Karachi",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(clinic)
            clinics.append(clinic)

        # --- Doctors ---
        doctors: list[Doctor] = []
        doctor_counter = 0
        for spec in SPECIALIZATIONS:
            count = DOCTORS_PER_SPECIALIZATION[spec]
            for i in range(count):
                doctor_counter += 1
                gender = random.choice(["M", "F"])
                name = _random_name(gender)
                clinic = clinics[doctor_counter % len(clinics)]
                slug = name.lower().replace(" ", ".").replace("dr.", "")
                email = _bulk_email(f"doctor.{slug}.{doctor_counter}")

                user = User(
                    id=uuid.uuid4(),
                    email=email,
                    phone=_pakistani_phone(used_phones),
                    name=_doctor_display_name(name),
                    password_hash=password_hash,
                    user_type="doctor",
                    is_active=True,
                    created_at=now,
                )
                db.add(user)

                fee = Decimal(str(random.randint(15, 35) * 100))  # Rs. 1500–3500
                rating = Decimal(str(round(random.uniform(3.5, 5.0), 2)))
                max_patients = random.randint(15, 25)
                duration = random.choice([15, 30, 45, 60])

                doc = Doctor(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    clinic_id=clinic.id,
                    specialization=spec,
                    qualifications=json.dumps(QUALIFICATIONS_BY_SPEC[spec]),
                    consultation_fee=fee,
                    bio=f"Experienced {spec} serving patients in {clinic.city}.",
                    is_available=True,
                    max_patients_per_day=max_patients,
                    appointment_duration_minutes=duration,
                    languages_spoken=json.dumps(random.choice(LANGUAGE_OPTIONS)),
                    rating=rating,
                    total_appointments=0,
                    created_at=now,
                )
                db.add(doc)
                doctors.append(doc)

                # Schedules for next 30 weekdays
                for day_date in _weekday_dates(today, today + timedelta(days=30)):
                    db.add(
                        DoctorSchedule(
                            id=uuid.uuid4(),
                            doctor_id=doc.id,
                            date=day_date,
                            start_time=time(9, 0),
                            end_time=time(17, 0),
                            break_start=time(13, 0),
                            break_end=time(14, 0),
                            is_holiday=False,
                            max_patients=max_patients,
                        )
                    )

        # --- Receptionists (5–10) ---
        num_receptionists = random.randint(5, 10)
        for i in range(1, num_receptionists + 1):
            name = _random_name(random.choice(["M", "F"]))
            db.add(
                User(
                    id=uuid.uuid4(),
                    email=_bulk_email(f"receptionist.{i}"),
                    phone=_pakistani_phone(used_phones),
                    name=f"{name} (Receptionist)",
                    password_hash=password_hash,
                    user_type="receptionist",
                    is_active=True,
                    created_at=now,
                )
            )

        # --- Patients (100–150) ---
        num_patients = random.randint(100, 150)
        patients: list[Patient] = []
        for i in range(1, num_patients + 1):
            gender = random.choice(["M", "F"])
            name = _random_name(gender)
            age = random.randint(18, 75)
            dob = today - timedelta(days=age * 365 + random.randint(0, 364))

            has_allergies = random.random() < 0.55
            has_conditions = random.random() < 0.45
            allergies = random.sample(ALLERGIES_POOL, k=random.randint(1, 2)) if has_allergies else []
            conditions = random.sample(CONDITIONS_POOL, k=random.randint(1, 2)) if has_conditions else []

            user = User(
                id=uuid.uuid4(),
                email=_bulk_email(f"patient.{i}"),
                phone=_pakistani_phone(used_phones),
                name=name,
                password_hash=password_hash,
                user_type="patient",
                is_active=True,
                created_at=now - timedelta(days=random.randint(1, 365)),
            )
            db.add(user)

            ec_name = _random_name(random.choice(["M", "F"]))
            pat = Patient(
                id=uuid.uuid4(),
                user_id=user.id,
                date_of_birth=dob,
                gender=gender,
                blood_type=random.choice(BLOOD_TYPES),
                allergies=json.dumps(allergies),
                medical_conditions=json.dumps(conditions),
                emergency_contact_name=ec_name,
                emergency_contact_phone=_pakistani_phone(used_phones),
                emergency_contact_relation=random.choice(RELATIONS),
                preferred_notification=random.choice(["whatsapp", "email", "sms"]),
                total_appointments=0,
                total_no_shows=0,
                created_at=user.created_at,
            )
            db.add(pat)
            patients.append(pat)

        db.flush()

        # --- Appointments (300–500) ---
        num_appointments = random.randint(300, 500)
        date_start = today - timedelta(days=60)
        date_end = today + timedelta(days=30)
        weekday_pool = _weekday_dates(date_start, date_end)
        slot_pool = _slot_times(duration=30)

        status_targets = {
            "completed": int(num_appointments * 0.70),
            "scheduled": int(num_appointments * 0.15),
            "cancelled": int(num_appointments * 0.10),
            "no_show": num_appointments
            - int(num_appointments * 0.70)
            - int(num_appointments * 0.15)
            - int(num_appointments * 0.10),
        }

        urgency_pool = (
            ["low"] * int(num_appointments * 0.35)
            + ["normal"] * int(num_appointments * 0.45)
            + ["high"] * int(num_appointments * 0.17)
            + ["critical"] * max(1, int(num_appointments * 0.03))
        )
        random.shuffle(urgency_pool)
        while len(urgency_pool) < num_appointments:
            urgency_pool.append("normal")

        doctor_bookings: dict[uuid.UUID, set[datetime]] = {d.id: set() for d in doctors}
        appointments_created = 0

        past_dates = [d for d in weekday_pool if d < today]
        future_dates = [d for d in weekday_pool if d > today]

        def _slots_for_dates(dates: list[date]) -> list[tuple[Doctor, datetime]]:
            slots: list[tuple[Doctor, datetime]] = []
            for doctor in doctors:
                for day_date in dates:
                    for slot in slot_pool:
                        slots.append((doctor, datetime.combine(day_date, slot)))
            random.shuffle(slots)
            return slots

        past_today_slots = _slots_for_dates(past_dates + [today])
        future_today_slots = _slots_for_dates(future_dates + [today])

        terminal_statuses = (
            ["completed"] * status_targets["completed"]
            + ["cancelled"] * status_targets["cancelled"]
            + ["no_show"] * status_targets["no_show"]
        )
        scheduled_statuses = ["scheduled"] * status_targets["scheduled"]
        random.shuffle(terminal_statuses)
        random.shuffle(scheduled_statuses)

        def _create_from_pool(
            pool: list[tuple[Doctor, datetime]],
            status_list: list[str],
        ) -> None:
            nonlocal appointments_created
            status_idx = 0
            for doctor, appt_dt in pool:
                if status_idx >= len(status_list):
                    break
                if appt_dt in doctor_bookings[doctor.id]:
                    continue
                doctor_bookings[doctor.id].add(appt_dt)
                status = status_list[status_idx]
                status_idx += 1
                patient = random.choice(patients)
                urgency = urgency_pool[appointments_created]
                symptoms = random.choice(SPECIALIZATION_SYMPTOMS[doctor.specialization])

                db.add(
                    Appointment(
                        id=uuid.uuid4(),
                        clinic_id=doctor.clinic_id,
                        doctor_id=doctor.id,
                        patient_id=patient.id,
                        appointment_time=appt_dt,
                        duration_minutes=doctor.appointment_duration_minutes,
                        status=status,
                        appointment_type=random.choice(
                            ["in_person", "in_person", "in_person", "video", "phone"]
                        ),
                        symptoms_reported=symptoms,
                        urgency_level=urgency,
                        notes="Bulk seed appointment." if status == "completed" else None,
                        feedback_score=(
                            random.randint(3, 5)
                            if status == "completed" and random.random() < 0.6
                            else None
                        ),
                        feedback_text=(
                            random.choice(
                                [
                                    "Very professional and thorough consultation.",
                                    "Wait time was reasonable. Good experience.",
                                    "Doctor explained everything clearly.",
                                ]
                            )
                            if status == "completed" and random.random() < 0.4
                            else None
                        ),
                        cancelled_at=(
                            now - timedelta(days=random.randint(1, 30))
                            if status == "cancelled"
                            else None
                        ),
                        created_at=appt_dt - timedelta(days=random.randint(1, 14)),
                    )
                )
                appointments_created += 1

        _create_from_pool(past_today_slots, terminal_statuses)
        _create_from_pool(future_today_slots, scheduled_statuses)

        db.flush()

        # Update aggregate counters on doctors/patients
        for doc in doctors:
            doc.total_appointments = (
                db.query(Appointment)
                .filter(Appointment.doctor_id == doc.id, Appointment.status == "completed")
                .count()
            )
        for pat in patients:
            pat_appts = db.query(Appointment).filter(Appointment.patient_id == pat.id).all()
            pat.total_appointments = sum(1 for a in pat_appts if a.status == "completed")
            pat.total_no_shows = sum(1 for a in pat_appts if a.status == "no_show")

        db.commit()

        # --- Summary & AI triage coverage ---
        spec_counts: dict[str, int] = {}
        for doc in doctors:
            spec_counts[doc.specialization] = spec_counts.get(doc.specialization, 0) + 1

        triage_ok = all(spec_counts.get(spec, 0) >= 2 for spec in AI_TRIAGE_SPECIALIZATIONS)

        print("\n========== Bulk Seed Summary ==========")
        print(f"  Clinics created:       {len(clinics)}")
        print(f"  Doctors created:       {len(doctors)}")
        print(f"  Receptionists created: {num_receptionists}")
        print(f"  Patients created:      {len(patients)}")
        print(f"  Appointments created:  {appointments_created}")
        print("\n  Doctors by specialization:")
        for spec in SPECIALIZATIONS:
            print(f"    {spec}: {spec_counts.get(spec, 0)}")
        print("\n  AI triage specialty coverage (need >= 2 each):")
        for spec in AI_TRIAGE_SPECIALIZATIONS:
            count = spec_counts.get(spec, 0)
            mark = "OK" if count >= 2 else "MISSING"
            print(f"    {spec}: {count} [{mark}]")
        if triage_ok:
            print("\n  AI service can find doctors for every triage-recommended specialization.")
        else:
            print("\n  WARNING: Some AI triage specializations have fewer than 2 doctors!")
        print(f"\n  Bulk user password: {BULK_SEED_PASSWORD}")
        print(f"  Bulk email domain:  @{BULK_SEED_EMAIL_DOMAIN}")
        print("========================================\n")

        return {
            "status": "seeded",
            "clinics": len(clinics),
            "doctors": len(doctors),
            "receptionists": num_receptionists,
            "patients": len(patients),
            "appointments": appointments_created,
            "ai_triage_coverage_ok": triage_ok,
            "specialization_counts": spec_counts,
        }

    except Exception as e:
        db.rollback()
        print(f"Error during bulk seeding: {e}")
        raise
    finally:
        if should_close:
            db.close()
