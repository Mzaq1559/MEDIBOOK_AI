import pytest
import uuid
import json
from datetime import datetime, date, time, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.doctor_schedule import DoctorSchedule
from app.models.clinic_holiday import ClinicHoliday
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.core.security import get_password_hash
from app.core.auth import create_access_token

# In-memory SQLite for high-speed isolated tests
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seed_data(db_session):
    """Seed foundational test data (Clinic, Admin, Receptionist, Doctor, Patient)."""
    # 1. Clinic
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
        is_active=True
    )
    db_session.add(clinic)

    # 2. Admin User
    admin_user = User(
        id=uuid.uuid4(),
        email="admin@primecare.pk",
        phone="03009990001",
        name="Admin User",
        password_hash=get_password_hash("AdminPass123!"),
        user_type="admin",
        is_active=True
    )
    db_session.add(admin_user)

    # 3. Receptionist User
    recep_user = User(
        id=uuid.uuid4(),
        email="receptionist@primecare.pk",
        phone="03009990002",
        name="Receptionist Sana",
        password_hash=get_password_hash("RecepPass123!"),
        user_type="receptionist",
        is_active=True
    )
    db_session.add(recep_user)

    # 4. Doctor User & Doctor Profile
    doc_user = User(
        id=uuid.uuid4(),
        email="ahmed.khan@primecare.pk",
        phone="03009876541",
        name="Dr. Ahmed Khan",
        password_hash=get_password_hash("DoctorPass123!"),
        user_type="doctor",
        is_active=True
    )
    db_session.add(doc_user)

    doctor = Doctor(
        id=uuid.uuid4(),
        user_id=doc_user.id,
        clinic_id=clinic.id,
        specialization="Cardiologist",
        qualifications=json.dumps(["MBBS", "MD Cardiology"]),
        consultation_fee=2500.00,
        bio="Cardiology specialist",
        is_available=True,
        max_patients_per_day=20,
        appointment_duration_minutes=30,
        languages_spoken=json.dumps(["Urdu", "English"]),
        rating=4.8
    )
    db_session.add(doctor)

    # 5. Patient User & Patient Profile
    pat_user = User(
        id=uuid.uuid4(),
        email="ali.khan@example.com",
        phone="03001234567",
        name="Ali Khan",
        password_hash=get_password_hash("PatientPass123!"),
        user_type="patient",
        is_active=True
    )
    db_session.add(pat_user)

    patient = Patient(
        id=uuid.uuid4(),
        user_id=pat_user.id,
        date_of_birth=date(1990, 5, 15),
        gender="M",
        blood_type="O+",
        allergies=json.dumps(["Penicillin"]),
        medical_conditions=json.dumps(["Hypertension"]),
        emergency_contact_name="Muhammad Hassan",
        emergency_contact_phone="03001111111",
        emergency_contact_relation="Brother",
        preferred_notification="whatsapp"
    )
    db_session.add(patient)

    # 6. Second Patient for isolation testing
    pat2_user = User(
        id=uuid.uuid4(),
        email="sara.ahmed@example.com",
        phone="03001234568",
        name="Sara Ahmed",
        password_hash=get_password_hash("PatientPass123!"),
        user_type="patient",
        is_active=True
    )
    db_session.add(pat2_user)

    patient2 = Patient(
        id=uuid.uuid4(),
        user_id=pat2_user.id,
        date_of_birth=date(1995, 8, 20),
        gender="F",
        blood_type="B+",
        allergies=json.dumps(["Peanuts"]),
        medical_conditions=json.dumps(["Asthma"]),
        emergency_contact_name="Tariq Ahmed",
        emergency_contact_phone="03002222222",
        emergency_contact_relation="Father",
        preferred_notification="whatsapp"
    )
    db_session.add(patient2)

    db_session.commit()

    # Create auth tokens
    admin_token = create_access_token(admin_user.id, admin_user.email, admin_user.user_type)
    doctor_token = create_access_token(doc_user.id, doc_user.email, doc_user.user_type)
    patient_token = create_access_token(pat_user.id, pat_user.email, pat_user.user_type)
    patient2_token = create_access_token(pat2_user.id, pat2_user.email, pat2_user.user_type)
    recep_token = create_access_token(recep_user.id, recep_user.email, recep_user.user_type)

    return {
        "clinic": clinic,
        "admin_user": admin_user,
        "recep_user": recep_user,
        "doc_user": doc_user,
        "doctor": doctor,
        "pat_user": pat_user,
        "patient": patient,
        "pat2_user": pat2_user,
        "patient2": patient2,
        "admin_headers": {"Authorization": f"Bearer {admin_token}"},
        "doctor_headers": {"Authorization": f"Bearer {doctor_token}"},
        "patient_headers": {"Authorization": f"Bearer {patient_token}"},
        "patient2_headers": {"Authorization": f"Bearer {patient2_token}"},
        "recep_headers": {"Authorization": f"Bearer {recep_token}"},
    }
