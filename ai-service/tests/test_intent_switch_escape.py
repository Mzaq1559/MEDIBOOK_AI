"""Regression tests: intent-switch escape from active booking states.

BUG: Once inside ASKING_FOLLOWUP / ASKING_HISTORY, the chatbot blindly
consumes ALL messages as follow-up answers — even clear unrelated requests
like "What are my appointments?" or "cancel my appointment".

Additionally, "Reschedule appointment" from IDLE could be misclassified by
the NLU as intent="appointment", causing the dispatcher to route to
handle_new_booking (symptom prompt) instead of handle_reschedule.

These tests verify:
1. "What are my appointments?" during ASKING_FOLLOWUP breaks out to lookup
2. "cancel my appointment" during ASKING_FOLLOWUP breaks out to cancel
3. "reschedule my appointment" during ASKING_FOLLOWUP breaks out to reschedule
4. Question-like messages with "?" during ASKING_FOLLOWUP break out
5. Normal follow-up answers (e.g. "3 hours ago") still pass through
6. "Reschedule appointment" from IDLE routes to handle_reschedule, NOT symptom flow
7. ASKING_HISTORY also has the intent-switch escape hatch
"""
import unittest
from unittest.mock import patch, MagicMock

from app.chatbot_handlers import handle_new_booking, handle_lookup, handle_reschedule
from app.chatbot_state import S


def _make_session(state=S.ASKING_FOLLOWUP, **overrides):
    """Build a session in the given state."""
    session = {
        "state": state,
        "patient_id": "pat-123",
        "symptoms_text": "headache and fever",
        "follow_ups": [
            "When did this start?",
            "Have you had this before?",
            "Is it getting worse?",
        ],
        "follow_up_index": 0,
        "specialty": None,
        "urgency_level": "normal",
        "urgency_reason": None,
        "medical_history": None,
        "candidate_doctors": [],
        "selected_doctor": None,
        "selected_slot": None,
        "selected_slot_label": None,
        "selected_timestamp": None,
        "picked_appointment_id": None,
        "previous_slot_label": None,
        "patient_appointments": [],
        "messages": [],
    }
    session.update(overrides)
    return session


def _nlu(intent="symptom", **overrides):
    base = {
        "intent": intent,
        "doctor_name": None,
        "doctor_id": None,
        "specialty": None,
        "wants_doctor_list": False,
        "date": None,
        "symptoms": None,
        "appointment_id": None,
        "confirms": False,
        "declines": False,
        "faq_topic": None,
        "option_id": None,
    }
    base.update(overrides)
    return base


class TestIntentSwitchEscapeDuringFollowup(unittest.TestCase):
    """Clear intent-switch messages must break out of ASKING_FOLLOWUP."""

    @patch("app.chatbot_handlers.handle_lookup")
    def test_lookup_question_breaks_out(self, mock_lookup):
        """'What are my appointments?' must NOT be consumed as a follow-up answer."""
        mock_lookup.return_value = ("Your appointments:", "show_appointments", [], {"appointments": []})
        session = _make_session()
        nlu = _nlu(intent="lookup")

        msg, action, _, ui_data = handle_new_booking(
            session, "What are my appointments?", nlu, "Bearer test-token"
        )

        mock_lookup.assert_called_once()
        self.assertEqual(msg, "Your appointments:")
        # State should NOT be ASKING_FOLLOWUP anymore
        self.assertNotEqual(session["state"], S.ASKING_FOLLOWUP)

    @patch("app.chatbot_handlers.handle_cancel")
    def test_cancel_request_breaks_out(self, mock_cancel):
        """'cancel my appointment' must route to the cancel flow."""
        mock_cancel.return_value = ("No appointments to cancel.", "show_appointments", [], {})
        session = _make_session()
        nlu = _nlu(intent="cancel")

        msg, action, _, ui_data = handle_new_booking(
            session, "cancel my appointment", nlu, "Bearer test-token"
        )

        mock_cancel.assert_called_once()
        self.assertNotEqual(session["state"], S.ASKING_FOLLOWUP)

    @patch("app.chatbot_handlers.handle_reschedule")
    def test_reschedule_request_breaks_out(self, mock_reschedule):
        """'reschedule my appointment' must route to the reschedule flow."""
        mock_reschedule.return_value = ("Which appointment?", "show_appointments", [], {})
        session = _make_session()
        nlu = _nlu(intent="reschedule")

        msg, action, _, ui_data = handle_new_booking(
            session, "reschedule my appointment", nlu, "Bearer test-token"
        )

        mock_reschedule.assert_called_once()
        self.assertNotEqual(session["state"], S.ASKING_FOLLOWUP)

    @patch("app.chatbot_handlers.handle_lookup")
    def test_question_mark_with_keywords_breaks_out(self, mock_lookup):
        """Even if NLU says 'symptom', a question with keywords must break out."""
        mock_lookup.return_value = ("Your appointments:", "show_appointments", [], {"appointments": []})
        session = _make_session()
        # NLU misclassifies but text has "?" + "my appointment"
        nlu = _nlu(intent="symptom")

        msg, action, _, ui_data = handle_new_booking(
            session, "Can I see my appointment?", nlu, "Bearer test-token"
        )

        mock_lookup.assert_called_once()

    def test_normal_followup_answer_passes_through(self):
        """Normal answers like '3 hours ago' must still be consumed as follow-up."""
        session = _make_session()
        nlu = _nlu(intent="symptom")

        msg, action, _, ui_data = handle_new_booking(
            session, "3 hours ago", nlu, "Bearer test-token"
        )

        # Should advance to next follow-up question, not break out
        self.assertEqual(session["follow_up_index"], 1)
        self.assertIn("Thanks", msg)

    def test_free_text_symptom_answer_passes_through(self):
        """Symptom-like text without clear intent-switch must pass through."""
        session = _make_session()
        nlu = _nlu(intent="symptom")

        msg, action, _, ui_data = handle_new_booking(
            session, "since yesterday morning, it started slowly", nlu, "Bearer test-token"
        )

        self.assertEqual(session["follow_up_index"], 1)
        # The symptoms text should have been appended
        self.assertIn("yesterday", session["symptoms_text"])


class TestIntentSwitchEscapeDuringHistory(unittest.TestCase):
    """ASKING_HISTORY must also have the escape hatch."""

    @patch("app.chatbot_handlers.handle_lookup")
    def test_lookup_during_history_breaks_out(self, mock_lookup):
        """'show my appointments' during ASKING_HISTORY must break out."""
        mock_lookup.return_value = ("Your appointments:", "show_appointments", [], {"appointments": []})
        session = _make_session(state=S.ASKING_HISTORY)
        nlu = _nlu(intent="lookup")

        msg, action, _, ui_data = handle_new_booking(
            session, "show my appointments", nlu, "Bearer test-token"
        )

        mock_lookup.assert_called_once()
        self.assertNotEqual(session["state"], S.ASKING_HISTORY)


class TestRescheduleRoutingFromIdle(unittest.TestCase):
    """'Reschedule appointment' from IDLE must go to handle_reschedule, not symptom flow."""

    def test_reschedule_regex_matches(self):
        """The RESCHEDULE_RE regex must match 'Reschedule appointment'."""
        from app.chatbot_nlu import RESCHEDULE_RE
        self.assertIsNotNone(RESCHEDULE_RE.search("Reschedule appointment"))
        self.assertIsNotNone(RESCHEDULE_RE.search("reschedule my appointment"))
        self.assertIsNotNone(RESCHEDULE_RE.search("time change please"))

    @patch("app.chatbot_handlers.backend_client.fetch_patient_appointments")
    def test_reschedule_from_idle_fetches_appointments(self, mock_fetch):
        """handle_reschedule called from IDLE must fetch appointments, not show symptom prompt."""
        mock_fetch.return_value = [
            {
                "id": "appt-1",
                "appointment_id": "appt-1",
                "doctor_name": "Dr. Test",
                "appointment_time": "2026-09-05T10:00:00",
                "status": "scheduled",
            }
        ]
        session = _make_session(state=S.IDLE)
        nlu = _nlu(intent="reschedule")

        msg, action, _, ui_data = handle_reschedule(
            session, "Reschedule appointment", nlu, "Bearer test-token"
        )

        # Should fetch appointments, NOT return symptom prompt
        mock_fetch.assert_called_once()
        self.assertNotIn("symptoms", msg.lower())
        self.assertEqual(session["state"], S.RESCHEDULE_PICK)
        self.assertIn("Which appointment", msg)


if __name__ == "__main__":
    unittest.main()
