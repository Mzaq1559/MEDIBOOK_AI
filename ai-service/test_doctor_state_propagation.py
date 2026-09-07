import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.chatbot import handle_message, new_session, get_session


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


def test_doctor_state_propagation_bug_scenario():
    """Scenario 1: Patient has historical preferred doctor Dr. Ahmed Khan.

    Turn 1 returns Dr. Tariq Mahmood.
    Turn 2 confirms booking.
    Assert active selected doctor is Dr. Tariq Mahmood with UUID injected into prompt,
    and propose_book_appointment receives Dr. Tariq Mahmood's UUID.
    """
    conv_id = "test-prop-conv-1"
    patient_id = "pat-ali-123"

    mock_patient_info = {
        "name": "Ali Khan",
        "phone": "+923001234567",
        "medical_conditions": ["Hypertension"],
        "allergies": ["Penicillin"],
    }
    mock_appts = [
        {
            "id": "appt-old-1",
            "doctor_name": "Dr. Ahmed Khan",
            "clinic_name": "City Health Clinic",
            "appointment_time": "2026-08-10T10:00:00Z",
            "symptoms_reported": "Routine checkup",
            "status": "completed",
        }
    ]

    t1_groq_resp = [
        FakeMessage(tool_calls=[FakeToolCall("tc1", "get_doctors_by_specialty", '{"specialty": "General Medicine"}')]),
        FakeMessage(tool_calls=[], content="I recommend Dr. Tariq Mahmood at City Health Clinic. Would you like to book an appointment with him?"),
    ]
    t1_tool_exec = [
        {
            "ok": True,
            "doctors": [
                {
                    "doctor_id": "doc-tariq-uuid",
                    "name": "Dr. Tariq Mahmood",
                    "specialization": "General Medicine",
                    "clinic_name": "City Health Clinic",
                    "consultation_fee": 2000,
                    "available_slots": ["2026-09-08 at 10:00 AM"],
                }
            ],
            "ui_data": {
                "doctors": [
                    {
                        "doctor_id": "doc-tariq-uuid",
                        "name": "Dr. Tariq Mahmood",
                        "specialization": "General Medicine",
                        "clinic_name": "City Health Clinic",
                    }
                ]
            },
        }
    ]

    t1_groq_calls = []

    def mock_complete_t1(messages, tools, tool_choice, temperature):
        t1_groq_calls.append(messages)
        return t1_groq_resp[len(t1_groq_calls) - 1]

    with patch("app.patient_context.backend_client.get_patient_info", return_value=mock_patient_info), \
         patch("app.patient_context.backend_client.fetch_patient_appointments", return_value=mock_appts), \
         patch("app.chatbot.groq_client.complete_with_tools", side_effect=mock_complete_t1), \
         patch("app.chatbot.execute_tool", side_effect=t1_tool_exec):

        handle_message(
            conversation_id=conv_id,
            patient_id=patient_id,
            message="I need to see a doctor for chest pain",
            language="english",
            authorization="Bearer test-token",
        )

    session = get_session(conv_id)
    assert session is not None
    assert session.get("selected_doctor") is not None
    assert session["selected_doctor"]["doctor_id"] == "doc-tariq-uuid"

    # Turn 2: user says "yes, book with him tomorrow at 10am"
    t2_groq_resp = [
        FakeMessage(tool_calls=[FakeToolCall("tc2", "propose_book_appointment", '{"patient_id": "pat-ali-123", "doctor_id": "doc-tariq-uuid", "datetime": "2026-09-08 at 10:00 AM", "symptoms": "chest pain"}')]),
        FakeMessage(tool_calls=[], content="I have prepared your appointment proposal with Dr. Tariq Mahmood for tomorrow at 10:00 AM. Please confirm if you'd like me to proceed."),
    ]
    t2_tool_exec = [
        {
            "ok": True,
            "proposal_id": "prop-123",
            "summary": "Book appointment with Dr. Tariq Mahmood on 2026-09-08 at 10:00 AM.",
            "ui_data": {
                "booking": {
                    "doctor": {
                        "doctor_id": "doc-tariq-uuid",
                        "name": "Dr. Tariq Mahmood",
                    },
                    "selectedSlot": "2026-09-08 at 10:00 AM",
                    "isConfirmed": False,
                }
            },
        }
    ]

    t2_groq_calls = []

    def mock_complete_t2(messages, tools, tool_choice, temperature):
        t2_groq_calls.append(messages)
        return t2_groq_resp[len(t2_groq_calls) - 1]

    with patch("app.patient_context.backend_client.get_patient_info", return_value=mock_patient_info), \
         patch("app.patient_context.backend_client.fetch_patient_appointments", return_value=mock_appts), \
         patch("app.chatbot.groq_client.complete_with_tools", side_effect=mock_complete_t2), \
         patch("app.chatbot.execute_tool", side_effect=t2_tool_exec):

        handle_message(
            conversation_id=conv_id,
            patient_id=patient_id,
            message="yes, book with him tomorrow at 10am",
            language="english",
            authorization="Bearer test-token",
        )

    # Assert active selected doctor is Dr. Tariq Mahmood
    assert session["selected_doctor"]["doctor_id"] == "doc-tariq-uuid"

    # Assert Dr. Tariq Mahmood's UUID was injected into the prompt messages in Turn 2
    prompt_messages = t2_groq_calls[0]
    system_contents = [m["content"] for m in prompt_messages if m.get("role") == "system"]
    active_doc_system_msg = next((c for c in system_contents if "Active doctor selected for booking" in c), None)
    assert active_doc_system_msg is not None
    assert "doc-tariq-uuid" in active_doc_system_msg
    assert "Dr. Tariq Mahmood" in active_doc_system_msg

    # Assert propose_book_appointment received Dr. Tariq Mahmood's UUID (doc-tariq-uuid)
    first_t2_call = t2_groq_resp[0].tool_calls[0]
    args = json.loads(first_t2_call.function.arguments)
    assert args["doctor_id"] == "doc-tariq-uuid"


def test_doctor_state_propagation_no_history():
    """Scenario 2: Patient with NO appointment history.

    Verifies candidate/selected doctor state propagation without regression.
    """
    conv_id = "test-prop-conv-2"
    patient_id = "pat-new-456"

    mock_patient_info = {"name": "Sara Ahmed", "phone": "+923009876543"}
    mock_appts = []

    t1_groq_resp = [
        FakeMessage(tool_calls=[FakeToolCall("tc1", "get_doctors_by_specialty", '{"specialty": "Cardiology"}')]),
        FakeMessage(tool_calls=[], content="Dr. Fatima Zahra is available for cardiology consultations."),
    ]
    t1_tool_exec = [
        {
            "ok": True,
            "doctors": [
                {
                    "doctor_id": "doc-fatima-uuid",
                    "name": "Dr. Fatima Zahra",
                    "specialization": "Cardiology",
                    "clinic_name": "Heart Center",
                }
            ],
            "ui_data": {
                "doctors": [
                    {
                        "doctor_id": "doc-fatima-uuid",
                        "name": "Dr. Fatima Zahra",
                    }
                ]
            },
        }
    ]

    t1_groq_calls = []

    def mock_complete_t1(messages, tools, tool_choice, temperature):
        t1_groq_calls.append(messages)
        return t1_groq_resp[len(t1_groq_calls) - 1]

    with patch("app.patient_context.backend_client.get_patient_info", return_value=mock_patient_info), \
         patch("app.patient_context.backend_client.fetch_patient_appointments", return_value=mock_appts), \
         patch("app.chatbot.groq_client.complete_with_tools", side_effect=mock_complete_t1), \
         patch("app.chatbot.execute_tool", side_effect=t1_tool_exec):

        handle_message(
            conversation_id=conv_id,
            patient_id=patient_id,
            message="I need a cardiologist",
            language="english",
            authorization="Bearer test-token",
        )

    session = get_session(conv_id)
    assert session is not None
    assert session.get("selected_doctor") is not None
    assert session["selected_doctor"]["doctor_id"] == "doc-fatima-uuid"

    # Turn 2: check availability
    t2_groq_resp = [
        FakeMessage(tool_calls=[FakeToolCall("tc2", "get_doctor_availability", '{"doctor_id": "doc-fatima-uuid", "date": "2026-09-08"}')]),
        FakeMessage(tool_calls=[], content="Dr. Fatima Zahra has slots at 11:00 AM."),
    ]
    t2_tool_exec = [
        {
            "ok": True,
            "doctor_id": "doc-fatima-uuid",
            "slots": ["2026-09-08 at 11:00"],
            "ui_data": {"slots": [{"label": "2026-09-08 at 11:00"}]},
        }
    ]

    t2_groq_calls = []

    def mock_complete_t2(messages, tools, tool_choice, temperature):
        t2_groq_calls.append(messages)
        return t2_groq_resp[len(t2_groq_calls) - 1]

    with patch("app.patient_context.backend_client.get_patient_info", return_value=mock_patient_info), \
         patch("app.patient_context.backend_client.fetch_patient_appointments", return_value=mock_appts), \
         patch("app.chatbot.groq_client.complete_with_tools", side_effect=mock_complete_t2), \
         patch("app.chatbot.execute_tool", side_effect=t2_tool_exec):

        handle_message(
            conversation_id=conv_id,
            patient_id=patient_id,
            message="when is she free?",
            language="english",
            authorization="Bearer test-token",
        )

    assert session["selected_doctor"]["doctor_id"] == "doc-fatima-uuid"
    prompt_messages = t2_groq_calls[0]
    system_contents = [m["content"] for m in prompt_messages if m.get("role") == "system"]
    active_msg = next((c for c in system_contents if "Active doctor selected for booking" in c), None)
    assert active_msg is not None
    assert "doc-fatima-uuid" in active_msg


def test_doctor_state_propagation_preferred_is_recommended():
    """Scenario 3: Patient whose recommended doctor IS their preferred doctor.

    Verifies prompt has only one active doctor block and no duplicate doctor injections.
    """
    conv_id = "test-prop-conv-3"
    patient_id = "pat-same-789"

    mock_patient_info = {"name": "Usman Malik", "phone": "+923001112233"}
    mock_appts = [
        {
            "id": "appt-old-2",
            "doctor_name": "Dr. Ahmed Khan",
            "clinic_name": "Main Clinic",
            "appointment_time": "2026-08-01T09:00:00Z",
            "status": "completed",
        }
    ]

    t1_groq_resp = [
        FakeMessage(tool_calls=[FakeToolCall("tc1", "get_doctors_by_specialty", '{"specialty": "General Medicine"}')]),
        FakeMessage(tool_calls=[], content="Dr. Ahmed Khan is available."),
    ]
    t1_tool_exec = [
        {
            "ok": True,
            "doctors": [
                {
                    "doctor_id": "doc-ahmed-uuid",
                    "name": "Dr. Ahmed Khan",
                    "specialization": "General Medicine",
                    "clinic_name": "Main Clinic",
                }
            ],
            "ui_data": {
                "doctors": [
                    {
                        "doctor_id": "doc-ahmed-uuid",
                        "name": "Dr. Ahmed Khan",
                    }
                ]
            },
        }
    ]

    t1_groq_calls = []

    def mock_complete_t1(messages, tools, tool_choice, temperature):
        t1_groq_calls.append(messages)
        return t1_groq_resp[len(t1_groq_calls) - 1]

    with patch("app.patient_context.backend_client.get_patient_info", return_value=mock_patient_info), \
         patch("app.patient_context.backend_client.fetch_patient_appointments", return_value=mock_appts), \
         patch("app.chatbot.groq_client.complete_with_tools", side_effect=mock_complete_t1), \
         patch("app.chatbot.execute_tool", side_effect=t1_tool_exec):

        handle_message(
            conversation_id=conv_id,
            patient_id=patient_id,
            message="I want to see my doctor",
            language="english",
            authorization="Bearer test-token",
        )

    session = get_session(conv_id)
    assert session is not None
    assert session["selected_doctor"]["doctor_id"] == "doc-ahmed-uuid"

    # Turn 2
    t2_groq_resp = [
        FakeMessage(content="Dr. Ahmed Khan is ready to assist."),
    ]
    t2_groq_calls = []

    def mock_complete_t2(messages, tools, tool_choice, temperature):
        t2_groq_calls.append(messages)
        return t2_groq_resp[len(t2_groq_calls) - 1]

    with patch("app.patient_context.backend_client.get_patient_info", return_value=mock_patient_info), \
         patch("app.patient_context.backend_client.fetch_patient_appointments", return_value=mock_appts), \
         patch("app.chatbot.groq_client.complete_with_tools", side_effect=mock_complete_t2):

        handle_message(
            conversation_id=conv_id,
            patient_id=patient_id,
            message="book for 3pm",
            language="english",
            authorization="Bearer test-token",
        )

    prompt_messages = t2_groq_calls[0]
    system_contents = [m["content"] for m in prompt_messages if m.get("role") == "system"]

    active_blocks = [c for c in system_contents if "Active doctor selected for booking" in c]
    candidate_blocks = [c for c in system_contents if "Candidate doctors available" in c]

    assert len(active_blocks) == 1
    assert len(candidate_blocks) == 0
