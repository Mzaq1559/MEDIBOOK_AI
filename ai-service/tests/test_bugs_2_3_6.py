"""
Regression tests for Bugs 2, 3, and 6.

Bug 2: Booking confirmation fails with "That time slot is not available"
       due to timezone bug — target_date/slot_time extracted from naive UTC
       instead of Karachi time in validate_booking_slot.

Bug 3: "change" during AWAIT_CONFIRM routes to handle_reschedule
       instead of the AWAIT_CONFIRM handler's own "change" logic.

Bug 6: ASKING_HISTORY skipped when Groq NLU extracts specialty from
       conversation context during ASKING_FOLLOWUP, causing
       _handle_named_selection to jump to SHOWING_DOCTORS.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta
from unittest.mock import patch, MagicMock

import pytest
import pytz

from app.chatbot_handlers import handle_new_booking, _handle_named_selection
from app.chatbot_state import S, new_session


KARACHI_TZ = pytz.timezone("Asia/Karachi")


# ── Bug 6: ASKING_HISTORY reached across multiple symptom categories ────

class TestBug6_AskingHistoryReached:
    """Verify that _handle_named_selection does NOT bypass follow-up questions
    when Groq's NLU extracts a specialty from conversation context."""

    def _run_followup_flow(self, specialty: str, follow_ups: list[str]):
        """Run through all follow-up questions with specialty in NLU,
        assert ASKING_HISTORY is reached at the end."""
        session = {
            "state": S.ASKING_FOLLOWUP,
            "symptoms_text": f"symptoms for {specialty}",
            "specialty": specialty,
            "follow_ups": follow_ups,
            "follow_up_index": 0,
            "urgency_level": "normal",
        }
        nlu = {
            "intent": "symptom",
            "specialty": specialty,  # Groq extracts from context
            "doctor_name": None,
            "wants_doctor_list": False,
            "symptoms": None,
        }
        with patch("app.chatbot_handlers.backend_client.list_doctors", return_value=[]), \
             patch("app.chatbot_handlers.fetch_doctor_slots", return_value=[]), \
             patch("app.chatbot_handlers.is_emergency", return_value=False):
            for i, answer in enumerate(["answer1", "answer2", "answer3"]):
                msg, action, _, _ = handle_new_booking(session, answer, nlu, None)
                if i < len(follow_ups) - 1:
                    assert session["state"] == S.ASKING_FOLLOWUP, \
                        f"Expected ASKING_FOLLOWUP after answer {i+1}, got {session['state']}"
                    assert session["follow_up_index"] == i + 1
            # After last answer, should transition to ASKING_HISTORY
            assert session["state"] == S.ASKING_HISTORY, \
                f"Expected ASKING_HISTORY after all follow-ups, got {session['state']}"

    def test_dermatology_reaches_asking_history(self):
        self._run_followup_flow(
            "Dermatologist",
            ["How long?", "Itchy?", "Tried creams?"],
        )

    def test_cardiology_reaches_asking_history(self):
        self._run_followup_flow(
            "Cardiologist",
            ["When did this start?", "Had before?", "Sharp or dull?"],
        )

    def test_ent_reaches_asking_history(self):
        self._run_followup_flow(
            "ENT Specialist",
            ["Which area?", "Fever?", "How long?"],
        )

    def test_general_medicine_reaches_asking_history(self):
        self._run_followup_flow(
            "General Medicine",
            ["When?", "Before?", "Worse?"],
        )

    def test_named_selection_does_not_fire_during_followup(self):
        """_handle_named_selection with specialty in NLU must NOT be called
        during ASKING_FOLLOWUP (removed from the code path)."""
        session = {
            "state": S.ASKING_FOLLOWUP,
            "symptoms_text": "rashes",
            "specialty": "Dermatologist",
            "follow_ups": ["Q1", "Q2", "Q3"],
            "follow_up_index": 0,
        }
        nlu = {
            "intent": "symptom",
            "specialty": "Dermatologist",
            "doctor_name": None,
            "wants_doctor_list": False,
        }
        # Even with specialty in NLU, _handle_named_selection should NOT be
        # called from ASKING_FOLLOWUP.  We verify by checking that the flow
        # continues to the next follow-up question.
        with patch("app.chatbot_handlers.backend_client.list_doctors", return_value=[]), \
             patch("app.chatbot_handlers.fetch_doctor_slots", return_value=[]), \
             patch("app.chatbot_handlers.is_emergency", return_value=False):
            msg, action, _, _ = handle_new_booking(session, "2 days", nlu, None)
        assert session["state"] == S.ASKING_FOLLOWUP
        assert session["follow_up_index"] == 1
        assert "Thanks" in msg


# ── Bug 3: "change" during AWAIT_CONFIRM routes correctly ───────────────

class TestBug3_ChangeDuringAwaitConfirm:
    """Verify that 'change' during AWAIT_CONFIRM routes to the
    AWAIT_CONFIRM handler (→ SHOWING_DOCTORS) instead of handle_reschedule."""

    def test_change_during_await_confirm_goes_to_showing_doctors(self):
        session = {
            "state": S.AWAIT_CONFIRM,
            "symptoms_text": "headache",
            "specialty": "General Medicine",
            "selected_doctor": {"doctor_id": "doc-1", "name": "Dr. Test"},
            "selected_slot": {"timestamp": "2026-09-05T10:00:00+05:00"},
            "selected_slot_label": "Sep 05 at 10:00",
            "candidate_doctors": [
                {"doctor_id": "doc-1", "name": "Dr. Test", "specialization": "General Medicine"},
            ],
        }
        nlu = {
            "intent": "reschedule",  # Groq classifies "change" as reschedule
            "wants_doctor_list": False,
            "doctor_name": None,
            "specialty": None,
            "symptoms": None,
        }
        with patch("app.chatbot_handlers.backend_client.list_doctors", return_value=[]), \
             patch("app.chatbot_handlers.fetch_doctor_slots", return_value=[]):
            msg, action, _, ui = handle_new_booking(session, "change", nlu, None)

        assert session["state"] == S.SHOWING_DOCTORS
        assert "different" in msg.lower() or "pick" in msg.lower()

    def test_yes_during_await_confirm_triggers_booking(self):
        """Verify that 'yes' (confirm) still works during AWAIT_CONFIRM."""
        session = {
            "state": S.AWAIT_CONFIRM,
            "symptoms_text": "headache",
            "specialty": "General Medicine",
            "patient_id": str(uuid.uuid4()),
            "selected_doctor": {
                "doctor_id": str(uuid.uuid4()),
                "name": "Dr. Test",
                "clinic_name": "Test Clinic",
                "clinic_address": "Test City",
            },
            "selected_slot": {"timestamp": "2026-12-05T10:00:00+05:00"},
            "selected_slot_label": "Dec 05 at 10:00",
            "selected_timestamp": "2026-12-05T10:00:00+05:00",
            "candidate_doctors": [],
            "urgency_level": "normal",
            "urgency_reason": "test",
            "medical_history": None,
        }
        nlu = {
            "intent": "appointment",
            "confirms": True,
            "declines": False,
            "wants_doctor_list": False,
            "doctor_name": None,
            "specialty": None,
            "symptoms": None,
        }
        with patch("app.chatbot_handlers.backend_client.create_appointment", return_value={
            "appointment_id": str(uuid.uuid4()),
            "patient_id": str(uuid.uuid4()),
        }) as mock_create, \
             patch("app.chatbot_handlers.google_calendar.create_calendar_event", return_value=None), \
             patch("app.chatbot_handlers.reminders.send_confirmation_email", return_value=True):
            msg, action, _, _ = handle_new_booking(session, "yes", nlu, "Bearer test-token")

        assert session["state"] == S.BOOKED
        mock_create.assert_called_once()


# ── Bug 2: Timezone-correct slot validation ─────────────────────────────
# Test lives in backend/tests/test_bug2_timezone.py because
# validate_booking_slot is in backend/app/services/appointment_service.py
