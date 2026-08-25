import pytest


def test_list_clinics(client, seed_data):
    response = client.get("/api/clinics")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["clinics"][0]["name"] == "Prime Care Clinic Taxila"
    assert data["clinics"][0]["city"] == "Taxila"


def test_get_clinic_details(client, seed_data):
    cid = seed_data["clinic"].id
    response = client.get(f"/api/clinics/{cid}")
    assert response.status_code == 200
    data = response.json()
    assert data["clinic_id"] == str(cid)
    assert len(data["doctors"]) >= 1
    assert data["working_hours_start"] == "09:00"


def test_create_clinic_admin_only(client, seed_data):
    payload = {
        "name": "Second Branch Islamabad",
        "address": "F-7 Markaz, Islamabad",
        "city": "Islamabad",
        "phone": "03007778899",
        "email": "isb@primecare.pk",
        "working_hours_start": "08:30",
        "working_hours_end": "16:30",
        "working_days": "Mon,Tue,Wed,Thu,Fri,Sat",
        "timezone": "Asia/Karachi"
    }
    # 1. Non-admin fails
    res_pat = client.post("/api/clinics", json=payload, headers=seed_data["patient_headers"])
    assert res_pat.status_code == 403

    # 2. Admin succeeds
    res_admin = client.post("/api/clinics", json=payload, headers=seed_data["admin_headers"])
    assert res_admin.status_code == 201
    data = res_admin.json()
    assert data["name"] == "Second Branch Islamabad"
    assert data["city"] == "Islamabad"
