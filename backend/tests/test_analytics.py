import pytest
from datetime import date


def test_get_dashboard_analytics_authorized(client, seed_data):
    response = client.get("/api/analytics/dashboard", headers=seed_data["doctor_headers"])
    assert response.status_code == 200
    data = response.json()
    assert "total_appointments_today" in data
    assert "completed_today" in data
    assert "doctor_utilization_percent" in data
    assert "common_symptoms" in data
    assert data["clinic_name"] == "Prime Care Clinic Taxila"


def test_get_dashboard_analytics_forbidden_for_patient(client, seed_data):
    response = client.get("/api/analytics/dashboard", headers=seed_data["patient_headers"])
    assert response.status_code == 403
    data = response.json()
    assert data["error"] is True
    assert data["error_code"] == "FORBIDDEN"


def test_get_daily_summary(client, seed_data):
    today_str = date.today().strftime("%Y-%m-%d")
    response = client.get(f"/api/analytics/daily-summary?date={today_str}", headers=seed_data["admin_headers"])
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == today_str
    assert "appointments_by_status" in data
    assert "appointments_by_urgency" in data
    assert "summary" in data
