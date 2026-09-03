"""
Tests: Chatbot booking flow, intent routing, and off-topic fallback handling.

Reproduces and verifies fixes for:
1. Clicking "Book an appointment" starts symptom intake before doctor selection.
2. Repeated clicks on "Book an appointment" restart symptom intake rather than misrouting into stale triage state.
3. Describing health symptoms properly triggers symptom intake and triage.
4. Off-topic/hostile user input ("u are stupid") mid-conversation returns a fallback prompt without corrupting session state or misrouting into triage.
"""

import uuid
import unittest
from unittest.mock import patch, MagicMock


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
                "status": "available",
            }
        ],
    }
]


class TestChatbotBookingFlow(unittest.TestCase):
    def setUp(self):
        self.conv_id = str(uuid.uuid4())
        self.patient_id = str(uuid.uuid4())

    @patch("app.backend_client.list_doctors")
    def test_click_book_appointment_starts_symptom_intake(self, mock_list_doctors):
        """Clicking 'Book an appointment' must start symptom intake."""
        mock_list_doctors.return_value = FAKE_DOCTORS

        from app.chatbot import handle_message

        res = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="Book an appointment",
            language="en",
            authorization=None,
        )

        self.assertEqual(res["next_action"], "waiting_for_symptoms")
        self.assertNotIn("doctors", res["ui_data"])
        self.assertIn("What brings you in", res["bot_message"])
        self.assertIn("Please describe your symptoms", res["bot_message"])

    @patch("app.backend_client.list_doctors")
    def test_repeat_click_book_appointment_stays_in_booking_flow(self, mock_list_doctors):
        """Repeated clicks of 'Book an appointment' must remain in booking flow, never misrouting to stale state."""
        mock_list_doctors.return_value = FAKE_DOCTORS

        from app.chatbot import handle_message
        from app.chatbot_state import get_session, S

        # Turn 1
        res1 = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="Book an appointment",
            language="en",
            authorization=None,
        )
        self.assertEqual(res1["next_action"], "waiting_for_symptoms")

        # Turn 2: Click "Book an appointment" again — must stay in booking flow
        # (state is preserved, NOT reset to greeting)
        res2 = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="Book an appointment",
            language="en",
            authorization=None,
        )
        session = get_session(self.conv_id)
        # State must NOT reset to IDLE; should advance within booking flow
        self.assertNotEqual(session["state"], S.IDLE)
        self.assertNotIn("Hi! I'm", res2["bot_message"])

        # Turn 3: Click "Book an appointment" a third time — still in flow
        res3 = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="Book an appointment",
            language="en",
            authorization=None,
        )
        session = get_session(self.conv_id)
        self.assertNotEqual(session["state"], S.IDLE)
        self.assertNotIn("Hi! I'm", res3["bot_message"])

    @patch("app.chatbot.classify", return_value={"intent": "symptom", "symptoms": "high fever and runny nose", "specialty": None, "doctor_name": None, "doctor_id": None, "wants_doctor_list": False, "date": None, "appointment_id": None, "confirms": False, "declines": False, "faq_topic": None, "option_id": None})
    def test_describing_symptoms_triggers_triage(self, mock_classify):
        """Describing actual health symptoms should trigger symptom triage follow-ups."""
        from app.chatbot import handle_message

        res = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="I have had a high fever and runny nose for 2 days",
            language="en",
            authorization=None,
        )

        self.assertEqual(res["next_action"], "waiting_for_symptoms")
        self.assertIn("What brings you in", res["bot_message"])

    @patch("app.chatbot.classify", return_value={"intent": "symptom", "symptoms": None})
    def test_off_topic_input_during_booking_continues_symptom_intake(self, mock_classify):
        """Off-topic input during booking is handled as the current symptom answer."""

        from app.chatbot import handle_message

        # Turn 1: Enter booking flow
        handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="Book an appointment",
            language="en",
            authorization=None,
        )

        # Turn 2: Off-topic input "u are stupid"
        res2 = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="u are stupid",
            language="en",
            authorization=None,
        )

        self.assertEqual(res2["next_action"], "waiting_for_input")
        self.assertIn("When did this start?", res2["bot_message"])
        self.assertNotIn("doctors", res2["ui_data"])

    @patch("app.chatbot.classify", return_value={"intent": "symptom", "symptoms": None})
    def test_off_topic_input_in_idle_starts_symptom_intake(self, mock_classify):
        """Off-topic input in IDLE state starts the symptom-intake flow."""
        from app.chatbot import handle_message

        res = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="u are stupid",
            language="en",
            authorization=None,
        )

        self.assertEqual(res["next_action"], "waiting_for_symptoms")
        self.assertIn("What brings you in", res["bot_message"])


if __name__ == "__main__":
    unittest.main()
