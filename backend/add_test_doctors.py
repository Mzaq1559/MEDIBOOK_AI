import uuid
import json
from datetime import datetime, date, time, timedelta

from app.database import SessionLocal
from app.models.user import User
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.doctor_schedule import DoctorSchedule
from app.core.security import get_password_hash


db = SessionLocal()

try:
    # 1. Get or create clinic
    clinic = db.query(Clinic).filter(
        Clinic.name == "Prime Care Clinic Taxila"
    ).first()

    if not clinic:
        clinic = Clinic(
            id=uuid.uuid4(),
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
            updated_at=datetime.utcnow(),
        )
        db.add(clinic)
        db.flush()

    print(f"Clinic ready: {clinic.name}")

    # 2. Test doctors
    doctors_data = [
        {
            "name": "Dr. Ahmed Khan",
            "email": "ahmed.khan@primecare.pk",
            "phone": "03009876541",
            "specialization": "Cardiologist",
            "qualifications": ["MBBS", "MD Cardiology", "FCPS"],
            "fee": 2500.00,
            "bio": "Senior Interventional Cardiologist with 12+ years experience.",
            "max_patients": 20,
            "languages": ["Urdu", "English"],
            "rating": 4.8,
        },
        {
            "name": "Dr. Fatima Malik",
            "email": "fatima.malik@primecare.pk",
            "phone": "03009876542",
            "specialization": "Dermatologist",
            "qualifications": ["MBBS", "FCPS Dermatology"],
            "fee": 2000.00,
            "bio": "Consultant Dermatologist and aesthetic medicine specialist.",
            "max_patients": 25,
            "languages": ["Urdu", "English", "Punjabi"],
            "rating": 4.7,
        },
        {
            "name": "Dr. Zain Ali",
            "email": "zain.ali@primecare.pk",
            "phone": "03009876543",
            "specialization": "ENT Specialist",
            "qualifications": ["MBBS", "MS Otolaryngology"],
            "fee": 1800.00,
            "bio": "Expert in ear, nose, throat diagnostics and treatment.",
            "max_patients": 20,
            "languages": ["Urdu", "English"],
            "rating": 4.6,
        },
    ]

    for data in doctors_data:

        # Find existing doctor user or create one
        user = db.query(User).filter(
            User.email == data["email"]
        ).first()

        if not user:
            user = User(
                id=uuid.uuid4(),
                email=data["email"],
                phone=data["phone"],
                name=data["name"],
                password_hash=get_password_hash("DoctorPass123!"),
                user_type="doctor",
                is_active=True,
                created_at=datetime.utcnow(),
            )
            db.add(user)
            db.flush()

        # Find existing doctor profile or create one
        doctor = db.query(Doctor).filter(
            Doctor.user_id == user.id
        ).first()

        if not doctor:
            doctor = Doctor(
                id=uuid.uuid4(),
                user_id=user.id,
                clinic_id=clinic.id,
                specialization=data["specialization"],
                qualifications=json.dumps(data["qualifications"]),
                consultation_fee=data["fee"],
                bio=data["bio"],
                is_available=True,
                max_patients_per_day=data["max_patients"],
                appointment_duration_minutes=30,
                languages_spoken=json.dumps(data["languages"]),
                rating=data["rating"],
                total_appointments=0,
                created_at=datetime.utcnow(),
            )
            db.add(doctor)
            db.flush()

        # 3. Create schedules for next 7 days
        for offset in range(7):
            schedule_date = date.today() + timedelta(days=offset)

            existing_schedule = db.query(DoctorSchedule).filter(
                DoctorSchedule.doctor_id == doctor.id,
                DoctorSchedule.date == schedule_date
            ).first()

            if not existing_schedule:
                schedule = DoctorSchedule(
                    id=uuid.uuid4(),
                    doctor_id=doctor.id,
                    date=schedule_date,
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                    break_start=time(13, 0),
                    break_end=time(14, 0),
                    is_holiday=False,
                    max_patients=data["max_patients"],
                )
                db.add(schedule)

        print(f"Doctor ready: {data['name']}")

    db.commit()

    print("\nSUCCESS!")
    print("Clinic: Prime Care Clinic Taxila")
    print("Doctors: 3")
    print("Schedules: next 7 days")

except Exception as e:
    db.rollback()
    print("ERROR:", e)
    raise

finally:
    db.close()