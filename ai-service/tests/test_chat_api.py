from fastapi.testclient import TestClient

from app.main import app
from app.symptom_triage import EMERGENCY_ALERT

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "medibook-ai-service"


def test_empty_message_rejected():
    res = client.post("/api/chat/message", json={"message": "   "})
    assert res.status_code in (400, 422)


def test_emergency_skips_llm_and_returns_exact_text():
    res = client.post(
        "/api/chat/message",
        json={"message": "I'm having severe chest pain and can't breathe"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["bot_message"] == EMERGENCY_ALERT
    assert body["next_action"] == "emergency_redirect"
    conv = body["conversation_id"]
    hist = client.get(f"/api/chat/history/{conv}")
    assert hist.status_code == 200
    assert hist.json()["messages"]


def test_confirm_without_jwt_asks_login(monkeypatch):
    from app import chatbot

    calls = {"create": 0}

    def fake_create(*args, **kwargs):
        calls["create"] += 1
        raise AssertionError("must not call backend without JWT")

    monkeypatch.setattr(chatbot.backend_client, "create_appointment", fake_create)

    conv = "conv-login-test"
    session = chatbot._new_session(conv, "f47ac10b-58cc-4372-a567-0e02b2c3d479")
    session["state"] = "await_confirm"
    session["selected_doctor"] = {
        "doctor_id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "Dr. Ahmed Khan",
        "specialization": "Cardiologist",
        "clinic_name": "Prime Care Clinic",
        "clinic_address": "Taxila",
        "consultation_fee": 2500,
    }
    session["selected_timestamp"] = "2026-08-25T09:00:00Z"
    session["selected_slot_label"] = "2026-08-25 at 09:00"
    session["symptoms_text"] = "chest pain"

    res = client.post(
        "/api/chat/message",
        json={"conversation_id": conv, "message": "yes, confirm", "patient_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"},
    )
    assert res.status_code == 200
    assert "logged in" in res.json()["bot_message"].lower()
    assert res.json()["next_action"] == "waiting_for_login"
    assert calls["create"] == 0
