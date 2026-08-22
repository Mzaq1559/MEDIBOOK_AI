import pytest
import uuid
from datetime import datetime, date, time, timedelta
from app.models.clinic_holiday import ClinicHoliday
from app.models.doctor_schedule import DoctorSchedule
from app.models.appointment import Appointment


def test_doctor_availability_normal_working_day(client, seed_data):
    doc_id = seed_data["doctor"].id
    # Find next Monday (weekday index 0)
    target = date.today() + timedelta(days=1)
    while target.weekday() != 0:
        target += timedelta(days=1)

    url = f"/api/doctors/{doc_id}/availability?date={target.strftime('%Y-%m-%d')}&next_days=1"
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()

    assert data["doctor_id"] == str(doc_id)
    assert len(data["availability"]) == 1
    day_info = data["availability"][0]
    assert day_info["working_hours"] == "09:00-17:00"
    assert len(day_info["slots"]) > 0
    # Check slots count (09:00 to 17:00 at 30 min duration = 16 slots)
    assert len(day_info["slots"]) == 16
    assert day_info["available_count"] == 16


def test_doctor_availability_weekend_closed(client, seed_data):
    doc_id = seed_data["doctor"].id
    # Find next Sunday (weekday index 6)
    target = date.today() + timedelta(days=1)
    while target.weekday() != 6:
        target += timedelta(days=1)

    url = f"/api/doctors/{doc_id}/availability?date={target.strftime('%Y-%m-%d')}&next_days=1"
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    day_info = data["availability"][0]
    assert day_info["working_hours"] == "CLOSED"
    assert len(day_info["slots"]) == 0
    assert day_info["available_count"] == 0


def test_doctor_availability_clinic_holiday(client, seed_data, db_session):
    doc_id = seed_data["doctor"].id
    target = date.today() + timedelta(days=2)
    while target.weekday() >= 5:
        target += timedelta(days=1)

    # Insert clinic holiday
    holiday = ClinicHoliday(
        id=uuid.uuid4(),
        clinic_id=seed_data["clinic"].id,
        holiday_date=target,
        holiday_name="Special Test Holiday"
    )
    db_session.add(holiday)
    db_session.commit()

    url = f"/api/doctors/{doc_id}/availability?date={target.strftime('%Y-%m-%d')}&next_days=1"
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    day_info = data["availability"][0]
    assert day_info["working_hours"] == "HOLIDAY"
    assert len(day_info["slots"]) == 0


def test_doctor_availability_doctor_holiday(client, seed_data, db_session):
    doc_id = seed_data["doctor"].id
    target = date.today() + timedelta(days=3)
    while target.weekday() >= 5:
        target += timedelta(days=1)

    # Mark doctor schedule as holiday
    sched = DoctorSchedule(
        id=uuid.uuid4(),
        doctor_id=doc_id,
        date=target,
        is_holiday=True,
        holiday_reason="Annual Medical Conference"
    )
    db_session.add(sched)
    db_session.commit()

    url = f"/api/doctors/{doc_id}/availability?date={target.strftime('%Y-%m-%d')}&next_days=1"
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    day_info = data["availability"][0]
    assert day_info["working_hours"] == "HOLIDAY"
    assert len(day_info["slots"]) == 0


def test_doctor_availability_with_break_and_existing_appointment(client, seed_data, db_session):
    doc_id = seed_data["doctor"].id
    target = date.today() + timedelta(days=4)
    while target.weekday() >= 5:
        target += timedelta(days=1)

    # Set break 13:00 to 14:00
    sched = DoctorSchedule(
        id=uuid.uuid4(),
        doctor_id=doc_id,
        date=target,
        start_time=time(9, 0),
        end_time=time(17, 0),
        break_start=time(13, 0),
        break_end=time(14, 0)
    )
    db_session.add(sched)

    # Add existing appointment at 10:00
    appt = Appointment(
        id=uuid.uuid4(),
        clinic_id=seed_data["clinic"].id,
        doctor_id=doc_id,
        patient_id=seed_data["patient"].id,
        appointment_time=datetime.combine(target, time(10, 0)),
        duration_minutes=30,
        status="scheduled",
        symptoms_reported="Chest pain",
        urgency_level="normal"
    )
    db_session.add(appt)
    db_session.commit()

    url = f"/api/doctors/{doc_id}/availability?date={target.strftime('%Y-%m-%d')}&next_days=1"
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    day_info = data["availability"][0]

    # Slot at 10:00 should be booked
    slot_10 = next(s for s in day_info["slots"] if s["time"] == "10:00")
    assert slot_10["available"] is False
    assert slot_10["status"] == "booked"

    # Slots during lunch break (13:00, 13:30) should be booked/unavailable
    slot_13 = next(s for s in day_info["slots"] if s["time"] == "13:00")
    assert slot_13["available"] is False
    slot_1330 = next(s for s in day_info["slots"] if s["time"] == "13:30")
    assert slot_1330["available"] is False

    # Slot at 09:00 should be free
    slot_09 = next(s for s in day_info["slots"] if s["time"] == "09:00")
    assert slot_09["available"] is True


def test_doctor_availability_daily_capacity_reached(client, seed_data, db_session):
    doc_id = seed_data["doctor"].id
    target = date.today() + timedelta(days=5)
    while target.weekday() >= 5:
        target += timedelta(days=1)

    # Set daily limit of 2 patients
    sched = DoctorSchedule(
        id=uuid.uuid4(),
        doctor_id=doc_id,
        date=target,
        max_patients=2
    )
    db_session.add(sched)

    # Add 2 appointments
    for h in [9, 10]:
        db_session.add(
            Appointment(
                id=uuid.uuid4(),
                clinic_id=seed_data["clinic"].id,
                doctor_id=doc_id,
                patient_id=seed_data["patient"].id,
                appointment_time=datetime.combine(target, time(h, 0)),
                duration_minutes=30,
                status="scheduled",
                symptoms_reported="Fever",
                urgency_level="normal"
            )
        )
    db_session.commit()

    url = f"/api/doctors/{doc_id}/availability?date={target.strftime('%Y-%m-%d')}&next_days=1"
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    day_info = data["availability"][0]
    assert day_info["available_count"] == 0
    assert all(s["available"] is False for s in day_info["slots"])
