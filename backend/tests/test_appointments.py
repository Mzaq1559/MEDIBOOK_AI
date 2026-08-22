import pytest
import uuid
from datetime import datetime, date, time, timedelta


def test_create_appointment_success(client, seed_data):
    doc_id = str(seed_data["doctor"].id)
    pat_id = str(seed_data["patient"].id)

    # Next working weekday at 10:00 AM
    target = date.today() + timedelta(days=1)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    appt_time = f"{target.strftime('%Y-%m-%d')}T10:00:00Z"

    payload = {
        "doctor_id": doc_id,
        "patient_id": pat_id,
        "appointment_time": appt_time,
        "symptoms_reported": "Severe chest pain and difficulty breathing",
        "urgency_level": "high",
        "appointment_type": "in_person"
    }

    response = client.post("/api/appointments", json=payload, headers=seed_data["patient_headers"])
    assert response.status_code == 201
    data = response.json()
    assert data["doctor_id"] == doc_id
    assert data["patient_id"] == pat_id
    assert data["status"] == "scheduled"
    assert data["urgency_level"] == "high"
    assert "confirmation_message" in data
    assert "reminder_time_1" in data


def test_create_appointment_doctor_double_booking(client, seed_data):
    doc_id = str(seed_data["doctor"].id)
    pat1_id = str(seed_data["patient"].id)
    pat2_id = str(seed_data["patient2"].id)

    target = date.today() + timedelta(days=2)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    appt_time = f"{target.strftime('%Y-%m-%d')}T11:00:00Z"

    # First booking for patient 1
    res1 = client.post(
        "/api/appointments",
        json={
            "doctor_id": doc_id,
            "patient_id": pat1_id,
            "appointment_time": appt_time,
            "symptoms_reported": "Headache",
            "urgency_level": "normal"
        },
        headers=seed_data["patient_headers"]
    )
    assert res1.status_code == 201

    # Second booking for patient 2 at same time with same doctor -> Conflict
    res2 = client.post(
        "/api/appointments",
        json={
            "doctor_id": doc_id,
            "patient_id": pat2_id,
            "appointment_time": appt_time,
            "symptoms_reported": "Fever",
            "urgency_level": "normal"
        },
        headers=seed_data["patient2_headers"]
    )
    assert res2.status_code == 409
    data = res2.json()
    assert data["error"] is True
    assert data["error_code"] == "SLOT_UNAVAILABLE"


def test_create_appointment_patient_double_booking(client, seed_data, db_session):
    doc1_id = str(seed_data["doctor"].id)
    pat1_id = str(seed_data["patient"].id)

    # Create a second doctor
    doc2_user = seed_data["admin_user"]  # use admin user id or new user
    doc2 = seed_data["doctor"]

    target = date.today() + timedelta(days=3)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    appt_time = f"{target.strftime('%Y-%m-%d')}T14:00:00Z"

    # Patient books with doctor 1
    res1 = client.post(
        "/api/appointments",
        json={
            "doctor_id": doc1_id,
            "patient_id": pat1_id,
            "appointment_time": appt_time,
            "symptoms_reported": "Checkup",
            "urgency_level": "normal"
        },
        headers=seed_data["patient_headers"]
    )
    assert res1.status_code == 201

    # Same patient tries to book with doctor 1 at exact same slot -> DOUBLE_BOOKING error
    res2 = client.post(
        "/api/appointments",
        json={
            "doctor_id": doc1_id,
            "patient_id": pat1_id,
            "appointment_time": appt_time,
            "symptoms_reported": "Another checkup",
            "urgency_level": "normal"
        },
        headers=seed_data["patient_headers"]
    )
    assert res2.status_code == 409
    data = res2.json()
    assert data["error"] is True
    assert data["error_code"] in ("DOUBLE_BOOKING", "SLOT_UNAVAILABLE")


def test_create_appointment_past_time(client, seed_data):
    doc_id = str(seed_data["doctor"].id)
    pat_id = str(seed_data["patient"].id)

    payload = {
        "doctor_id": doc_id,
        "patient_id": pat_id,
        "appointment_time": "2020-01-01T10:00:00Z",
        "symptoms_reported": "Past symptom",
        "urgency_level": "normal"
    }

    response = client.post("/api/appointments", json=payload, headers=seed_data["patient_headers"])
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "INVALID_TIME"


def test_get_and_list_appointments(client, seed_data):
    doc_id = str(seed_data["doctor"].id)
    pat_id = str(seed_data["patient"].id)

    target = date.today() + timedelta(days=4)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    appt_time = f"{target.strftime('%Y-%m-%d')}T15:00:00Z"

    create_res = client.post(
        "/api/appointments",
        json={
            "doctor_id": doc_id,
            "patient_id": pat_id,
            "appointment_time": appt_time,
            "symptoms_reported": "Back pain",
            "urgency_level": "low"
        },
        headers=seed_data["patient_headers"]
    )
    appt_id = create_res.json()["appointment_id"]

    # 1. Get Appointment Details
    detail_res = client.get(f"/api/appointments/{appt_id}", headers=seed_data["patient_headers"])
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["appointment_id"] == appt_id
    assert detail_data["doctor_name"] == "Dr. Ahmed Khan"

    # 2. List Appointments
    list_res = client.get(f"/api/appointments?status=scheduled", headers=seed_data["patient_headers"])
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1


def test_reschedule_and_cancel_appointment(client, seed_data):
    doc_id = str(seed_data["doctor"].id)
    pat_id = str(seed_data["patient"].id)

    target = date.today() + timedelta(days=5)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    appt_time = f"{target.strftime('%Y-%m-%d')}T09:30:00Z"

    create_res = client.post(
        "/api/appointments",
        json={
            "doctor_id": doc_id,
            "patient_id": pat_id,
            "appointment_time": appt_time,
            "symptoms_reported": "Flu",
            "urgency_level": "low"
        },
        headers=seed_data["patient_headers"]
    )
    appt_id = create_res.json()["appointment_id"]

    # Reschedule to 10:30 AM
    new_appt_time = f"{target.strftime('%Y-%m-%d')}T10:30:00Z"
    resched_res = client.put(
        f"/api/appointments/{appt_id}",
        json={"appointment_time": new_appt_time},
        headers=seed_data["patient_headers"]
    )
    assert resched_res.status_code == 200
    resched_data = resched_res.json()
    assert resched_data["status"] == "scheduled"
    assert "rescheduled successfully" in resched_data["message"]

    # Cancel Appointment
    cancel_res = client.delete(f"/api/appointments/{appt_id}", headers=seed_data["patient_headers"])
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["status"] == "cancelled"


def test_complete_and_feedback_flow(client, seed_data):
    doc_id = str(seed_data["doctor"].id)
    pat_id = str(seed_data["patient"].id)

    target = date.today() + timedelta(days=6)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    appt_time = f"{target.strftime('%Y-%m-%d')}T11:30:00Z"

    create_res = client.post(
        "/api/appointments",
        json={
            "doctor_id": doc_id,
            "patient_id": pat_id,
            "appointment_time": appt_time,
            "symptoms_reported": "High blood pressure",
            "urgency_level": "high"
        },
        headers=seed_data["patient_headers"]
    )
    appt_id = create_res.json()["appointment_id"]

    # Doctor marks as completed
    comp_res = client.patch(
        f"/api/appointments/{appt_id}/complete",
        json={"notes": "Prescribed antihypertensive medication."},
        headers=seed_data["doctor_headers"]
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "completed"

    # Patient submits 5-star feedback
    feed_res = client.patch(
        f"/api/appointments/{appt_id}/feedback",
        json={"feedback_score": 5, "feedback_text": "Great doctor and quick consultation!"},
        headers=seed_data["patient_headers"]
    )
    assert feed_res.status_code == 200
    feed_data = feed_res.json()
    assert feed_data["feedback_score"] == 5
    assert feed_data["doctor_rating_updated"] > 0
