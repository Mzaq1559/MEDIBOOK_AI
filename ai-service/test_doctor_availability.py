import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.chatbot import handle_message, handle_message_stream, new_session, get_session
from app.tools import execute_tool, HANDLERS, REQUIRED_PARAMS


class FakeToolCall:
    def __init__(self, id: str, name: str, arguments: str = "{}"):
        self.id = id
        self.function = MagicMock()
        self.function.name = name
        self.function.arguments = arguments


class FakeMessage:
    def __init__(self, tool_calls=None, content=""):
        self.role = "assistant"
        self.tool_calls = tool_calls or []
        self.content = content


def test_get_doctor_availability_handler_registration():
    """Verify get_doctor_availability is registered in HANDLERS and REQUIRED_PARAMS."""
    assert "get_doctor_availability" in HANDLERS
    assert "get_doctor_availability" in REQUIRED_PARAMS


def test_doctor_availability_clears_stale_doctors_list():
    """Verify turn 2 (get_doctor_availability) emits slots ui_data, clears doctors list, and sets next_action to waiting_for_slot_selection."""
    conv_id = "test-avail-conv-1"
    session = new_session(conv_id, "patient-1")

    # Turn 1: user asks for cardiologists -> agent calls get_doctors_by_specialty
    mock_responses_t1 = [
        FakeMessage(tool_calls=[FakeToolCall("tc1", "get_doctors_by_specialty", '{"specialty": "Cardiology"}')]),
        FakeMessage(tool_calls=[], content="Here are our available cardiologists: Dr. Fatima Zahra, Dr. Ahmed Khan."),
    ]
    mock_exec_t1 = [
        {
            "ok": True,
            "doctors": [
                {"doctor_id": "doc-fatima", "name": "Dr. Fatima Zahra", "specialization": "Cardiology"},
                {"doctor_id": "doc-ahmed", "name": "Dr. Ahmed Khan", "specialization": "Cardiology"},
            ],
            "ui_data": {
                "doctors": [
                    {"doctor_id": "doc-fatima", "name": "Dr. Fatima Zahra", "specialization": "Cardiology"},
                    {"doctor_id": "doc-ahmed", "name": "Dr. Ahmed Khan", "specialization": "Cardiology"},
                ]
            },
        }
    ]

    with patch("app.chatbot.groq_client.complete_with_tools", side_effect=mock_responses_t1), \
         patch("app.chatbot.execute_tool", side_effect=mock_exec_t1):

        res_t1 = handle_message(
            conversation_id=conv_id,
            patient_id="patient-1",
            message="book me with a cardiologist",
            language="english",
            authorization=None,
        )

        assert res_t1["next_action"] == "waiting_for_doctor_selection"
        assert "doctors" in res_t1["ui_data"]
        assert len(res_t1["ui_data"]["doctors"]) == 2

    # Turn 2: user asks for Dr. Fatima Zahra's availability -> agent calls get_doctor_availability
    mock_responses_t2 = [
        FakeMessage(tool_calls=[FakeToolCall("tc2", "get_doctor_availability", '{"doctor_id": "doc-fatima", "date": "2026-09-04"}')]),
        FakeMessage(tool_calls=[], content="Dr. Fatima Zahra has open slots on September 4th at 13:30, 14:00, 14:30. Which time works best?"),
    ]
    mock_exec_t2 = [
        {
            "ok": True,
            "doctor_id": "doc-fatima",
            "date": "2026-09-04",
            "slots": ["2026-09-04 at 13:30", "2026-09-04 at 14:00"],
            "timestamps": ["2026-09-04T13:30:00Z", "2026-09-04T14:00:00Z"],
            "ui_data": {
                "slots": [
                    {"date": "2026-09-04", "time": "13:30", "timestamp": "2026-09-04T13:30:00Z", "label": "2026-09-04 at 13:30"},
                    {"date": "2026-09-04", "time": "14:00", "timestamp": "2026-09-04T14:00:00Z", "label": "2026-09-04 at 14:00"},
                ]
            },
        }
    ]

    with patch("app.chatbot.groq_client.complete_with_tools", side_effect=mock_responses_t2), \
         patch("app.chatbot.execute_tool", side_effect=mock_exec_t2):

        res_t2 = handle_message(
            conversation_id=conv_id,
            patient_id="patient-1",
            message="check Dr. Fatima Zahra availability",
            language="english",
            authorization=None,
        )

        assert res_t2["next_action"] == "waiting_for_slot_selection"
        assert "slots" in res_t2["ui_data"]
        assert len(res_t2["ui_data"]["slots"]) == 2
        assert "doctors" not in res_t2["ui_data"]
