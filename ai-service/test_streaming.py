import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.chatbot import TOOL_FRIENDLY_LABELS, handle_message_stream, new_session
from app.main import app
from fastapi.testclient import TestClient


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


def test_tool_friendly_labels_mapping():
    """Verify all required tool names map to human-friendly labels."""
    expected_mappings = {
        "list_doctors": "Looking up available doctors...",
        "get_doctors_by_specialty": "Looking up available doctors...",
        "get_doctor_availability": "Checking availability...",
        "get_availability": "Checking availability...",
        "get_patient_appointments": "Checking your appointments...",
        "search_patient_appointments": "Checking your appointments...",
        "get_clinic_info": "Getting clinic information...",
        "get_patient_info": "Getting clinic information...",
        "retrieve_medical_knowledge": "Looking into that for you...",
        "propose_book_appointment": "Preparing your booking...",
        "propose_reschedule_appointment": "Preparing your reschedule...",
        "propose_cancel_appointment": "Preparing your cancellation...",
        "execute_confirmed_action": "Confirming your appointment...",
    }
    for tool_name, expected_label in expected_mappings.items():
        assert TOOL_FRIENDLY_LABELS.get(tool_name) == expected_label


def test_streaming_emits_status_events_for_two_tool_calls():
    """Verify intermediate status events are emitted in sequence before the final response."""
    conv_id = "test-stream-conv-1"

    # Round 1: calls get_doctors_by_specialty
    # Round 2: calls get_availability
    # Round 3: final text reply
    mock_responses = [
        FakeMessage(tool_calls=[FakeToolCall("tc1", "get_doctors_by_specialty", '{"specialty": "Cardiology"}')]),
        FakeMessage(tool_calls=[FakeToolCall("tc2", "get_availability", '{"doctor_id": "doc1"}')]),
        FakeMessage(tool_calls=[], content="Dr. Ahmed is available on Monday at 10:00 AM."),
    ]

    mock_execute_results = [
        {"ok": True, "doctors": [{"id": "doc1", "name": "Dr. Ahmed"}], "ui_data": {"doctors": []}},
        {"ok": True, "slots": ["10:00 AM"], "ui_data": {"slots": []}},
    ]

    with patch("app.chatbot.groq_client.complete_with_tools", side_effect=mock_responses) as mock_groq, \
         patch("app.chatbot.execute_tool", side_effect=mock_execute_results) as mock_exec:

        events = list(handle_message_stream(
            conversation_id=conv_id,
            patient_id=None,
            message="I need a cardiologist for Monday",
            language="english",
            authorization=None,
        ))

        # Parse SSE events
        parsed_events = []
        for raw in events:
            lines = raw.strip().split("\n")
            ev_type = ""
            data_str = ""
            for line in lines:
                if line.startswith("event:"):
                    ev_type = line.replace("event:", "").strip()
                elif line.startswith("data:"):
                    data_str = line.replace("data:", "").strip()
            if ev_type and data_str:
                parsed_events.append((ev_type, json.loads(data_str)))

        # Expect at least 3 events: status (doctor lookup), status (availability check), final
        assert len(parsed_events) >= 3

        # First tool status event
        assert parsed_events[0][0] == "status"
        assert parsed_events[0][1]["label"] == "Looking up available doctors..."
        # Ensure no raw tool name or arguments are exposed
        assert "tool_name" not in parsed_events[0][1]
        assert "arguments" not in parsed_events[0][1]
        assert "get_doctors_by_specialty" not in json.dumps(parsed_events[0][1])

        # Second tool status event
        assert parsed_events[1][0] == "status"
        assert parsed_events[1][1]["label"] == "Checking availability..."
        assert "get_availability" not in json.dumps(parsed_events[1][1])

        # Final event
        assert parsed_events[2][0] == "final"
        final_data = parsed_events[2][1]
        assert "bot_message" in final_data
        assert "Dr. Ahmed is available" in final_data["bot_message"]
        assert "conversation_id" in final_data
        assert final_data["conversation_id"] == conv_id


def test_streaming_api_endpoint_with_stream_flag():
    """Verify POST /api/chat/message with stream=True returns SSE response."""
    client = TestClient(app)

    mock_responses = [
        FakeMessage(tool_calls=[FakeToolCall("tc1", "get_patient_appointments", "{}")]),
        FakeMessage(tool_calls=[], content="You have one appointment scheduled."),
    ]

    with patch("app.chatbot.groq_client.complete_with_tools", side_effect=mock_responses), \
         patch("app.chatbot.execute_tool", return_value={"ok": True, "appointments": []}):

        response = client.post(
            "/api/chat/message",
            json={"message": "what are my appointments?", "stream": True},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        body_text = response.text
        assert "event: status" in body_text
        assert "Checking your appointments..." in body_text
        assert "event: final" in body_text
        assert "You have one appointment scheduled." in body_text


def test_streaming_error_handling_mid_stream():
    """Verify that an unexpected failure mid-stream emits an error event without crashing."""
    conv_id = "test-error-conv"

    with patch("app.chatbot.run_agent_loop_stream", side_effect=RuntimeError("Groq timeout")):
        events = list(handle_message_stream(
            conversation_id=conv_id,
            patient_id=None,
            message="Hello",
            language="english",
            authorization=None,
        ))

        assert len(events) == 1
        assert "event: error" in events[0]
        assert "Our AI assistant encountered an issue" in events[0]
