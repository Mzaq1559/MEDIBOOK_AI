import pytest
from fastapi import status


# ---------------------------------------------------------------------------
# 1. Chat: verify the bot returns a real response (not an error fallback)
# ---------------------------------------------------------------------------
def test_chat_returns_real_response(client):
    resp = client.post("/api/chat/message", json={"message": "hello"})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "Please try again or contact our team" not in data.get("bot_message", "")


# ---------------------------------------------------------------------------
# 2-4. Login tests for each seeded role
# ---------------------------------------------------------------------------
def test_admin_login_succeeds(client, auth_headers_factory):
    headers = auth_headers_factory("admin")
    assert "Authorization" in headers
    # Verify the token works on a protected endpoint
    resp = client.get("/api/analytics/dashboard", headers=headers)
    assert resp.status_code == status.HTTP_200_OK


def test_doctor_login_succeeds(client, auth_headers_factory):
    headers = auth_headers_factory("doctor")
    assert "Authorization" in headers
    resp = client.get("/api/analytics/dashboard", headers=headers)
    assert resp.status_code == status.HTTP_200_OK


def test_patient_login_succeeds(client, auth_headers_factory):
    headers = auth_headers_factory("patient")
    assert "Authorization" in headers
    # Patient can search their own appointments
    resp = client.get("/api/appointments/search", headers=headers)
    assert resp.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# 5. Mark an appointment complete → dashboard count goes up
# ---------------------------------------------------------------------------
def _get_first_non_completed_appointment(client, headers):
    """Return the first appointment whose status is not 'completed'."""
    resp = client.get("/api/appointments", headers=headers)
    if resp.status_code != status.HTTP_200_OK:
        return None
    data = resp.json()
    for apt in data.get("appointments", []):
        if apt.get("status") != "completed":
            return apt
    return None


def test_mark_complete_updates_status_and_stats(client, auth_headers_factory):
    admin_headers = auth_headers_factory("admin")

    # Find a non-completed appointment
    apt = _get_first_non_completed_appointment(client, admin_headers)
    assert apt is not None, "No suitable appointment found to complete"
    apt_id = apt["appointment_id"]

    # Extract the appointment's date so we query the dashboard for the correct day
    apt_date = apt["appointment_time"][:10]  # "YYYY-MM-DD"

    # Snapshot dashboard metrics for that date before completing
    before_resp = client.get(
        "/api/analytics/dashboard",
        params={"date": apt_date},
        headers=admin_headers,
    )
    assert before_resp.status_code == status.HTTP_200_OK
    completed_before = before_resp.json().get("completed_today", 0)

    # Complete the appointment
    complete_resp = client.patch(
        f"/api/appointments/{apt_id}/complete",
        json={"notes": "Test completion"},
        headers=admin_headers,
    )
    assert complete_resp.status_code == status.HTTP_200_OK

    # Dashboard count for that date should have increased by 1
    after_resp = client.get(
        "/api/analytics/dashboard",
        params={"date": apt_date},
        headers=admin_headers,
    )
    assert after_resp.status_code == status.HTTP_200_OK
    completed_after = after_resp.json().get("completed_today", 0)
    assert completed_after == completed_before + 1


# ---------------------------------------------------------------------------
# 6. Patient sees updated appointment status after completion
# ---------------------------------------------------------------------------
def test_patient_sees_updated_status(client, auth_headers_factory):
    patient_headers = auth_headers_factory("patient")
    resp = client.get("/api/appointments/search", headers=patient_headers)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    completed = [
        a for a in data.get("appointments", [])
        if a.get("status") == "completed"
    ]
    assert completed, "Patient does not see any completed appointments"
