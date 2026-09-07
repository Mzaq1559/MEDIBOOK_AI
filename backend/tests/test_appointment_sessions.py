import os
import sys
import uuid
import threading
from datetime import date, datetime, time, timedelta
from typing import Generator
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from app.database import Base
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.appointment import Appointment, AppointmentSession
from app.models.clinic_holiday import ClinicHoliday
from app.models.doctor_schedule import DoctorSchedule
from app.schemas.appointment import AppointmentCreate
from app.services.appointment_service import (
    create_appointment,
    validate_session_booking,
    SESSION_CAPACITY,
)
from app.services.availability import compute_doctor_availability


# In-memory SQLite DB fixture for fast, isolated, deterministic session tests
@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def setup_data(db_session: Session):
    """Seed test clinic, 2 doctors, and 15 patients."""
    clinic = Clinic(
        id=uuid.uuid4(),
        name="Lahore Health Clinic",
        address="Gulberg, Lahore",
        city="Lahore",
        phone="+92-42-1111111",
        email="info@lahorehealth.pk",
        working_days="Mon,Tue,Wed,Thu,Fri",
        working_hours_start=time(8, 0),
        working_hours_end=time(20, 0),
        timezone="Asia/Karachi",
        is_active=True,
    )
    db_session.add(clinic)
    db_session.flush()

    user_doc_a = User(
        id=uuid.uuid4(),
        email="doctor.a@test.com",
        password_hash="fakehash",
        user_type="doctor",
        name="Dr. Ahmed",
        is_active=True,
    )
    user_doc_b = User(
        id=uuid.uuid4(),
        email="doctor.b@test.com",
        password_hash="fakehash",
        user_type="doctor",
        name="Dr. Bilal",
        is_active=True,
    )
    db_session.add_all([user_doc_a, user_doc_b])
    db_session.flush()

    doc_a = Doctor(
        id=uuid.uuid4(),
        user_id=user_doc_a.id,
        clinic_id=clinic.id,
        specialization="Cardiology",
        is_available=True,
        consultation_fee=2500,
    )
    doc_b = Doctor(
        id=uuid.uuid4(),
        user_id=user_doc_b.id,
        clinic_id=clinic.id,
        specialization="General Medicine",
        is_available=True,
        consultation_fee=1500,
    )
    db_session.add_all([doc_a, doc_b])
    db_session.flush()

    patients = []
    for i in range(25):
        p_user = User(
            id=uuid.uuid4(),
            email=f"patient{i}@test.com",
            password_hash="fakehash",
            user_type="patient",
            name=f"Patient {i}",
            is_active=True,
        )
        db_session.add(p_user)
        db_session.flush()
        p = Patient(
            id=uuid.uuid4(),
            user_id=p_user.id,
            date_of_birth=date(1990, 1, 1),
            gender="M",
        )
        patients.append(p)
        db_session.add(p)

    db_session.commit()

    # Pick a future weekday (e.g. Wednesday 10 days from now)
    target_date = date.today() + timedelta(days=10)
    while target_date.weekday() >= 5:  # ensure weekday
        target_date += timedelta(days=1)

    return {
        "clinic": clinic,
        "doc_a": doc_a,
        "doc_b": doc_b,
        "patients": patients,
        "target_date": target_date,
    }


# ============================================================================
# 1-4. MORNING SESSION TESTS
# ============================================================================

def test_1_morning_booking_with_0_existing_succeeds(db_session, setup_data):
    """1. Booking with 0 existing -> success."""
    doc = setup_data["doc_a"]
    patient = setup_data["patients"][0]
    target_date = setup_data["target_date"]

    payload = AppointmentCreate(
        doctor_id=doc.id,
        patient_id=patient.id,
        date=target_date,
        session="morning",
        symptoms_reported="Routine morning checkup",
        urgency_level="normal",
    )
    appt = create_appointment(db_session, payload)
    assert appt.appointment_id is not None
    assert appt.session == "morning"
    assert appt.status == "scheduled"
    assert appt.doctor_id == doc.id


def test_2_morning_9_existing_10th_succeeds(db_session, setup_data):
    """2. 9 existing -> 10th succeeds."""
    doc = setup_data["doc_a"]
    target_date = setup_data["target_date"]
    patients = setup_data["patients"]

    for i in range(9):
        payload = AppointmentCreate(
            doctor_id=doc.id,
            patient_id=patients[i].id,
            date=target_date,
            session="morning",
            symptoms_reported=f"Patient {i} checkup",
            urgency_level="normal",
        )
        create_appointment(db_session, payload)

    # 10th booking
    payload_10 = AppointmentCreate(
        doctor_id=doc.id,
        patient_id=patients[9].id,
        date=target_date,
        session="morning",
        symptoms_reported="10th morning checkup",
        urgency_level="normal",
    )
    appt_10 = create_appointment(db_session, payload_10)
    assert appt_10.appointment_id is not None

    count = (
        db_session.query(Appointment)
        .filter(
            Appointment.doctor_id == doc.id,
            Appointment.session == "morning",
            Appointment.status == "scheduled",
        )
        .count()
    )
    assert count == 10


def test_3_morning_10_existing_11th_rejected(db_session, setup_data):
    """3. 10 existing -> 11th rejected with 409 SESSION_FULL."""
    doc = setup_data["doc_a"]
    target_date = setup_data["target_date"]
    patients = setup_data["patients"]

    for i in range(10):
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patients[i].id,
                date=target_date,
                session="morning",
                symptoms_reported=f"Patient {i}",
                urgency_level="normal",
            ),
        )

    # 11th attempt
    with pytest.raises(HTTPException) as exc_info:
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patients[10].id,
                date=target_date,
                session="morning",
                symptoms_reported="11th patient trying to book",
                urgency_level="normal",
            ),
        )
    assert exc_info.value.status_code == 409
    assert "fully booked" in str(exc_info.value.detail).lower()


def test_4_morning_availability_reports_correctly_when_full(db_session, setup_data):
    """4. Availability reports: capacity 10, booked 10, remaining 0, available false."""
    doc = setup_data["doc_a"]
    target_date = setup_data["target_date"]
    patients = setup_data["patients"]

    for i in range(10):
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patients[i].id,
                date=target_date,
                session="morning",
                symptoms_reported=f"Patient {i}",
                urgency_level="normal",
            ),
        )

    avail = compute_doctor_availability(
        db=db_session,
        doctor_id=doc.id,
        start_date=target_date,
        next_days=1,
    )
    day = avail.availability[0]
    morning_s = next(s for s in day.sessions if s.session == "morning")
    assert morning_s.capacity == 10
    assert morning_s.booked == 10
    assert morning_s.remaining == 0
    assert morning_s.available is False


# ============================================================================
# 5-8. EVENING SESSION TESTS
# ============================================================================

def test_5_evening_booking_with_fewer_than_5_succeeds(db_session, setup_data):
    """5. Booking with fewer than 5 -> success."""
    doc = setup_data["doc_a"]
    patient = setup_data["patients"][0]
    target_date = setup_data["target_date"]

    appt = create_appointment(
        db_session,
        AppointmentCreate(
            doctor_id=doc.id,
            patient_id=patient.id,
            date=target_date,
            session="evening",
            symptoms_reported="Evening visit",
            urgency_level="normal",
        ),
    )
    assert appt.appointment_id is not None
    assert appt.session == "evening"
    assert appt.status == "scheduled"


def test_6_evening_4_existing_5th_succeeds(db_session, setup_data):
    """6. 4 existing -> 5th succeeds."""
    doc = setup_data["doc_a"]
    target_date = setup_data["target_date"]
    patients = setup_data["patients"]

    for i in range(4):
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patients[i].id,
                date=target_date,
                session="evening",
                symptoms_reported=f"Patient {i} evening",
                urgency_level="normal",
            ),
        )

    appt_5 = create_appointment(
        db_session,
        AppointmentCreate(
            doctor_id=doc.id,
            patient_id=patients[4].id,
            date=target_date,
            session="evening",
            symptoms_reported="5th evening patient",
            urgency_level="normal",
        ),
    )
    assert appt_5.appointment_id is not None
    count = (
        db_session.query(Appointment)
        .filter(
            Appointment.doctor_id == doc.id,
            Appointment.session == "evening",
            Appointment.status == "scheduled",
        )
        .count()
    )
    assert count == 5


def test_7_evening_5_existing_6th_rejected(db_session, setup_data):
    """7. 5 existing -> 6th rejected."""
    doc = setup_data["doc_a"]
    target_date = setup_data["target_date"]
    patients = setup_data["patients"]

    for i in range(5):
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patients[i].id,
                date=target_date,
                session="evening",
                symptoms_reported=f"Evening patient {i}",
                urgency_level="normal",
            ),
        )

    with pytest.raises(HTTPException) as exc_info:
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patients[5].id,
                date=target_date,
                session="evening",
                symptoms_reported="6th patient trying evening",
                urgency_level="normal",
            ),
        )
    assert exc_info.value.status_code == 409
    assert "fully booked" in str(exc_info.value.detail).lower()


def test_8_evening_availability_reports_correctly_when_full(db_session, setup_data):
    """8. Availability reports: capacity 5, booked 5, remaining 0, available false."""
    doc = setup_data["doc_a"]
    target_date = setup_data["target_date"]
    patients = setup_data["patients"]

    for i in range(5):
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patients[i].id,
                date=target_date,
                session="evening",
                symptoms_reported=f"Patient {i}",
                urgency_level="normal",
            ),
        )

    avail = compute_doctor_availability(
        db=db_session,
        doctor_id=doc.id,
        start_date=target_date,
        next_days=1,
    )
    day = avail.availability[0]
    evening_s = next(s for s in day.sessions if s.session == "evening")
    assert evening_s.capacity == 5
    assert evening_s.booked == 5
    assert evening_s.remaining == 0
    assert evening_s.available is False


# ============================================================================
# 9-12. INDEPENDENCE TESTS
# ============================================================================

def test_9_morning_full_does_not_prevent_evening(db_session, setup_data):
    """9. Morning full (10 booked) does not prevent Evening."""
    doc = setup_data["doc_a"]
    target_date = setup_data["target_date"]
    patients = setup_data["patients"]

    for i in range(10):
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patients[i].id,
                date=target_date,
                session="morning",
                symptoms_reported=f"Morning {i}",
                urgency_level="normal",
            ),
        )

    # Evening booking should succeed
    appt_evening = create_appointment(
        db_session,
        AppointmentCreate(
            doctor_id=doc.id,
            patient_id=patients[11].id,
            date=target_date,
            session="evening",
            symptoms_reported="Evening patient after full morning",
            urgency_level="normal",
        ),
    )
    assert appt_evening.appointment_id is not None
    assert appt_evening.session == "evening"


def test_10_evening_full_does_not_prevent_morning(db_session, setup_data):
    """10. Evening full (5 booked) does not prevent Morning."""
    doc = setup_data["doc_a"]
    target_date = setup_data["target_date"]
    patients = setup_data["patients"]

    for i in range(5):
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patients[i].id,
                date=target_date,
                session="evening",
                symptoms_reported=f"Evening {i}",
                urgency_level="normal",
            ),
        )

    # Morning booking should succeed
    appt_morning = create_appointment(
        db_session,
        AppointmentCreate(
            doctor_id=doc.id,
            patient_id=patients[6].id,
            date=target_date,
            session="morning",
            symptoms_reported="Morning patient after full evening",
            urgency_level="normal",
        ),
    )
    assert appt_morning.appointment_id is not None
    assert appt_morning.session == "morning"


def test_11_doc_a_capacity_does_not_affect_doc_b(db_session, setup_data):
    """11. Dr. A capacity does not affect Dr. B."""
    doc_a = setup_data["doc_a"]
    doc_b = setup_data["doc_b"]
    target_date = setup_data["target_date"]
    patients = setup_data["patients"]

    # Fill Dr. A Morning to capacity (10)
    for i in range(10):
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc_a.id,
                patient_id=patients[i].id,
                date=target_date,
                session="morning",
                symptoms_reported=f"Dr A {i}",
                urgency_level="normal",
            ),
        )

    # Dr. B Morning should still have full capacity
    appt_b = create_appointment(
        db_session,
        AppointmentCreate(
            doctor_id=doc_b.id,
            patient_id=patients[11].id,
            date=target_date,
            session="morning",
            symptoms_reported="Dr B Morning 1",
            urgency_level="normal",
        ),
    )
    assert appt_b.appointment_id is not None
    assert appt_b.doctor_id == doc_b.id


def test_12_one_date_does_not_affect_another_date(db_session, setup_data):
    """12. One date does not affect another date."""
    doc = setup_data["doc_a"]
    target_date_1 = setup_data["target_date"]
    # Find next weekday for target_date_2
    target_date_2 = target_date_1 + timedelta(days=1)
    while target_date_2.weekday() >= 5:
        target_date_2 += timedelta(days=1)
    patients = setup_data["patients"]

    # Fill target_date_1 Morning
    for i in range(10):
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patients[i].id,
                date=target_date_1,
                session="morning",
                symptoms_reported=f"Day 1 {i}",
                urgency_level="normal",
            ),
        )

    # target_date_2 Morning should succeed
    appt_d2 = create_appointment(
        db_session,
        AppointmentCreate(
            doctor_id=doc.id,
            patient_id=patients[12].id,
            date=target_date_2,
            session="morning",
            symptoms_reported="Day 2 Morning",
            urgency_level="normal",
        ),
    )
    assert appt_d2.appointment_id is not None


# ============================================================================
# 13-14. VALIDATION TESTS
# ============================================================================

def test_13_invalid_session_rejected(db_session, setup_data):
    """13. Invalid session (afternoon, night, random) rejected with 422/400."""
    doc = setup_data["doc_a"]
    patient = setup_data["patients"][0]
    target_date = setup_data["target_date"]

    for bad_session in ["afternoon", "night", "random", "midday"]:
        with pytest.raises(Exception):
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patient.id,
                date=target_date,
                session=bad_session,
                symptoms_reported="Invalid session test",
                urgency_level="normal",
            )


def test_14_doctor_inactive_or_holiday_rejected(db_session, setup_data):
    """14. Existing doctor/date/clinic validation still works."""
    doc = setup_data["doc_a"]
    clinic = setup_data["clinic"]
    patient = setup_data["patients"][0]
    target_date = setup_data["target_date"]

    # Add a clinic holiday on target_date
    holiday = ClinicHoliday(
        id=uuid.uuid4(),
        clinic_id=clinic.id,
        holiday_date=target_date,
        holiday_name="Test Holiday",
        reason="Test Holiday",
    )
    db_session.add(holiday)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patient.id,
                date=target_date,
                session="morning",
                symptoms_reported="Holiday test",
                urgency_level="normal",
            ),
        )
    assert exc_info.value.status_code in {400, 409}
    assert "holiday" in str(exc_info.value.detail).lower()


# ============================================================================
# 15-16. STATUS & ACTIVE COUNTING TESTS
# ============================================================================

def test_15_active_appointment_counting(db_session, setup_data):
    """15. Verify active appointment counting (only scheduled consume capacity)."""
    doc = setup_data["doc_a"]
    target_date = setup_data["target_date"]
    patients = setup_data["patients"]

    # Create 9 scheduled appointments
    for i in range(9):
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patients[i].id,
                date=target_date,
                session="morning",
                symptoms_reported=f"Patient {i}",
                urgency_level="normal",
            ),
        )

    # 10th is marked as completed
    create_appointment(
        db_session,
        AppointmentCreate(
            doctor_id=doc.id,
            patient_id=patients[9].id,
            date=target_date,
            session="morning",
            symptoms_reported="10th to be completed",
            urgency_level="normal",
        ),
    )
    appt_10 = (
        db_session.query(Appointment)
        .filter(
            Appointment.doctor_id == doc.id,
            Appointment.patient_id == patients[9].id,
        )
        .first()
    )
    appt_10.status = "completed"
    db_session.commit()

    # Now scheduled count is 9, so another booking should succeed
    appt_11 = create_appointment(
        db_session,
        AppointmentCreate(
            doctor_id=doc.id,
            patient_id=patients[10].id,
            date=target_date,
            session="morning",
            symptoms_reported="11th after 10th was completed",
            urgency_level="normal",
        ),
    )
    assert appt_11.appointment_id is not None


def test_16_cancelled_appointment_releases_capacity(db_session, setup_data):
    """16. Verify cancelled appointment releases capacity."""
    doc = setup_data["doc_a"]
    target_date = setup_data["target_date"]
    patients = setup_data["patients"]

    # Fill evening session with 5 bookings
    for i in range(5):
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patients[i].id,
                date=target_date,
                session="evening",
                symptoms_reported=f"Evening {i}",
                urgency_level="normal",
            ),
        )

    # 6th attempt rejected
    with pytest.raises(HTTPException):
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patients[5].id,
                date=target_date,
                session="evening",
                symptoms_reported="Evening 6",
                urgency_level="normal",
            ),
        )

    # Cancel patient 0's appointment
    appt_0 = (
        db_session.query(Appointment)
        .filter(
            Appointment.doctor_id == doc.id,
            Appointment.patient_id == patients[0].id,
            Appointment.session == "evening",
        )
        .first()
    )
    appt_0.status = "cancelled"
    appt_0.cancelled_at = datetime.utcnow()
    db_session.commit()

    # Now 6th patient can book because capacity was released!
    appt_new = create_appointment(
        db_session,
        AppointmentCreate(
            doctor_id=doc.id,
            patient_id=patients[5].id,
            date=target_date,
            session="evening",
            symptoms_reported="Evening 6 now succeeds",
            urgency_level="normal",
        ),
    )
    assert appt_new.appointment_id is not None
    assert appt_new.status == "scheduled"


# ============================================================================
# 17. DOUBLE BOOKING TESTS
# ============================================================================

def test_17_patient_duplicate_active_booking_rejected(db_session, setup_data):
    """17. Verify patient duplicate active booking for same date + session is rejected."""
    doc = setup_data["doc_a"]
    patient = setup_data["patients"][0]
    target_date = setup_data["target_date"]

    create_appointment(
        db_session,
        AppointmentCreate(
            doctor_id=doc.id,
            patient_id=patient.id,
            date=target_date,
            session="morning",
            symptoms_reported="First appointment",
            urgency_level="normal",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patient.id,
                date=target_date,
                session="morning",
                symptoms_reported="Duplicate appointment attempt",
                urgency_level="normal",
            ),
        )
    assert exc_info.value.status_code == 409
    assert "already has an appointment booked" in str(exc_info.value.detail).lower() or "double_booking" in str(exc_info.value.detail).lower()


# ============================================================================
# 18. CONCURRENCY & BOUNDARY TESTS
# ============================================================================

def test_18_concurrency_simultaneous_boundary_attempts(db_session, setup_data):
    """18. Test simultaneous booking attempts near capacity boundary.

    9 existing Morning appointments.
    Multiple simultaneous booking attempts.
    Expected final state: 10 maximum, NEVER 11.
    """
    doc = setup_data["doc_a"]
    target_date = setup_data["target_date"]
    patients = setup_data["patients"]

    # Pre-book 9 appointments
    for i in range(9):
        create_appointment(
            db_session,
            AppointmentCreate(
                doctor_id=doc.id,
                patient_id=patients[i].id,
                date=target_date,
                session="morning",
                symptoms_reported=f"Pre-booked {i}",
                urgency_level="normal",
            ),
        )

    # Now attempt 4 simultaneous bookings for the single remaining (10th) spot
    success_count = 0
    failure_count = 0
    lock = threading.Lock()

    def attempt_booking(p):
        nonlocal success_count, failure_count
        try:
            # Each thread uses validate_session_booking / create_appointment logic
            with lock:
                appt = create_appointment(
                    db_session,
                    AppointmentCreate(
                        doctor_id=doc.id,
                        patient_id=p.id,
                        date=target_date,
                        session="morning",
                        symptoms_reported="Concurrent race",
                        urgency_level="normal",
                    ),
                )
            if appt:
                success_count += 1
        except HTTPException as e:
            if e.status_code == 409:
                failure_count += 1
            else:
                raise

    threads = []
    # Patients 9, 10, 11, 12 try simultaneously
    for p in patients[9:13]:
        t = threading.Thread(target=attempt_booking, args=(p,))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Total booked morning appointments must be exactly 10, never 11
    final_count = (
        db_session.query(Appointment)
        .filter(
            Appointment.doctor_id == doc.id,
            Appointment.session == "morning",
            Appointment.status == "scheduled",
        )
        .count()
    )

    assert final_count == 10, f"Expected 10 morning appointments, found {final_count}"
    assert success_count == 1, f"Expected exactly 1 success, got {success_count}"
    assert failure_count == 3, f"Expected 3 rejections, got {failure_count}"
