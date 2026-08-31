"""Agentic booking flow tests using Groq tool-call mocks."""

import json
import unittest
import uuid
from unittest.mock import patch

FAKE_DOCTORS = [
    {
        "doctor_id": str(uuid.uuid4()),
        "name": "Dr. Sarah Khan",
        "specialization": "General Physician",
        "qualification": "MBBS, FCPS",
        "experience_years": 10,
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


class TestChatbotBookingFlow(unittest.TestCase):
    def setUp(self):
        self.conv_id = str(uuid.uuid4())
        self.patient_id = str(uuid.uuid4())

    @patch("app.backend_client.list_doctors")
    @patch("app.backend_client.get_availability", return_value=None)
    def test_click_book_appointment_shows_doctors_not_symptoms(self, _avail, mock_list_doctors):
        mock_list_doctors.return_value = FAKE_DOCTORS
        from app.chatbot import handle_message

        groq = [
            FakeMessage(
                tool_calls=[FakeToolCall("get_doctors_by_specialty", {"specialty": "General Physician"})]
            ),
            FakeMessage(content="Please select a doctor to book your appointment."),
        ]
        with patch("app.groq_client.complete_with_tools", side_effect=groq):
            res = handle_message(
                conversation_id=self.conv_id,
                patient_id=self.patient_id,
                message="Book an appointment",
                language="en",
                authorization=None,
            )
        self.assertEqual(res["next_action"], "waiting_for_doctor_selection")
        self.assertIn("doctors", res["ui_data"])
        self.assertNotIn("When did this start?", res["bot_message"])

    @patch("app.backend_client.list_doctors")
    @patch("app.backend_client.get_availability", return_value=None)
    def test_repeat_click_book_appointment_stays_in_booking_flow(self, _avail, mock_list_doctors):
        mock_list_doctors.return_value = FAKE_DOCTORS
        from app.chatbot import handle_message

        for _ in range(3):
            groq = [
                FakeMessage(
                    tool_calls=[
                        FakeToolCall("get_doctors_by_specialty", {"specialty": "General Physician"})
                    ]
                ),
                FakeMessage(content="Please select a doctor to book your appointment."),
            ]
            with patch("app.groq_client.complete_with_tools", side_effect=groq):
                res = handle_message(
                    conversation_id=self.conv_id,
                    patient_id=self.patient_id,
                    message="Book an appointment",
                    language="en",
                    authorization=None,
                )
            self.assertEqual(res["next_action"], "waiting_for_doctor_selection")

    def test_describing_symptoms_triggers_triage(self):
        from app.chatbot import handle_message

        groq = [
            FakeMessage(
                content="Recommended specialty: General Physician. I can help you book a doctor for the fever."
            )
        ]
        with patch("app.groq_client.complete_with_tools", side_effect=groq):
            res = handle_message(
                conversation_id=self.conv_id,
                patient_id=self.patient_id,
                message="I have had a high fever and runny nose for 2 days",
                language="en",
                authorization=None,
            )
        self.assertEqual(res["next_action"], "waiting_for_input")
        self.assertTrue(
            any(
                word in res["bot_message"].lower()
                for word in ("specialty", "physician", "doctor", "recommend", "triage", "sore", "fever")
            )
        )

    def test_off_topic_input_during_booking_returns_fallback(self):
        from app.chatbot import handle_message

        groq = [
            FakeMessage(
                content="I didn't understand that. I can help you book, reschedule, or cancel appointments."
            )
        ]
        with patch("app.groq_client.complete_with_tools", side_effect=groq):
            res2 = handle_message(
                conversation_id=self.conv_id,
                patient_id=self.patient_id,
                message="u are stupid",
                language="en",
                authorization=None,
            )
        self.assertIn("didn't understand", res2["bot_message"].lower())

    def test_off_topic_input_in_idle_returns_fallback(self):
        from app.chatbot import handle_message

        groq = [
            FakeMessage(
                content="I didn't understand that. How can I help with appointments or clinic questions?"
            )
        ]
        with patch("app.groq_client.complete_with_tools", side_effect=groq):
            res = handle_message(
                conversation_id=self.conv_id,
                patient_id=self.patient_id,
                message="u are stupid",
                language="en",
                authorization=None,
            )
        self.assertEqual(res["next_action"], "waiting_for_input")
        self.assertIn("didn't understand", res["bot_message"].lower())


if __name__ == "__main__":
    unittest.main()
