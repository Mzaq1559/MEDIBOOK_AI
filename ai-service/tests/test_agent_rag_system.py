"""
Safety and agent tests for MediBook AI.

Emergency detection remains deterministic. Booking, reschedule, and cancel
are driven by Groq tool calls — not hardcoded intent routers.
"""

import json
import unittest
import uuid
from unittest.mock import patch

from app.chatbot import get_session, handle_message
from app.symptom_triage import EMERGENCY_ALERT
from app.tools import execute_tool

DOC_ID = str(uuid.uuid4())
PATIENT_ID = str(uuid.uuid4())
OTHER_PATIENT_ID = str(uuid.uuid4())
APPT_ID = str(uuid.uuid4())
SLOT_TS = "2026-09-01T09:00:00+05:00"

FAKE_DOCTORS = [
    {
        "doctor_id": DOC_ID,
        "name": "Dr. Sarah Khan",
        "specialization": "General Physician",
        "consultation_fee": 2000,
        "clinic_name": "MediBook Central Clinic",
        "clinic_address": "Main Boulevard, Lahore",
        "availability_slots": [
            {
                "timestamp": SLOT_TS,
                "label": "Sep 01, 2026 at 09:00 AM",
                "date": "2026-09-01",
                "time": "09:00 AM",
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
        "doctor_name": "Dr. Sarah Khan",
        "clinic_name": "MediBook Central Clinic",
        "patient_id": PATIENT_ID,
        "appointment_time": "2026-09-01T09:00:00Z",
        "status": "scheduled",
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


class TestAgentRAGSystem(unittest.TestCase):
    def setUp(self):
        self.conv_id = str(uuid.uuid4())
        self.patient_id = PATIENT_ID
        self.auth_header = "Bearer fake-test-jwt-token"

    def test_1_emergency_detection_runs_first(self):
        res = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="Help, chest pain and severe difficulty breathing!",
            language="en",
            authorization=self.auth_header,
        )
        self.assertEqual(res["next_action"], "emergency_redirect")
        self.assertEqual(res["bot_message"], EMERGENCY_ALERT)

    @patch("app.backend_client.list_doctors", return_value=FAKE_DOCTORS)
    @patch("app.backend_client.get_availability", return_value=None)
    def test_2_booking_intent_shows_doctors_not_symptoms(self, _avail, _docs):
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
                authorization=self.auth_header,
            )
        self.assertEqual(res["next_action"], "waiting_for_doctor_selection")
        self.assertIn("doctors", res["ui_data"])
        self.assertNotIn("When did this start?", res["bot_message"])

    @patch("app.backend_client.list_doctors", return_value=FAKE_DOCTORS)
    @patch("app.backend_client.get_availability", return_value=None)
    def test_3_repeat_booking_clicks_do_not_misfire(self, _avail, _docs):
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
                    authorization=self.auth_header,
                )
            self.assertEqual(res["next_action"], "waiting_for_doctor_selection")
            self.assertNotIn("When did this start?", res["bot_message"])

    @patch("app.backend_client.list_doctors", return_value=FAKE_DOCTORS)
    @patch("app.backend_client.get_availability", return_value=None)
    @patch("app.backend_client.create_appointment")
    def test_4_confirm_then_book_writes_once(self, mock_create, _avail, _docs):
        mock_create.return_value = {
            "appointment_id": APPT_ID,
            "clinic_id": str(uuid.uuid4()),
            "status": "scheduled",
        }
        groq_ask = [FakeMessage(content="Book Dr. Sarah Khan on Sep 01 at 09:00 AM? Reply yes to confirm.")]
        with patch("app.groq_client.complete_with_tools", side_effect=groq_ask):
            res1 = handle_message(
                conversation_id=self.conv_id,
                patient_id=self.patient_id,
                message=f"Book {DOC_ID} at {SLOT_TS}",
                language="en",
                authorization=self.auth_header,
            )
        mock_create.assert_not_called()
        self.assertIn("confirm", res1["bot_message"].lower())

        groq_book = [
            FakeMessage(
                tool_calls=[
                    FakeToolCall(
                        "book_appointment",
                        {
                            "patient_id": PATIENT_ID,
                            "doctor_id": DOC_ID,
                            "datetime": SLOT_TS,
                            "symptoms": "General Consultation",
                        },
                    )
                ]
            ),
            FakeMessage(content="Your appointment with Dr. Sarah Khan is confirmed!"),
        ]
        with patch("app.groq_client.complete_with_tools", side_effect=groq_book):
            res2 = handle_message(
                conversation_id=self.conv_id,
                patient_id=self.patient_id,
                message="Yes, confirm it",
                language="en",
                authorization=self.auth_header,
            )
        mock_create.assert_called_once()
        self.assertIn("confirmed", res2["bot_message"].lower())

    @patch("app.backend_client.list_doctors", return_value=FAKE_DOCTORS)
    @patch("app.backend_client.get_availability", return_value=None)
    def test_5_unavailable_slot_rejected_by_book_tool(self, _avail, _docs):
        groq = [
            FakeMessage(
                tool_calls=[
                    FakeToolCall(
                        "book_appointment",
                        {
                            "patient_id": PATIENT_ID,
                            "doctor_id": DOC_ID,
                            "datetime": "2026-12-31T23:59:00+05:00",
                            "symptoms": "checkup",
                        },
                    )
                ]
            ),
            FakeMessage(content="That slot is unavailable. Please pick another time."),
        ]
        with patch("app.backend_client.create_appointment") as mock_create:
            with patch("app.groq_client.complete_with_tools", side_effect=groq):
                res = handle_message(
                    conversation_id=self.conv_id,
                    patient_id=self.patient_id,
                    message="Book me at 2026-12-31T23:59:00+05:00",
                    language="en",
                    authorization=self.auth_header,
                )
            mock_create.assert_not_called()
        self.assertIn("unavailable", res["bot_message"].lower())

    def test_6_ownership_check_prevents_unauthorized_cancellation(self):
        session = {
            "patient_id": OTHER_PATIENT_ID,
            "last_ui_data": {},
            "patient_appointments": FAKE_APPOINTMENTS,
        }
        res = execute_tool(
            "cancel_appointment",
            {"appointment_id": APPT_ID},
            session,
            self.auth_header,
        )
        self.assertFalse(res["ok"])
        self.assertTrue("does not belong" in res["error"].lower() or "not found" in res["error"].lower())

    def test_7_off_topic_input_redirects(self):
        groq = [
            FakeMessage(
                content=(
                    "I didn't understand that. I am your MediBook AI assistant. "
                    "I can help you book, reschedule, or cancel appointments."
                )
            )
        ]
        with patch("app.groq_client.complete_with_tools", side_effect=groq):
            res = handle_message(
                conversation_id=self.conv_id,
                patient_id=self.patient_id,
                message="u are stupid",
                language="en",
                authorization=self.auth_header,
            )
        self.assertIn("didn't understand", res["bot_message"].lower())
        session = get_session(self.conv_id)
        self.assertIsNotNone(session)

    def test_8_symptom_description_gets_natural_reply(self):
        groq = [
            FakeMessage(
                content="For a mild headache and runny nose I recommend a General Physician. Shall I show available doctors?"
            )
        ]
        with patch("app.groq_client.complete_with_tools", side_effect=groq):
            res = handle_message(
                conversation_id=self.conv_id,
                patient_id=self.patient_id,
                message="I have had a mild persistent headache and runny nose",
                language="en",
                authorization=self.auth_header,
            )
        self.assertEqual(res["next_action"], "waiting_for_input")
        self.assertTrue(
            any(k in res["bot_message"].lower() for k in ("physician", "doctor", "specialty", "recommend", "headache"))
        )


if __name__ == "__main__":
    unittest.main()
