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


def test_doctor_id_and_option_id_matching():
    from app.chatbot import _match_doctor_and_slot

    candidates = [
        {
            "doctor_id": "550e8400-e29b-41d4-a716-446655440001",
            "name": "Dr. Ahmed Khan",
            "specialization": "Cardiologist",
            "slots": [{"date": "2026-08-25", "time": "14:00", "timestamp": "2026-08-25T14:00:00Z"}],
        },
        {
            "doctor_id": "550e8400-e29b-41d4-a716-446655440002",
            "name": "Dr. Fatima Malik",
            "specialization": "Dermatologist",
            "slots": [{"date": "2026-08-25", "time": "15:30", "timestamp": "2026-08-25T15:30:00Z"}],
        },
    ]

    # Test 1: Direct option_id in nlu
    matched = _match_doctor_and_slot(
        "I select this option",
        {"option_id": "doc-550e8400-e29b-41d4-a716-446655440002"},
        candidates,
    )
    assert matched is not None
    assert matched["doctor"]["name"] == "Dr. Fatima Malik"

    # Test 2: Doctor ID in text click (doc-<uuid>)
    matched_text = _match_doctor_and_slot(
        "doc-550e8400-e29b-41d4-a716-446655440001 at 14:00",
        {},
        candidates,
    )
    assert matched_text is not None
    assert matched_text["doctor"]["name"] == "Dr. Ahmed Khan"
    assert matched_text["slot"]["time"] == "14:00"

    # Test 3: Option index (doc-2)
    matched_opt = _match_doctor_and_slot("doc-2", {}, candidates)
    assert matched_opt is not None
    assert matched_opt["doctor"]["name"] == "Dr. Fatima Malik"

    # Test 4: Name fallback
    matched_name = _match_doctor_and_slot("Dr. Ahmed", {}, candidates)
    assert matched_name is not None
    assert matched_name["doctor"]["name"] == "Dr. Ahmed Khan"


def test_session_ttl_eviction(monkeypatch):
    import time
    from app import chatbot

    conv_id = "conv-ttl-test-123"
    session = chatbot._new_session(conv_id, "patient-1")
    assert chatbot.get_session(conv_id) is not None

    # Advance time by 3 hours (exceeding 2-hour TTL)
    future_time = time.time() + 3 * 3600
    monkeypatch.setattr(time, "time", lambda: future_time)

    # get_session triggers cleanup and returns None
    assert chatbot.get_session(conv_id) is None
    assert conv_id not in chatbot._sessions


def test_booking_triggers_calendar_n8n_and_reminders(monkeypatch):
    from app import chatbot
    from integrations import google_calendar, n8n_webhook, reminders

    calls = {"gcal": 0, "n8n_created": 0, "reminders": []}

    def fake_create_appt(*args, **kwargs):
        return {
            "appointment_id": "550e8400-e29b-41d4-a716-446655440099",
            "doctor_id": "550e8400-e29b-41d4-a716-446655440001",
            "doctor_name": "Dr. Ahmed Khan",
            "patient_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "patient_name": "Ali Khan",
            "appointment_time": "2026-08-25T14:00:00Z",
            "status": "confirmed",
        }

    def fake_gcal_create(payload):
        calls["gcal"] += 1
        return "gcal-evt-12345"

    def fake_n8n_created(payload):
        calls["n8n_created"] += 1
        return True

    def fake_trigger_reminder(payload, reminder_type="24h", **kwargs):
        calls["reminders"].append(reminder_type)
        return True

    monkeypatch.setattr(chatbot.backend_client, "create_appointment", fake_create_appt)
    monkeypatch.setattr(google_calendar, "create_calendar_event", fake_gcal_create)
    monkeypatch.setattr(n8n_webhook, "dispatch_appointment_created", fake_n8n_created)
    monkeypatch.setattr(reminders, "trigger_reminder", fake_trigger_reminder)

    conv = "conv-integration-booking-test"
    session = chatbot._new_session(conv, "f47ac10b-58cc-4372-a567-0e02b2c3d479")
    session["state"] = "await_confirm"
    session["selected_doctor"] = {
        "doctor_id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "Dr. Ahmed Khan",
        "specialization": "Cardiologist",
        "clinic_name": "Prime Care Clinic",
        "clinic_address": "Ground Floor, ABC Plaza, Taxila",
        "consultation_fee": 2500,
    }
    session["selected_timestamp"] = "2026-08-25T14:00:00Z"
    session["selected_slot_label"] = "2026-08-25 at 14:00"

    res = client.post(
        "/api/chat/message",
        headers={"Authorization": "Bearer fake-jwt-token"},
        json={"conversation_id": conv, "message": "yes, confirm", "patient_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["next_action"] == "appointment_booked"
    assert "confirmed" in body["bot_message"].lower()
    assert "whatsapp reminder 24 hours before" in body["bot_message"].lower()
    assert "whatsapp reminder 1 hour before" in body["bot_message"].lower()
    assert "calendar invite" in body["bot_message"].lower()

    # Verify integrations were called
    assert calls["gcal"] == 1
    assert calls["n8n_created"] == 1
    assert "24h" in calls["reminders"]
    assert "1h" in calls["reminders"]


def test_booking_succeeds_even_when_integrations_fail(monkeypatch):
    from app import chatbot
    from integrations import google_calendar, n8n_webhook, reminders

    def fake_create_appt(*args, **kwargs):
        return {
            "appointment_id": "550e8400-e29b-41d4-a716-446655440099",
            "doctor_id": "550e8400-e29b-41d4-a716-446655440001",
            "doctor_name": "Dr. Ahmed Khan",
            "patient_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "appointment_time": "2026-08-25T14:00:00Z",
            "status": "confirmed",
        }

    def failing_gcal(payload):
        raise RuntimeError("Google API network crash")

    def failing_n8n(payload):
        raise RuntimeError("n8n endpoint unreachable")

    def failing_reminder(payload, reminder_type="24h", **kwargs):
        raise RuntimeError("Reminder dispatch error")

    monkeypatch.setattr(chatbot.backend_client, "create_appointment", fake_create_appt)
    monkeypatch.setattr(google_calendar, "create_calendar_event", failing_gcal)
    monkeypatch.setattr(n8n_webhook, "dispatch_appointment_created", failing_n8n)
    monkeypatch.setattr(reminders, "trigger_reminder", failing_reminder)

    conv = "conv-integration-failure-resilience-test"
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
    session["selected_timestamp"] = "2026-08-25T14:00:00Z"
    session["selected_slot_label"] = "2026-08-25 at 14:00"

    res = client.post(
        "/api/chat/message",
        headers={"Authorization": "Bearer fake-jwt-token"},
        json={"conversation_id": conv, "message": "confirm", "patient_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"},
    )
    # The booking confirmation must still succeed!
    assert res.status_code == 200
    body = res.json()
    assert body["next_action"] == "appointment_booked"
    assert "confirmed" in body["bot_message"].lower()


def test_reschedule_triggers_calendar_and_n8n(monkeypatch):
    from app import chatbot
    from integrations import google_calendar, n8n_webhook

    calls = {"gcal_update": 0, "n8n_reschedule": 0}

    def fake_reschedule_appt(*args, **kwargs):
        return {
            "appointment_id": "550e8400-e29b-41d4-a716-446655440099",
            "appointment_time": "2026-08-26T10:00:00Z",
            "status": "rescheduled",
        }

    def fake_gcal_update(event_id, new_time, **kwargs):
        calls["gcal_update"] += 1
        return True

    def fake_n8n_reschedule(payload):
        calls["n8n_reschedule"] += 1
        return True

    monkeypatch.setattr(chatbot.backend_client, "reschedule_appointment", fake_reschedule_appt)
    monkeypatch.setattr(google_calendar, "update_calendar_event", fake_gcal_update)
    monkeypatch.setattr(n8n_webhook, "dispatch_appointment_rescheduled", fake_n8n_reschedule)

    conv = "conv-reschedule-integration-test"
    session = chatbot._new_session(conv, "f47ac10b-58cc-4372-a567-0e02b2c3d479")
    session["state"] = "reschedule_await_confirm"
    session["reschedule_appointment_id"] = "550e8400-e29b-41d4-a716-446655440099"
    session["google_calendar_event_id"] = "gcal-event-999"
    session["selected_timestamp"] = "2026-08-26T10:00:00Z"
    session["selected_slot_label"] = "2026-08-26 at 10:00"

    res = client.post(
        "/api/chat/message",
        headers={"Authorization": "Bearer fake-jwt-token"},
        json={"conversation_id": conv, "message": "yes, confirm", "patient_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["next_action"] == "reschedule_complete"
    assert "rescheduled" in body["bot_message"].lower()
    assert "whatsapp reminder" in body["bot_message"].lower()

    assert calls["gcal_update"] == 1
    assert calls["n8n_reschedule"] == 1


def test_roman_urdu_booking_intent_and_emergency():
    from app import chatbot

    # 1. Booking intent in Roman Urdu
    conv = "conv-roman-urdu-1"
    res1 = client.post(
        "/api/chat/message",
        json={"conversation_id": conv, "message": "doctor se milna hai"},
    )
    assert res1.status_code == 200
    assert res1.json()["next_action"] == "waiting_for_symptoms"

    # 2. Emergency in Roman Urdu during symptom intake
    res2 = client.post(
        "/api/chat/message",
        json={"conversation_id": conv, "message": "seene mein shadeed dard aur saans lene me dushwari ho rahi hai"},
    )
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["next_action"] == "emergency_redirect"
    assert "1100" in body2["bot_message"]


def test_roman_urdu_confirmation_and_decline(monkeypatch):
    from app import chatbot

    def fake_create_appt(*args, **kwargs):
        return {
            "appointment_id": "APT-URDU-001",
            "doctor_name": "Dr. Ahmed Khan",
            "appointment_time": "2026-08-25T14:00:00Z",
            "status": "confirmed",
        }

    monkeypatch.setattr(chatbot.backend_client, "create_appointment", fake_create_appt)

    # Test "haan confirm" in Roman Urdu
    conv_confirm = "conv-roman-urdu-confirm"
    pid = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
    s1 = chatbot._new_session(conv_confirm, pid)
    s1["state"] = "await_confirm"
    s1["selected_doctor"] = {
        "doctor_id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "Dr. Ahmed Khan",
    }
    s1["selected_timestamp"] = "2026-08-25T14:00:00Z"
    s1["selected_slot_label"] = "2026-08-25 at 14:00"

    res_confirm = client.post(
        "/api/chat/message",
        headers={"Authorization": "Bearer fake-jwt"},
        json={"conversation_id": conv_confirm, "message": "haan confirm", "patient_id": pid},
    )
    assert res_confirm.status_code == 200
    assert res_confirm.json()["next_action"] == "appointment_booked"
    assert "confirmed" in res_confirm.json()["bot_message"].lower()

    # Test "nahi mat karo" decline in Roman Urdu
    conv_decline = "conv-roman-urdu-decline"
    s2 = chatbot._new_session(conv_decline, pid)
    s2["state"] = "await_confirm"
    s2["selected_doctor"] = {
        "doctor_id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "Dr. Ahmed Khan",
    }

    res_decline = client.post(
        "/api/chat/message",
        headers={"Authorization": "Bearer fake-jwt"},
        json={"conversation_id": conv_decline, "message": "nahi mat karo", "patient_id": pid},
    )
    assert res_decline.status_code == 200
    assert res_decline.json()["next_action"] == "waiting_for_doctor_selection"


def test_unrecognized_conversation_id_handled_gracefully():
    # 1. Non-existent / unrecognized conversation_id treats it as a new session without crashing
    res = client.post(
        "/api/chat/message",
        json={
            "conversation_id": "conv-XXXXXXXXX",
            "message": "some message",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["conversation_id"] == "conv-XXXXXXXXX"
    assert "bot_message" in data
    assert data["bot_message"] != ""


def test_exception_in_chat_returns_clean_400_instead_of_500(monkeypatch):
    from app import main

    def broken_handler(*args, **kwargs):
        raise ValueError("Corrupted session data")

    monkeypatch.setattr(main, "handle_message", broken_handler)

    res = client.post(
        "/api/chat/message",
        json={
            "conversation_id": "conv-corrupted-999",
            "message": "hello",
        },
    )
    assert res.status_code == 400
    assert res.json()["error_code"] == "INVALID_CONVERSATION"
    assert "Invalid or expired conversation_id" in res.json()["message"]





