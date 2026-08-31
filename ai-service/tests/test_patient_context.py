"""Patient context injection and receptionist-style system prompt."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from app.chatbot import handle_message
from app.patient_context import (
    build_patient_context_block,
    first_name,
    format_visit_when,
    load_patient_context,
)
from app.tools import build_system_prompt
from tests.test_agentic_tools import FakeMessage, PATIENT_ID


def test_first_name_handles_western_and_comma_order():
    assert first_name("Ali Khan") == "Ali"
    assert first_name("Khan, Ali") == "Ali"
    assert first_name("Fatima") == "Fatima"
    assert first_name("") == ""


def test_format_visit_when_is_conversational():
    assert format_visit_when("2026-08-27T10:00:00+05:00") == "August 27th at 10 AM"
    assert "August 27th" in format_visit_when("2026-08-27T10:00:00Z")


def test_patient_context_block_includes_history_and_language():
    block = build_patient_context_block(
        full_name="Ali Khan",
        given_name="Ali",
        last_visits=[
            {
                "date": "August 27th at 10 AM",
                "doctor": "Dr. Tariq Mahmood",
                "symptoms": "head issue",
                "clinic": "City Health Clinic",
                "status": "completed",
            }
        ],
        chronic_conditions=["migraine"],
        allergies=["penicillin"],
        preferred_doctor="Dr. Tariq Mahmood",
        preferred_clinic="City Health Clinic",
        language="urdu",
        conversation_history="- user: What are my appointments?",
    )
    assert "Patient: Ali Khan" in block
    assert "First name: Ali" in block
    assert "Last visit: August 27th at 10 AM with Dr. Tariq Mahmood" in block
    assert "Symptoms: head issue" in block
    assert "Chronic conditions: migraine" in block
    assert "Allergies / special notes: penicillin" in block
    assert "Language preference: urdu" in block
    assert "Preferred doctor: Dr. Tariq Mahmood" in block
    assert "What are my appointments?" in block


def test_system_prompt_is_receptionist_not_report():
    prompt = build_system_prompt()
    assert "experienced healthcare receptionist" in prompt
    assert "1-2 sentences max" in prompt
    assert "Hi Ali! You have an appointment with Dr. Tariq on Aug 27th at 10 AM." in prompt
    assert "When works best for you?" in prompt
    assert "Want to reschedule instead?" in prompt
    assert "Never write labeled fields" in prompt
    assert "Do NOT use markdown symbols (**) in responses." in prompt
    assert "Date & Time: 27 August 2026 at 10:00 AM" not in prompt


def test_load_patient_context_fetches_profile_and_last_visits():
    session = {
        "patient_id": PATIENT_ID,
        "messages": [{"role": "user", "message": "What are my appointments?"}],
    }
    profile = {
        "name": "Ali Khan",
        "medical_conditions": ["hypertension"],
        "allergies": ["dust"],
    }
    visits = [
        {
            "doctor_name": "Dr. Tariq Mahmood",
            "appointment_time": "2026-08-01T09:00:00+05:00",
            "symptoms_reported": "head issue",
            "clinic_name": "City Health Clinic",
            "status": "completed",
        },
        {
            "doctor_name": "Dr. Tariq Mahmood",
            "appointment_time": "2026-08-27T10:00:00+05:00",
            "symptoms_reported": "follow-up",
            "clinic_name": "City Health Clinic",
            "status": "scheduled",
        },
    ]
    with patch("app.backend_client.get_patient_info", return_value=profile):
        with patch("app.backend_client.fetch_patient_appointments", return_value=visits) as fetch:
            block = load_patient_context(session, "Bearer test-token", "english")
    fetch.assert_called_once()
    assert fetch.call_args.kwargs.get("status_filter") == "" or fetch.call_args[1].get("status_filter") == ""
    assert "First name: Ali" in block
    assert "Dr. Tariq Mahmood" in block
    assert "head issue" in block or "follow-up" in block
    assert "hypertension" in block
    assert session["patient_first_name"] == "Ali"


@patch("app.backend_client.get_patient_info", return_value={"name": "Ali Khan", "medical_conditions": ["chest concerns"], "allergies": []})
@patch(
    "app.backend_client.fetch_patient_appointments",
    return_value=[
        {
            "doctor_name": "Dr. Tariq Mahmood",
            "appointment_time": "2026-08-10T11:00:00+05:00",
            "symptoms_reported": "chest concerns",
            "clinic_name": "City Health Clinic",
            "status": "completed",
        }
    ],
)
def test_llm_receives_patient_context_before_reply(_fetch, _info):
    groq_turns = [
        FakeMessage(content="Hi Ali! You have one appointment with Dr. Tariq on Aug 27th at 10 AM."),
    ]
    captured = {}

    def capture(messages=None, tools=None, tool_choice=None, temperature=None):
        captured["messages"] = messages
        return groq_turns.pop(0)

    with patch("app.groq_client.complete_with_tools", side_effect=capture):
        res = handle_message(
            conversation_id=str(uuid.uuid4()),
            patient_id=PATIENT_ID,
            message="What are my appointments?",
            language="english",
            authorization="Bearer test-token",
        )
    system_blobs = "\n".join(m["content"] for m in captured["messages"] if m["role"] == "system")
    assert "experienced healthcare receptionist" in system_blobs
    assert "First name: Ali" in system_blobs
    assert "chest concerns" in system_blobs
    assert res["bot_message"] == "Hi Ali! You have one appointment with Dr. Tariq on Aug 27th at 10 AM."
    assert "Doctor:" not in res["bot_message"]
    assert "Patient Name:" not in res["bot_message"]


@patch("app.backend_client.get_patient_info", return_value={"name": "Ali Khan"})
@patch("app.backend_client.fetch_patient_appointments", return_value=[])
def test_conversational_cancel_and_cardiologist_replies(_fetch, _info):
    with patch(
        "app.groq_client.complete_with_tools",
        return_value=FakeMessage(content="Sure, I'll cancel that appointment with Dr. Tariq."),
    ):
        cancel = handle_message(
            conversation_id=str(uuid.uuid4()),
            patient_id=PATIENT_ID,
            message="I want to cancel",
            language="english",
            authorization="Bearer test-token",
        )
    assert cancel["bot_message"] == "Sure, I'll cancel that appointment with Dr. Tariq."
    assert "Please confirm cancellation" not in cancel["bot_message"]

    with patch(
        "app.groq_client.complete_with_tools",
        return_value=FakeMessage(
            content="Got it, Ali. I see you had chest concerns before. Let me find our best cardiologist."
        ),
    ):
        book = handle_message(
            conversation_id=str(uuid.uuid4()),
            patient_id=PATIENT_ID,
            message="Book me with a cardiologist",
            language="english",
            authorization="Bearer test-token",
        )
    assert "Got it, Ali" in book["bot_message"]
    assert "chest concerns" in book["bot_message"]
