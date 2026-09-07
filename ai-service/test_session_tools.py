"""Unit tests for session-based booking tools in AI service."""

from __future__ import annotations
import pytest
from app.tools import (
    REQUIRED_PARAMS,
    TOOL_DEFINITIONS,
    tool_propose_book_appointment,
    execute_tool,
    _booking_error,
)
from app import backend_client


def test_propose_book_appointment_schema_and_required_params():
    """Verify REQUIRED_PARAMS and TOOL_DEFINITIONS require patient_id, doctor_id, date, session, symptoms."""
    expected = ["patient_id", "doctor_id", "date", "session", "symptoms"]
    assert REQUIRED_PARAMS["propose_book_appointment"] == expected

    tool_def = next(
        t for t in TOOL_DEFINITIONS if t["function"]["name"] == "propose_book_appointment"
    )
    req = tool_def["function"]["parameters"]["required"]
    assert req == expected
    props = tool_def["function"]["parameters"]["properties"]
    assert "date" in props
    assert "session" in props
    assert "datetime" in props  # retained for legacy compatibility


def test_missing_date_returns_clear_error_no_today_fallback():
    """Verify tool_propose_book_appointment does NOT silently fall back to today when date is missing."""
    session = {
        "conversation_id": "test-c1",
        "candidate_doctors": [{"doctor_id": "doc-1", "name": "Dr. Smith", "clinic_name": "Clinic", "clinic_address": "Addr"}],
    }
    args = {
        "patient_id": "pat-1",
        "doctor_id": "doc-1",
        "session": "morning",
        "symptoms": "Fever",
        # date is omitted
    }
    res = tool_propose_book_appointment(session, args, auth="Bearer token")
    assert res["ok"] is False
    assert "A booking date is required (YYYY-MM-DD)" in res["error"]


def test_invalid_date_returns_clear_error():
    """Verify tool_propose_book_appointment rejects invalid date format."""
    session = {
        "conversation_id": "test-c1",
        "candidate_doctors": [{"doctor_id": "doc-1", "name": "Dr. Smith", "clinic_name": "Clinic", "clinic_address": "Addr"}],
    }
    args = {
        "patient_id": "pat-1",
        "doctor_id": "doc-1",
        "date": "invalid-not-a-date",
        "session": "morning",
        "symptoms": "Fever",
    }
    res = tool_propose_book_appointment(session, args, auth="Bearer token")
    assert res["ok"] is False
    assert "Invalid date format" in res["error"]


def test_missing_session_returns_clear_error_no_morning_fallback():
    """Verify tool_propose_book_appointment does NOT silently fall back to morning when session is missing."""
    session = {
        "conversation_id": "test-c1",
        "candidate_doctors": [{"doctor_id": "doc-1", "name": "Dr. Smith", "clinic_name": "Clinic", "clinic_address": "Addr"}],
    }
    args = {
        "patient_id": "pat-1",
        "doctor_id": "doc-1",
        "date": "2026-09-15",
        "symptoms": "Fever",
        # session is omitted
    }
    res = tool_propose_book_appointment(session, args, auth="Bearer token")
    assert res["ok"] is False
    assert "Please select a session: Morning (max 10 bookings) or Evening (max 5 bookings)" in res["error"]


def test_invalid_session_returns_clear_error():
    """Verify tool_propose_book_appointment rejects non-morning/evening sessions."""
    session = {
        "conversation_id": "test-c1",
        "candidate_doctors": [{"doctor_id": "doc-1", "name": "Dr. Smith", "clinic_name": "Clinic", "clinic_address": "Addr"}],
    }
    args = {
        "patient_id": "pat-1",
        "doctor_id": "doc-1",
        "date": "2026-09-15",
        "session": "afternoon",
        "symptoms": "Fever",
    }
    res = tool_propose_book_appointment(session, args, auth="Bearer token")
    assert res["ok"] is False
    assert "Please select a session: Morning (max 10 bookings) or Evening (max 5 bookings)" in res["error"]


def test_valid_session_and_date_creates_proposal():
    """Verify tool_propose_book_appointment succeeds with valid session and date."""
    session = {
        "conversation_id": "test-c1",
        "candidate_doctors": [{"doctor_id": "doc-1", "name": "Dr. Smith", "clinic_name": "Clinic", "clinic_address": "Addr"}],
    }
    args = {
        "patient_id": "pat-1",
        "doctor_id": "doc-1",
        "date": "2026-09-15",
        "session": "evening",
        "symptoms": "Headache",
    }
    res = tool_propose_book_appointment(session, args, auth="Bearer token")
    assert res["ok"] is True
    assert "proposal_id" in res
    assert "Evening Session" in res["summary"]
    assert "2026-09-15" in res["summary"]


def test_execute_tool_enforces_required_parameters():
    """Verify execute_tool enforces missing required date and session."""
    session = {"patient_id": "pat-1"}
    res = execute_tool(
        name="propose_book_appointment",
        arguments={"doctor_id": "doc-1", "symptoms": "Cough"},
        session=session,
        authorization="Bearer token",
    )
    assert res["ok"] is False
    assert "Missing required parameters" in res["error"]
    assert "date" in res["error"]
    assert "session" in res["error"]


def test_execute_tool_legacy_datetime_compatibility():
    """Verify execute_tool unpacks legacy datetime parameter into date and session."""
    session = {
        "conversation_id": "test-c1",
        "patient_id": "pat-1",
        "candidate_doctors": [{"doctor_id": "doc-1", "name": "Dr. Smith", "clinic_name": "Clinic", "clinic_address": "Addr"}],
    }
    res = execute_tool(
        name="propose_book_appointment",
        arguments={
            "doctor_id": "doc-1",
            "datetime": "2026-09-18 at 10:00 AM",
            "symptoms": "Routine Checkup",
        },
        session=session,
        authorization="Bearer token",
    )
    assert res["ok"] is True
    assert "Morning Session" in res["summary"]
    assert "2026-09-18" in res["summary"]


def test_booking_error_mapping():
    """Verify backend error translation for session-based appointment booking."""
    err_full = backend_client.BackendError(400, "SESSION_FULL", "Session is full")
    assert "booking capacity (10 for morning, 5 for evening)" in _booking_error(err_full)

    err_unavail = backend_client.BackendError(400, "SESSION_UNAVAILABLE", "Clinic closed")
    assert "not available for that session/date" in _booking_error(err_unavail)

    err_invalid = backend_client.BackendError(400, "INVALID_SESSION", "Invalid session")
    assert "Please select a valid session" in _booking_error(err_invalid)
