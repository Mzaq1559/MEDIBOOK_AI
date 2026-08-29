"""
Tests: Chatbot booking flow, intent routing, and off-topic fallback handling.

Reproduces and verifies fixes for:
1. Clicking "Book an appointment" directly presents doctor selection and booking options, not symptom-intake questions.
2. Repeated clicks on "Book an appointment" remain in the booking flow and do not misfire into symptom triage ("When did this start?", "Have you had this before?").
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
    def test_click_book_appointment_shows_doctors_not_symptoms(self, mock_list_doctors):
        """Clicking 'Book an appointment' must immediately return doctor selection, not symptom intake."""
        mock_list_doctors.return_value = FAKE_DOCTORS

        from app.chatbot import handle_message

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
        self.assertNotIn("Please describe your symptoms", res["bot_message"])

    @patch("app.backend_client.list_doctors")
    def test_repeat_click_book_appointment_stays_in_booking_flow(self, mock_list_doctors):
        """Repeated clicks of 'Book an appointment' must remain in booking flow, never asking triage follow-ups."""
        mock_list_doctors.return_value = FAKE_DOCTORS

        from app.chatbot import handle_message

        # Turn 1
        res1 = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="Book an appointment",
            language="en",
            authorization=None,
        )
        self.assertEqual(res1["next_action"], "waiting_for_doctor_selection")

        # Turn 2: Click "Book an appointment" again
        res2 = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="Book an appointment",
            language="en",
            authorization=None,
        )
        self.assertEqual(res2["next_action"], "waiting_for_doctor_selection")
        self.assertNotIn("When did this start?", res2["bot_message"])

        # Turn 3: Click "Book an appointment" a third time
        res3 = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="Book an appointment",
            language="en",
            authorization=None,
        )
        self.assertEqual(res3["next_action"], "waiting_for_doctor_selection")
        self.assertNotIn("Have you had this before?", res3["bot_message"])

    def test_describing_symptoms_triggers_triage(self):
        """Describing actual health symptoms should trigger symptom triage follow-ups."""
        from app.chatbot import handle_message

        res = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="I have had a high fever and runny nose for 2 days",
            language="en",
            authorization=None,
        )

        self.assertIn("waiting_for_input", res["next_action"])
        self.assertIn("Let me ask a few quick questions", res["bot_message"])

    @patch("app.backend_client.list_doctors")
    def test_off_topic_input_during_booking_returns_fallback(self, mock_list_doctors):
        """Hostile/off-topic input like 'u are stupid' during booking flow should return a fallback prompt without crashing state."""
        mock_list_doctors.return_value = FAKE_DOCTORS

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

        self.assertEqual(res2["next_action"], "waiting_for_doctor_selection")
        self.assertIn("didn't understand", res2["bot_message"].lower())
        self.assertIn("doctors", res2["ui_data"])

    def test_off_topic_input_in_idle_returns_fallback(self):
        """Off-topic input in IDLE state returns a helpful generic fallback."""
        from app.chatbot import handle_message

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
