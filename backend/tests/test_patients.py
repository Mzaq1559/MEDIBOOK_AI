import pytest


def test_get_patient_self_success(client, seed_data):
    pat_id = seed_data["patient"].id
    response = client.get(f"/api/patients/{pat_id}", headers=seed_data["patient_headers"])
    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == str(pat_id)
    assert data["email"] == "ali.khan@example.com"
    assert "Penicillin" in data["allergies"]


def test_get_patient_doctor_allowed(client, seed_data):
    pat_id = seed_data["patient"].id
    # Doctor accessing patient data is allowed
    response = client.get(f"/api/patients/{pat_id}", headers=seed_data["doctor_headers"])
    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == str(pat_id)


def test_get_patient_forbidden_for_other_patient(client, seed_data):
    pat1_id = seed_data["patient"].id
    # Patient 2 trying to access Patient 1's profile
    response = client.get(f"/api/patients/{pat1_id}", headers=seed_data["patient2_headers"])
    assert response.status_code == 403
    data = response.json()
    assert data["error"] is True
    assert data["error_code"] == "FORBIDDEN"


def test_update_patient_profile(client, seed_data):
    pat_id = seed_data["patient"].id
    payload = {
        "allergies": ["Penicillin", "Sulfa"],
        "medical_conditions": ["Hypertension", "Diabetes"],
        "emergency_contact_phone": "03009999999",
        "preferred_notification": "email"
    }
    response = client.put(f"/api/patients/{pat_id}", json=payload, headers=seed_data["patient_headers"])
    assert response.status_code == 200
    data = response.json()
    assert "Sulfa" in data["allergies"]
    assert "Diabetes" in data["medical_conditions"]
    assert data["preferred_notification"] == "email"


def test_get_patient_appointment_history(client, seed_data):
    pat_id = seed_data["patient"].id
    response = client.get(f"/api/patients/{pat_id}/appointments", headers=seed_data["patient_headers"])
    assert response.status_code == 200
    data = response.json()
    assert "appointments" in data
    assert "total" in data
