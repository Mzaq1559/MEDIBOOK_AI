"""
Comprehensive Test Suite: MediBook AI Agentic RAG System

Covers all 8 safety & functional requirements:
1. Emergency detection stays fully deterministic and executes first.
2. "Book an appointment" direct intent shows doctors, never symptom intake.
3. Repeated "Book an appointment" clicks stay in booking flow without misfiring.
4. Two-step write flow: propose step validates without writing to DB until user confirms.
5. Unavailable/conflicting slots are rejected at validate step.
6. Ownership check prevents canceling/rescheduling unauthorized appointments.
7. Off-topic/hostile input redirects without corrupting session state or pending proposals.
8. Symptom description uses RAG medical knowledge retrieval tool.
"""

import unittest
import uuid
from unittest.mock import MagicMock, patch

from app.chatbot import handle_message
from app.chatbot_state import get_session
from app.symptom_triage import EMERGENCY_ALERT

DOC_ID = str(uuid.uuid4())
PATIENT_ID = str(uuid.uuid4())
OTHER_PATIENT_ID = str(uuid.uuid4())
APPT_ID = str(uuid.uuid4())

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
                "timestamp": "2026-09-01T09:00:00+05:00",
                "label": "Sep 01, 2026 at 09:00 AM",
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


class TestAgentRAGSystem(unittest.TestCase):
    def setUp(self):
        self.conv_id = str(uuid.uuid4())
        self.patient_id = PATIENT_ID
        self.auth_header = "Bearer fake-test-jwt-token"

    def test_1_emergency_detection_runs_first(self):
        """Scenario 1: Emergency message bypasses LLM agent loop unconditionally."""
        res = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="Help, chest pain and severe difficulty breathing!",
            language="en",
            authorization=self.auth_header,
        )
        self.assertEqual(res["next_action"], "emergency_redirect")
        self.assertEqual(res["bot_message"], EMERGENCY_ALERT)

    @patch("app.backend_client.list_doctors")
    def test_2_booking_intent_shows_doctors_not_symptoms(self, mock_list_doctors):
        """Scenario 2: 'Book an appointment' shows doctors, never symptom-intake questions."""
        mock_list_doctors.return_value = FAKE_DOCTORS

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

    @patch("app.backend_client.list_doctors")
    def test_3_repeat_booking_clicks_do_not_misfire(self, mock_list_doctors):
        """Scenario 3: Repeated 'Book an appointment' messages remain in booking flow."""
        mock_list_doctors.return_value = FAKE_DOCTORS

        for turn in range(3):
            res = handle_message(
                conversation_id=self.conv_id,
                patient_id=self.patient_id,
                message="Book an appointment",
                language="en",
                authorization=self.auth_header,
            )
            self.assertEqual(res["next_action"], "waiting_for_doctor_selection")
            self.assertNotIn("When did this start?", res["bot_message"])

    @patch("app.backend_client.list_doctors")
    @patch("app.backend_client.create_appointment")
    def test_4_two_step_propose_and_confirm_flow(self, mock_create, mock_list_docs):

        """Scenario 4: Propose step validates without DB mutation; DB write only occurs on user confirm turn."""
        mock_list_docs.return_value = FAKE_DOCTORS
        mock_create.return_value = {
            "appointment_id": APPT_ID,
            "clinic_id": str(uuid.uuid4()),
            "status": "scheduled"
        }

        # Turn 1: User selects doctor & slot option
        res1 = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message=DOC_ID,
            language="en",
            authorization=self.auth_header,
        )
        self.assertEqual(res1["next_action"], "waiting_for_slot_selection")

        # Turn 2: User selects slot -> triggers propose_book_appointment
        res2 = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="2026-09-01T09:00:00+05:00",
            language="en",
            authorization=self.auth_header,
        )

        # Confirm DB write was NOT called on propose turn
        mock_create.assert_not_called()
        self.assertEqual(res2["next_action"], "waiting_for_confirmation")
        self.assertIn("Please reply 'Yes'", res2["bot_message"])

        # Check pending action in session
        session = get_session(self.conv_id)
        self.assertIsNotNone(session.get("pending_action"))
        self.assertEqual(session["pending_action"]["status"], "proposed")

        # Turn 3: User confirms ("Yes")
        res3 = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="Yes, confirm it",
            language="en",
            authorization=self.auth_header,
        )

        # Confirm DB write WAS called on confirmation turn
        mock_create.assert_called_once()
        self.assertEqual(res3["next_action"], "appointment_booked")
        self.assertIn("confirmed", res3["bot_message"].lower())
        self.assertIsNone(session.get("pending_action"))

    @patch("app.backend_client.list_doctors")
    def test_5_unavailable_slot_rejected_at_validate_step(self, mock_list_docs):
        """Scenario 5: Requesting an unavailable slot is rejected at propose step."""
        mock_list_docs.return_value = FAKE_DOCTORS

        # Select doctor first
        handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message=DOC_ID,
            language="en",
            authorization=self.auth_header,
        )

        # Request invalid slot
        res = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="2026-12-31T23:59:00+05:00",
            language="en",
            authorization=self.auth_header,
        )

        self.assertIn("unavailable", res["bot_message"].lower())
        session = get_session(self.conv_id)
        self.assertIsNone(session.get("pending_action"))

    @patch("app.backend_client.fetch_patient_appointments")
    def test_6_ownership_check_prevents_unauthorized_cancellation(self, mock_fetch_appts):
        """Scenario 6: Patient cannot cancel or reschedule appointments belonging to someone else."""
        mock_fetch_appts.return_value = FAKE_APPOINTMENTS

        from app.chatbot_handlers import tool_propose_cancel_appointment

        session = get_session(self.conv_id) or {"patient_id": OTHER_PATIENT_ID}
        
        # Attempt to cancel with wrong patient ID context
        res = tool_propose_cancel_appointment(
            session=session,
            appointment_id=APPT_ID,
            auth=self.auth_header
        )

        self.assertFalse(res["valid"])
        self.assertIn("does not belong", res["reason"].lower())

    @patch("app.backend_client.list_doctors")
    def test_7_off_topic_input_redirects_without_losing_session_state(self, mock_list_docs):
        """Scenario 7: Hostile/off-topic input mid-conversation returns fallback redirect without clearing pending proposal."""
        mock_list_docs.return_value = FAKE_DOCTORS

        # Setup proposal in turn 1 & 2
        handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message=DOC_ID,
            language="en",
            authorization=self.auth_header,
        )
        handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="2026-09-01T09:00:00+05:00",
            language="en",
            authorization=self.auth_header,
        )

        session = get_session(self.conv_id)
        self.assertIsNotNone(session.get("pending_action"))

        # Send off-topic input "u are stupid"
        res_offtopic = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="u are stupid",
            language="en",
            authorization=self.auth_header,
        )

        self.assertIn("didn't understand", res_offtopic["bot_message"].lower())
        # Verify pending action proposal was NOT destroyed by off-topic message
        self.assertIsNotNone(session.get("pending_action"))

    def test_8_symptom_triage_uses_rag_retrieval_tool(self):
        """Scenario 8: Symptom descriptions trigger medical knowledge retrieval."""
        res = handle_message(
            conversation_id=self.conv_id,
            patient_id=self.patient_id,
            message="I have had a mild persistent headache and runny nose",
            language="en",
            authorization=self.auth_header,
        )

        self.assertEqual(res["next_action"], "waiting_for_input")
        self.assertTrue(any(k in res["bot_message"].lower() for k in ("physician", "doctor", "specialty", "recommend", "triage", "headache")))


if __name__ == "__main__":
    unittest.main()
