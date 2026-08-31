"""Tests for agentic function-calling chat (no hardcoded state machine)."""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

from app.chatbot import handle_message
from app.tools import TOOL_DEFINITIONS, execute_tool

DOC_ID = str(uuid.uuid4())
PATIENT_ID = str(uuid.uuid4())
OTHER_PATIENT_ID = str(uuid.uuid4())
APPT_ID = str(uuid.uuid4())
SLOT_TS = "2026-09-01T09:00:00+05:00"
SLOT_LABEL = "2026-09-01 at 09:00 AM"

FAKE_DOCTORS = [
    {
        "doctor_id": DOC_ID,
        "name": "Dr. Ahmed Malik",
        "specialization": "Cardiologist",
        "consultation_fee": 2500,
        "clinic_name": "MediBook Central Clinic",
        "clinic_address": "Main Boulevard, Lahore",
        "availability_slots": [
            {
                "date": "2026-09-01",
                "time": "09:00 AM",
                "timestamp": SLOT_TS,
                "label": SLOT_LABEL,
                "status": "available",
            }
        ],
    }
]

FAKE_APPOINTMENTS = [
    {
        "id": APPT_ID,
        "appointment_id": APPT_ID,
        "doctor_id": DOC_ID,
        "doctor_name": "Dr. Ahmed Malik",
        "clinic_name": "MediBook Central Clinic",
        "patient_id": PATIENT_ID,
        "appointment_time": "2026-09-01T09:00:00Z",
        "status": "scheduled",
    }
]


class FakeFn:
    def __init__(self, name: str, arguments):
        self.name = name
        self.arguments = arguments if isinstance(arguments, str) else json.dumps(arguments)


class FakeToolCall:
    def __init__(self, name: str, arguments, call_id: str = "call_1"):
        self.id = call_id
        self.type = "function"
        self.function = FakeFn(name, arguments)


class FakeMessage:
    def __init__(self, content=None, tool_calls=None, role: str = "assistant"):
        self.content = content
        self.tool_calls = tool_calls
        self.role = role


def test_tool_schemas_cover_required_functions():
    names = {spec["function"]["name"] for spec in TOOL_DEFINITIONS}
    assert names == {
        "get_patient_appointments",
        "reschedule_appointment",
        "cancel_appointment",
        "book_appointment",
        "get_doctors_by_specialty",
        "get_availability",
        "get_patient_info",
    }


@patch("app.backend_client.list_doctors", return_value=FAKE_DOCTORS)
@patch("app.backend_client.get_availability", return_value=None)
def test_chest_pain_flow_calls_specialty_availability_then_books(_avail, _docs):
    conv_id = str(uuid.uuid4())
    created = {"appointment_id": APPT_ID, "status": "scheduled"}

    groq_turns = [
        FakeMessage(
            tool_calls=[
                FakeToolCall(
                    "get_doctors_by_specialty",
                    {"specialty": "Cardiologist"},
                    "c1",
                )
            ]
        ),
        FakeMessage(
            tool_calls=[
                FakeToolCall(
                    "get_availability",
                    {"doctor_id": DOC_ID, "date": "2026-09-01"},
                    "c2",
                )
            ]
        ),
        FakeMessage(
            content=(
                "I recommend Dr. Ahmed Malik (Cardiologist). "
                "Shall I book 2026-09-01 at 09:00 AM for your chest pain?"
            )
        ),
    ]

    with patch("app.groq_client.complete_with_tools", side_effect=groq_turns):
        res = handle_message(
            conversation_id=conv_id,
            patient_id=PATIENT_ID,
            message="I have chest pain, book me an appointment",
            language="english",
            authorization="Bearer test-token",
        )

    assert "Ahmed Malik" in res["bot_message"]
    assert "doctors" in (res["ui_data"] or {}) or "slots" in (res["ui_data"] or {})

    groq_confirm = [
        FakeMessage(
            tool_calls=[
                FakeToolCall(
                    "book_appointment",
                    {
                        "patient_id": PATIENT_ID,
                        "doctor_id": DOC_ID,
                        "datetime": SLOT_TS,
                        "symptoms": "chest pain",
                    },
                    "c3",
                )
            ]
        ),
        FakeMessage(content="Your appointment with Dr. Ahmed Malik is confirmed."),
    ]
    with patch("app.backend_client.create_appointment", return_value=created) as mock_create:
        with patch("app.groq_client.complete_with_tools", side_effect=groq_confirm):
            booked = handle_message(
                conversation_id=conv_id,
                patient_id=PATIENT_ID,
                message="Yes, please book it",
                language="english",
                authorization="Bearer test-token",
            )
    mock_create.assert_called_once()
    assert "confirmed" in booked["bot_message"].lower()


@patch("app.backend_client.fetch_patient_appointments", return_value=FAKE_APPOINTMENTS)
@patch("app.backend_client.list_doctors", return_value=FAKE_DOCTORS)
@patch("app.backend_client.get_availability", return_value=None)
def test_reschedule_flow_lists_then_updates(_avail, _docs, _fetch):
    conv_id = str(uuid.uuid4())
    groq_turns = [
        FakeMessage(
            tool_calls=[
                FakeToolCall("get_patient_appointments", {"patient_id": PATIENT_ID}, "r1")
            ]
        ),
        FakeMessage(
            content="You have an appointment with Dr. Ahmed Malik. Confirm moving it to tomorrow 9 AM?"
        ),
    ]
    with patch("app.groq_client.complete_with_tools", side_effect=groq_turns):
        listed = handle_message(
            conversation_id=conv_id,
            patient_id=PATIENT_ID,
            message="Reschedule my appointment to tomorrow",
            language="english",
            authorization="Bearer test-token",
        )
    assert listed["next_action"] == "show_appointments"

    groq_write = [
        FakeMessage(
            tool_calls=[
                FakeToolCall(
                    "reschedule_appointment",
                    {"appointment_id": APPT_ID, "new_datetime": SLOT_TS},
                    "r2",
                )
            ]
        ),
        FakeMessage(content="Your appointment is rescheduled to 2026-09-01 at 09:00 AM."),
    ]
    with patch("app.backend_client.reschedule_appointment", return_value={"status": "scheduled"}) as mock_rs:
        with patch("app.groq_client.complete_with_tools", side_effect=groq_write):
            done = handle_message(
                conversation_id=conv_id,
                patient_id=PATIENT_ID,
                message="Yes, confirm the new time",
                language="english",
                authorization="Bearer test-token",
            )
    mock_rs.assert_called_once()
    assert "reschedule" in done["bot_message"].lower()


@patch("app.backend_client.list_doctors", return_value=FAKE_DOCTORS)
@patch("app.backend_client.get_availability", return_value=None)
def test_what_doctors_are_available_uses_tools(_avail, _docs):
    groq_turns = [
        FakeMessage(
            tool_calls=[
                FakeToolCall("get_doctors_by_specialty", {"specialty": "General Physician"}, "d1"),
                FakeToolCall("get_availability", {"doctor_id": DOC_ID, "date": "2026-09-01"}, "d2"),
            ]
        ),
        FakeMessage(content="Dr. Ahmed Malik has an opening at 09:00 AM."),
    ]
    with patch("app.groq_client.complete_with_tools", side_effect=groq_turns):
        res = handle_message(
            conversation_id=str(uuid.uuid4()),
            patient_id=PATIENT_ID,
            message="What doctors are available?",
            language="english",
            authorization="Bearer test-token",
        )
    assert "Ahmed Malik" in res["bot_message"] or "09:00" in res["bot_message"]


def test_cancel_rejects_other_patients_appointment():
    session = {
        "patient_id": OTHER_PATIENT_ID,
        "last_ui_data": {},
        "patient_appointments": FAKE_APPOINTMENTS,
    }
    result = execute_tool(
        "cancel_appointment",
        {"appointment_id": APPT_ID},
        session,
        "Bearer test-token",
    )
    assert result["ok"] is False
    assert "does not belong" in result["error"].lower() or "not found" in result["error"].lower()


def test_execute_unknown_tool():
    result = execute_tool("explode_clinic", {}, {"last_ui_data": {}}, None)
    assert result["ok"] is False
    assert "Unknown tool" in result["error"]


def test_no_handle_lookup_or_state_machine_modules():
    import importlib
    import pkgutil
    import app

    names = {m.name for m in pkgutil.iter_modules(app.__path__)}
    assert "chatbot_handlers" not in names
    assert "chatbot_state" not in names
    chatbot = importlib.import_module("app.chatbot")
    source = open(chatbot.__file__, encoding="utf-8").read()
    assert "handle_lookup" not in source
    assert "handle_reschedule" not in source
    assert "pending_action" not in source
    assert "_run_agent_fallback" not in source
