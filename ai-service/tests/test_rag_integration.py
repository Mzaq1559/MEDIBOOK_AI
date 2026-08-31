"""Integration tests for chatbot flows with the agent loop."""

from __future__ import annotations

import json
from unittest.mock import patch

from app.chatbot import get_session, handle_message, new_session
from app.symptom_triage import EMERGENCY_ALERT

FAKE_DOCTORS = [
    {
        "doctor_id": "doc-123",
        "name": "Dr. Sarah Khan",
        "specialization": "General Physician",
        "consultation_fee": 2000,
        "clinic_name": "MediBook Central Clinic",
        "clinic_address": "Main Boulevard, Lahore",
        "availability_slots": [
            {
                "timestamp": "2026-09-01T09:00:00+05:00",
                "label": "Sep 01, 2026 at 09:00 AM",
                "date": "2026-09-01",
                "time": "09:00 AM",
                "status": "available",
            }
        ],
    }
]


class FakeFn:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments if isinstance(arguments, str) else json.dumps(arguments)


class FakeToolCall:
    def __init__(self, name, arguments, call_id="call_1"):
        self.id = call_id
        self.type = "function"
        self.function = FakeFn(name, arguments)


class FakeMessage:
    def __init__(self, content=None, tool_calls=None, role="assistant"):
        self.content = content
        self.tool_calls = tool_calls
        self.role = role


def _start_booking(conversation_id: str = "test-conv-1"):
    groq = [
        FakeMessage(
            tool_calls=[FakeToolCall("get_doctors_by_specialty", {"specialty": "General Physician"})]
        ),
        FakeMessage(content="Please select a doctor to book your appointment."),
    ]
    with patch("app.backend_client.list_doctors", return_value=FAKE_DOCTORS):
        with patch("app.backend_client.get_availability", return_value=None):
            with patch("app.groq_client.complete_with_tools", side_effect=groq):
                handle_message(
                    conversation_id=conversation_id,
                    patient_id=None,
                    message="I want to book an appointment",
                    language="english",
                    authorization=None,
                )
    return conversation_id


def test_booking_flow_starts_without_hardcoded_router():
    conv_id = _start_booking("booking-flow-1")
    session = get_session(conv_id)
    assert session is not None
    assert "doctors" in session["last_ui_data"]


def test_symptom_message_uses_agent_reply():
    groq = [FakeMessage(content="ENT guidance for sore throat. I can show ENT specialists if you want to book.")]
    result = None
    with patch("app.groq_client.complete_with_tools", side_effect=groq):
        result = handle_message(
            conversation_id="rag-symptom-1",
            patient_id=None,
            message="I've had a sore throat and cough for two days.",
            language="english",
            authorization=None,
        )
    assert "ENT guidance" in result["bot_message"]
    assert result["next_action"] == "waiting_for_input"


def test_emergency_overrides_agent_and_booking():
    result = handle_message(
        conversation_id="emergency-1",
        patient_id=None,
        message="I have severe chest pain and I cannot breathe properly.",
        language="english",
        authorization=None,
    )
    assert result["next_action"] == "emergency_redirect"
    assert "EMERGENCY" in result["bot_message"]


def test_cancel_intent_uses_appointment_tool():
    groq = [
        FakeMessage(
            tool_calls=[
                FakeToolCall(
                    "get_patient_appointments",
                    {"patient_id": "33333333-3333-4333-a333-333333333333"},
                )
            ]
        ),
        FakeMessage(content="Please log in or tell me which appointment to cancel."),
    ]
    with patch("app.groq_client.complete_with_tools", side_effect=groq):
        result = handle_message(
            conversation_id="cancel-1",
            patient_id="33333333-3333-4333-a333-333333333333",
            message="cancel my appointment",
            language="english",
            authorization="Bearer fake-token",
        )
    assert "cancel" in result["bot_message"].lower() or result["next_action"] in (
        "waiting_for_login",
        "show_appointments",
        "waiting_for_input",
    )


def test_reschedule_intent_uses_appointment_tool():
    groq = [
        FakeMessage(
            tool_calls=[
                FakeToolCall(
                    "get_patient_appointments",
                    {"patient_id": "33333333-3333-4333-a333-333333333333"},
                )
            ]
        ),
        FakeMessage(content="I can reschedule once I load your appointments."),
    ]
    with patch("app.backend_client.fetch_patient_appointments", return_value=[]):
        with patch("app.groq_client.complete_with_tools", side_effect=groq):
            result = handle_message(
                conversation_id="reschedule-1",
                patient_id="33333333-3333-4333-a333-333333333333",
                message="reschedule my appointment",
                language="english",
                authorization="Bearer fake-token",
            )
    assert result["next_action"] in (
        "waiting_for_login",
        "show_appointments",
        "waiting_for_input",
        "waiting_for_new_time",
        "waiting_for_reschedule_confirm",
    )


def test_new_session_helper_still_works():
    session = new_session("sess-1", "patient-1")
    assert get_session("sess-1") is session
    assert session["patient_id"] == "patient-1"
