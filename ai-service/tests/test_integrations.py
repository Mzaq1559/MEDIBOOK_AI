from unittest.mock import MagicMock
from app.config import settings
from integrations.google_calendar import (
    create_calendar_event,
    update_calendar_event,
    delete_calendar_event,
    _compute_end_time,
)
from integrations.n8n_webhook import (
    send_n8n_webhook,
    dispatch_appointment_created,
    dispatch_appointment_rescheduled,
    dispatch_appointment_cancelled,
)
from integrations.reminders import (
    calculate_reminder_times,
    format_reminder_message,
    trigger_reminder,
)


def test_google_calendar_graceful_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_CREDENTIALS_PATH", "")
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_API_KEY", "")
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_SECRET", "")

    event_id = create_calendar_event({
        "doctor_name": "Dr. Ahmed Khan",
        "patient_name": "Ali Khan",
        "appointment_time": "2026-08-25T10:00:00Z",
    })
    assert event_id is None

    updated = update_calendar_event("ev-123", "2026-08-25T11:00:00Z")
    assert updated is False

    deleted = delete_calendar_event("ev-123")
    assert deleted is False


def test_google_calendar_service_account_resolution():
    from integrations.google_calendar import _resolve_credentials_path
    path = _resolve_credentials_path()
    assert path is not None
    assert "google-calendar-credentials.json" in str(path)


def test_google_calendar_end_time_computation():
    end_time = _compute_end_time("2026-08-25T10:00:00Z", duration_minutes=45)
    assert "10:45:00" in end_time


def test_google_calendar_mocked_success(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_CREDENTIALS_PATH", "")
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_API_KEY", "test-api-key")

    mock_res = MagicMock()
    mock_res.status_code = 201
    mock_res.json.return_value = {"id": "gcal-event-999"}

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_res
    mock_client.patch.return_value = mock_res
    mock_client.delete.return_value = MagicMock(status_code=204)

    monkeypatch.setattr("httpx.Client", lambda *args, **kwargs: mock_client)

    event_id = create_calendar_event({
        "doctor_name": "Dr. Ahmed Khan",
        "patient_name": "Ali Khan",
        "appointment_time": "2026-08-25T10:00:00Z",
        "clinic_name": "Prime Care Clinic",
    })
    assert event_id == "gcal-event-999"

    assert update_calendar_event("gcal-event-999", "2026-08-25T11:00:00Z") is True
    assert delete_calendar_event("gcal-event-999") is True


def test_n8n_webhook_dispatches(monkeypatch):
    calls = []

    def mock_post(url, json, headers):
        calls.append({"url": url, "json": json})
        res = MagicMock()
        res.status_code = 200
        return res

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post = mock_post

    monkeypatch.setattr("httpx.Client", lambda *args, **kwargs: mock_client)

    appt = {
        "appointment_id": "APT-001",
        "patient_id": "p-1",
        "doctor_name": "Dr. Ahmed",
        "appointment_time": "2026-08-25T10:00:00Z",
    }

    # Synchronous test
    assert dispatch_appointment_created(appt, non_blocking=False) is True
    assert len(calls) == 1
    assert calls[0]["json"]["event"] == "appointment_created"
    assert calls[0]["json"]["data"]["appointment_id"] == "APT-001"

    assert dispatch_appointment_rescheduled(appt, non_blocking=False) is True
    assert calls[1]["json"]["event"] == "appointment_rescheduled"

    assert dispatch_appointment_cancelled(appt, non_blocking=False) is True
    assert calls[2]["json"]["event"] == "appointment_cancelled"


def test_reminder_time_calculations():
    res = calculate_reminder_times("2026-08-25T14:00:00Z")
    assert res["appointment_time"] == "2026-08-25T14:00:00Z"
    assert res["reminder_time_24h"] == "2026-08-24T14:00:00Z"
    assert res["reminder_time_1h"] == "2026-08-25T13:00:00Z"
    assert res["reminder_sent_24h"] is False
    assert res["reminder_sent_1h"] is False


def test_reminder_message_and_trigger(monkeypatch):
    appt = {
        "appointment_id": "APT-2026-08-22-001",
        "doctor_name": "Dr. Ahmed Khan",
        "patient_name": "Ali Khan",
        "clinic_name": "Prime Care Clinic",
        "appointment_time": "2026-08-22T14:00:00Z",
    }

    msg_24h = format_reminder_message(appt, "24h")
    assert "Dr. Ahmed Khan" in msg_24h
    assert "tomorrow" in msg_24h

    msg_1h = format_reminder_message(appt, "1h")
    assert "in 1 hour" in msg_1h

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = MagicMock(status_code=200)
    monkeypatch.setattr("httpx.Client", lambda *args, **kwargs: mock_client)

    success = trigger_reminder(appt, "24h", non_blocking=False)
    assert success is True
