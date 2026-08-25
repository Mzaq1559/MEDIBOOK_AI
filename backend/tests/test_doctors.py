import pytest


def test_list_doctors(client, seed_data):
    response = client.get("/api/doctors")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["doctors"]) >= 1
    assert data["doctors"][0]["specialization"] == "Cardiologist"


def test_list_doctors_with_filter(client, seed_data):
    response = client.get("/api/doctors?specialization=Cardio")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1

    response2 = client.get("/api/doctors?specialization=NonExistentSpec")
    assert response2.status_code == 200
    assert response2.json()["total"] == 0


def test_get_doctor_details(client, seed_data):
    doc_id = seed_data["doctor"].id
    response = client.get(f"/api/doctors/{doc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["doctor_id"] == str(doc_id)
    assert data["specialization"] == "Cardiologist"
    assert data["working_hours_start"] == "09:00"


def test_update_doctor_schedule_authorized(client, seed_data):
    doc_id = seed_data["doctor"].id
    payload = {
        "date": "2026-08-25",
        "start_time": "10:00",
        "end_time": "16:00",
        "break_start": "13:00",
        "break_end": "14:00",
        "is_holiday": False
    }
    response = client.put(
        f"/api/doctors/{doc_id}/schedule",
        json=payload,
        headers=seed_data["doctor_headers"]
    )
    assert response.status_code == 200
    data = response.json()
    assert data["start_time"] == "10:00"
    assert data["end_time"] == "16:00"


def test_update_doctor_schedule_unauthorized_role(client, seed_data):
    doc_id = seed_data["doctor"].id
    payload = {
        "date": "2026-08-25",
        "start_time": "10:00",
        "end_time": "16:00"
    }
    # Patients cannot update doctor schedules
    response = client.put(
        f"/api/doctors/{doc_id}/schedule",
        json=payload,
        headers=seed_data["patient_headers"]
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN"


def test_mark_doctor_holiday(client, seed_data):
    doc_id = seed_data["doctor"].id
    payload = {
        "date": "2026-08-28",
        "reason": "Personal Leave"
    }
    response = client.patch(
        f"/api/doctors/{doc_id}/holiday",
        json=payload,
        headers=seed_data["doctor_headers"]
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_holiday"] is True
    assert data["reason"] == "Personal Leave"
