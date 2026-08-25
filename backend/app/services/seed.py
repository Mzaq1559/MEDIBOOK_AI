import uuid
import json
from datetime import datetime, date, time, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.doctor_schedule import DoctorSchedule
from app.models.clinic_holiday import ClinicHoliday
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.core.security import get_password_hash

TEST_ADMIN_EMAIL = "admin@medibook.com"
TEST_ADMIN_PASSWORD = "Admin@123"
TEST_ADMIN_NAME = "Admin User"


def seed_test_admin(db: Optional[Session] = None) -> dict:
    """Ensure the standard test admin account exists (idempotent)."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        target_bind = db.get_bind() if db else engine
        Base.metadata.create_all(bind=target_bind)

        existing = (
            db.query(User)
            .filter(User.email == TEST_ADMIN_EMAIL, User.deleted_at.is_(None))
            .first()
        )
        if existing:
            return {
                "status": "already_exists",
                "user_id": str(existing.id),
                "email": existing.email,
            }

        admin_user = User(
            id=uuid.uuid4(),
            email=TEST_ADMIN_EMAIL,
            name=TEST_ADMIN_NAME,
            password_hash=get_password_hash(TEST_ADMIN_PASSWORD),
            user_type="admin",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db.add(admin_user)
        db.commit()
        print(f"--> Test admin created: {TEST_ADMIN_EMAIL}")
        return {
            "status": "created",
            "user_id": str(admin_user.id),
            "email": admin_user.email,
        }
    except Exception as e:
        db.rollback()
        print(f"Error seeding test admin: {str(e)}")
        raise e
    finally:
        if should_close:
            db.close()


def seed_database(db: Optional[Session] = None) -> dict:
    """Populate database with complete, realistic MediBook demo data."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        # Create all tables if not created using the active bind
        target_bind = db.get_bind() if db else engine
        Base.metadata.create_all(bind=target_bind)

        # Check if already seeded
        existing_clinic = db.query(Clinic).filter(Clinic.name == "Prime Care Clinic Taxila").first()
        if existing_clinic:
            return {"status": "already_seeded", "clinic_id": str(existing_clinic.id)}

        print("--> Seeding MediBook database...")

        # 1. Create Clinic
        clinic_id = uuid.uuid4()
        clinic = Clinic(
            id=clinic_id,
            name="Prime Care Clinic Taxila",
            address="Ground Floor, ABC Plaza, Taxila",
            city="Taxila",
            phone="03005551234",
            email="contact@primecare.pk",
            working_hours_start=time(9, 0),
            working_hours_end=time(17, 0),
            working_days="Mon,Tue,Wed,Thu,Fri",
            timezone="Asia/Karachi",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(clinic)

        # 2. Clinic Holidays
        h1 = ClinicHoliday(
            id=uuid.uuid4(),
            clinic_id=clinic_id,
            holiday_date=date(2026, 9, 1),
            holiday_name="Eid ul-Adha",
            reason="National Islamic Holiday"
        )
        h2 = ClinicHoliday(
            id=uuid.uuid4(),
            clinic_id=clinic_id,
            holiday_date=date(2026, 8, 14),
            holiday_name="Independence Day",
            reason="Pakistan Independence Day"
        )
        db.add_all([h1, h2])

        # 3. Create Admin User
        admin_id = uuid.uuid4()
        admin_user = User(
            id=admin_id,
            email="admin@primecare.pk",
            phone="03009990001",
            name="Muhammad Bilal (Admin)",
            password_hash=get_password_hash("AdminPass123!"),
            user_type="admin",
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(admin_user)

        # 4. Create Receptionist User
        receptionist_id = uuid.uuid4()
        receptionist_user = User(
            id=receptionist_id,
            email="receptionist@primecare.pk",
            phone="03009990002",
            name="Sana Tariq (Receptionist)",
            password_hash=get_password_hash("RecepPass123!"),
            user_type="receptionist",
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(receptionist_user)

        # 5. Create Doctors
        doctors_data = [
            {
                "name": "Dr. Ahmed Khan",
                "email": "ahmed.khan@primecare.pk",
                "phone": "03009876541",
                "specialization": "Cardiologist",
                "qualifications": ["MBBS", "MD Cardiology", "FCPS"],
                "fee": 2500.00,
                "bio": "Senior Interventional Cardiologist with 12+ years experience in cardiovascular care.",
                "duration": 30,
                "max_patients": 20,
                "languages": ["Urdu", "English"],
                "rating": 4.8
            },
            {
                "name": "Dr. Fatima Malik",
                "email": "fatima.malik@primecare.pk",
                "phone": "03009876542",
                "specialization": "Dermatologist",
                "qualifications": ["MBBS", "FCPS Dermatology"],
                "fee": 2000.00,
                "bio": "Consultant Dermatologist and aesthetic medicine specialist.",
                "duration": 30,
                "max_patients": 25,
                "languages": ["Urdu", "English", "Punjabi"],
                "rating": 4.7
            },
            {
                "name": "Dr. Zain Ali",
                "email": "zain.ali@primecare.pk",
                "phone": "03009876543",
                "specialization": "ENT Specialist",
                "qualifications": ["MBBS", "MS Otolaryngology"],
                "fee": 1800.00,
                "bio": "Expert in ear, nose, throat diagnostics, sinus relief, and head & neck surgery.",
                "duration": 30,
                "max_patients": 20,
                "languages": ["Urdu", "English"],
                "rating": 4.6
            }
        ]

        created_doctors = []
        for d_info in doctors_data:
            u_id = uuid.uuid4()
            d_user = User(
                id=u_id,
                email=d_info["email"],
                phone=d_info["phone"],
                name=d_info["name"],
                password_hash=get_password_hash("DoctorPass123!"),
                user_type="doctor",
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.add(d_user)

            doc_id = uuid.uuid4()
            doc = Doctor(
                id=doc_id,
                user_id=u_id,
                clinic_id=clinic_id,
                specialization=d_info["specialization"],
                qualifications=json.dumps(d_info["qualifications"]),
                consultation_fee=d_info["fee"],
                bio=d_info["bio"],
                is_available=True,
                max_patients_per_day=d_info["max_patients"],
                appointment_duration_minutes=d_info["duration"],
                languages_spoken=json.dumps(d_info["languages"]),
                rating=d_info["rating"],
                total_appointments=15,
                created_at=datetime.utcnow()
            )
            db.add(doc)
            created_doctors.append(doc)

            # Doctor Schedule with Lunch Break
            for offset in range(7):
                day_date = date.today() + timedelta(days=offset)
                sched = DoctorSchedule(
                    id=uuid.uuid4(),
                    doctor_id=doc_id,
                    date=day_date,
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                    break_start=time(13, 0),
                    break_end=time(14, 0),
                    is_holiday=False,
                    max_patients=d_info["max_patients"]
                )
                db.add(sched)

        # 6. Create Patients
        patients_data = [
            {
                "name": "Ali Khan",
                "email": "ali.khan@example.com",
                "phone": "03001234567",
                "dob": date(1990, 5, 15),
                "gender": "M",
                "blood": "O+",
                "allergies": ["Penicillin"],
                "conditions": ["Hypertension"],
                "ec_name": "Muhammad Hassan",
                "ec_phone": "03001111111",
                "ec_relation": "Brother"
            },
            {
                "name": "Sara Ahmed",
                "email": "sara.ahmed@example.com",
                "phone": "03001234568",
                "dob": date(1995, 8, 20),
                "gender": "F",
                "blood": "B+",
                "allergies": ["Peanuts"],
                "conditions": ["Asthma"],
                "ec_name": "Tariq Ahmed",
                "ec_phone": "03002222222",
                "ec_relation": "Father"
            },
            {
                "name": "Usman Tariq",
                "email": "usman.tariq@example.com",
                "phone": "03001234569",
                "dob": date(1988, 12, 10),
                "gender": "M",
                "blood": "A+",
                "allergies": [],
                "conditions": ["Diabetes"],
                "ec_name": "Ayesha Tariq",
                "ec_phone": "03003333333",
                "ec_relation": "Wife"
            }
        ]

        created_patients = []
        for p_info in patients_data:
            u_id = uuid.uuid4()
            p_user = User(
                id=u_id,
                email=p_info["email"],
                phone=p_info["phone"],
                name=p_info["name"],
                password_hash=get_password_hash("PatientPass123!"),
                user_type="patient",
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.add(p_user)

            pat_id = uuid.uuid4()
            pat = Patient(
                id=pat_id,
                user_id=u_id,
                date_of_birth=p_info["dob"],
                gender=p_info["gender"],
                blood_type=p_info["blood"],
                allergies=json.dumps(p_info["allergies"]),
                medical_conditions=json.dumps(p_info["conditions"]),
                emergency_contact_name=p_info["ec_name"],
                emergency_contact_phone=p_info["ec_phone"],
                emergency_contact_relation=p_info["ec_relation"],
                preferred_notification="whatsapp",
                total_appointments=3,
                total_no_shows=0,
                created_at=datetime.utcnow()
            )
            db.add(pat)
            created_patients.append(pat)

        # 7. Sample Appointments
        today_date = date.today()
        # Find next weekday if today is weekend
        while today_date.weekday() >= 5:
            today_date += timedelta(days=1)

        # Appointment 1: Completed earlier today
        appt1 = Appointment(
            id=uuid.uuid4(),
            clinic_id=clinic_id,
            doctor_id=created_doctors[0].id,
            patient_id=created_patients[0].id,
            appointment_time=datetime.combine(today_date, time(9, 30)),
            duration_minutes=30,
            status="completed",
            appointment_type="in_person",
            symptoms_reported="Chest tightness and mild palpitation after exertion.",
            urgency_level="high",
            notes="Blood pressure normal. Recommended ECG and lipid profile.",
            feedback_score=5,
            feedback_text="Dr. Ahmed explained everything very thoroughly. Excellent care!",
            created_at=datetime.utcnow() - timedelta(days=1)
        )
        db.add(appt1)

        # Appointment 2: Scheduled today afternoon
        appt2 = Appointment(
            id=uuid.uuid4(),
            clinic_id=clinic_id,
            doctor_id=created_doctors[0].id,
            patient_id=created_patients[1].id,
            appointment_time=datetime.combine(today_date, time(14, 0)),
            duration_minutes=30,
            status="scheduled",
            appointment_type="in_person",
            symptoms_reported="Persistent dry cough and shortness of breath.",
            urgency_level="normal",
            created_at=datetime.utcnow() - timedelta(days=1)
        )
        db.add(appt2)

        # Appointment 3: Scheduled with Dermatologist
        appt3 = Appointment(
            id=uuid.uuid4(),
            clinic_id=clinic_id,
            doctor_id=created_doctors[1].id,
            patient_id=created_patients[2].id,
            appointment_time=datetime.combine(today_date, time(11, 0)),
            duration_minutes=30,
            status="scheduled",
            appointment_type="in_person",
            symptoms_reported="Skin rash and redness on forearms.",
            urgency_level="low",
            created_at=datetime.utcnow()
        )
        db.add(appt3)

        db.commit()
        print("--> Seeding completed successfully!")
        return {
            "status": "seeded",
            "clinic_id": str(clinic_id),
            "doctors_count": len(created_doctors),
            "patients_count": len(created_patients)
        }

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {str(e)}")
        raise e
    finally:
        if should_close:
            db.close()


if __name__ == "__main__":
    import sys

    from app.services.bulk_seed import seed_bulk_test_data

    if len(sys.argv) > 1 and sys.argv[1] == "--test-admin":
        seed_test_admin()
    elif len(sys.argv) > 1 and sys.argv[1] == "--bulk-test-data":
        seed_bulk_test_data()
    else:
        seed_database()
