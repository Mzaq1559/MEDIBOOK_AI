"""Tests for plain-text chat replies and appointment listing without duplicate cards."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from app.chatbot import handle_message
from app.response_format import lists_appointment_details, strip_markdown
from app.tools import build_system_prompt
from tests.test_agentic_tools import (
    FAKE_APPOINTMENTS,
    PATIENT_ID,
    FakeMessage,
    FakeToolCall,
)

MARKDOWN_LISTING = (
    "I see you have one upcoming appointment:\n"
    "**Doctor:** Dr. Tariq Mahmood\n"
    "**Date & Time:** 27 August 2026 at 10:00 AM\n"
    "**Clinic:** City Health Clinic\n"
    "**Reason noted:** head burnt yesterday no worse\n"
    "Would you like me to cancel this appointment for you?"
)

PLAIN_LISTING = (
    "I see you have one upcoming appointment:\n"
    "Doctor: Dr. Tariq Mahmood\n"
    "Date & Time: 27 August 2026 at 10:00 AM\n"
    "Clinic: City Health Clinic\n"
    "Reason noted: head burnt yesterday no worse\n"
    "Would you like me to cancel this appointment for you?"
)


def test_strip_markdown_removes_bold_and_headings():
    raw = "## Summary\n**Doctor:** Dr. Tariq Mahmood"
    assert strip_markdown(raw) == (
        "Summary\nDoctor: Dr. Tariq Mahmood"
    )
    assert "**" not in strip_markdown(raw)
    assert "##" not in strip_markdown(raw)


def test_lists_appointment_details_detects_inline_fields():
    assert lists_appointment_details(MARKDOWN_LISTING) is True
    assert lists_appointment_details("You have one upcoming visit.") is False


def test_system_prompt_forbids_markdown_and_uses_conversational_tone():
    prompt = build_system_prompt()
    assert "Do NOT use markdown symbols (**) in responses." in prompt
    assert "experienced healthcare receptionist" in prompt
    assert "Hi Ali! You have an appointment with Dr. Tariq on Aug 27th at 10 AM." in prompt
    assert "Never write labeled fields" in prompt
    assert "Date & Time: 27 August 2026 at 10:00 AM" not in prompt


@patch("app.backend_client.fetch_patient_appointments", return_value=FAKE_APPOINTMENTS)
def test_what_are_my_appointments_is_plain_text_without_duplicate_cards(_fetch):
    groq_turns = [
        FakeMessage(
            tool_calls=[
                FakeToolCall("get_patient_appointments", {"patient_id": PATIENT_ID}, "a1")
            ]
        ),
        FakeMessage(content=MARKDOWN_LISTING),
    ]
    with patch("app.groq_client.complete_with_tools", side_effect=groq_turns):
        res = handle_message(
            conversation_id=str(uuid.uuid4()),
            patient_id=PATIENT_ID,
            message="What are my appointments?",
            language="english",
            authorization="Bearer test-token",
        )
    assert res["bot_message"] == PLAIN_LISTING
    assert "**" not in res["bot_message"]
    assert not (res.get("ui_data") or {}).get("appointments")


@patch("app.backend_client.fetch_patient_appointments", return_value=FAKE_APPOINTMENTS)
def test_cancel_my_appointment_asks_confirmation_without_markdown(_fetch):
    groq_turns = [
        FakeMessage(
            tool_calls=[
                FakeToolCall("get_patient_appointments", {"patient_id": PATIENT_ID}, "c1")
            ]
        ),
        FakeMessage(
            content=(
                "I can cancel this visit for you.\n"
                "**Doctor:** Dr. Ahmed Malik\n"
                "**Date & Time:** 1 September 2026 at 09:00 AM\n"
                "**Clinic:** MediBook Central Clinic\n"
                "Would you like me to cancel this appointment?"
            )
        ),
    ]
    with patch("app.groq_client.complete_with_tools", side_effect=groq_turns):
        res = handle_message(
            conversation_id=str(uuid.uuid4()),
            patient_id=PATIENT_ID,
            message="Cancel my appointment",
            language="english",
            authorization="Bearer test-token",
        )
    assert "**" not in res["bot_message"]
    assert "Doctor: Dr. Ahmed Malik" in res["bot_message"]
    assert "cancel" in res["bot_message"].lower()
    assert not (res.get("ui_data") or {}).get("appointments")


@patch("app.backend_client.fetch_patient_appointments", return_value=FAKE_APPOINTMENTS)
def test_reschedule_shows_current_details_and_asks_for_new_time(_fetch):
    groq_turns = [
        FakeMessage(
            tool_calls=[
                FakeToolCall("get_patient_appointments", {"patient_id": PATIENT_ID}, "r1")
            ]
        ),
        FakeMessage(
            content=(
                "Here is your current appointment.\n"
                "**Doctor:** Dr. Ahmed Malik\n"
                "**Date & Time:** 1 September 2026 at 09:00 AM\n"
                "**Clinic:** MediBook Central Clinic\n"
                "What new time would you like?"
            )
        ),
    ]
    with patch("app.groq_client.complete_with_tools", side_effect=groq_turns):
        res = handle_message(
            conversation_id=str(uuid.uuid4()),
            patient_id=PATIENT_ID,
            message="Reschedule",
            language="english",
            authorization="Bearer test-token",
        )
    assert "**" not in res["bot_message"]
    assert "Doctor: Dr. Ahmed Malik" in res["bot_message"]
    assert "new time" in res["bot_message"].lower()
    assert not (res.get("ui_data") or {}).get("appointments")
