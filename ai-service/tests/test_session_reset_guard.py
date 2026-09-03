"""Regression test: top-level intent misclassification must NOT reset active booking flow.

Covers the session-reset bug where the Groq LLM (especially after a
400→200 retry sequence) classifies a follow-up answer like "3 hours ago"
as intent="appointment" instead of "symptom".  The dispatcher must NOT
call _reset_patient_workflow() while the session is in an active booking
state (ASKING_SYMPTOMS, ASKING_FOLLOWUP, ASKING_HISTORY, SHOWING_DOCTORS,
SHOWING_SLOTS).

The conversation state must be preserved and the follow-up answer must be
processed by the active state handler, not treated as a new booking request.
"""

import uuid
import unittest
from unittest.mock import patch

from app.chatbot import handle_message
from app.chatbot_state import get_session, S


def _make_nlu(**overrides):
    """Build a minimal NLU dict with sensible defaults; override any key."""
    base = {
        "intent": "symptom",
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


class TestTopLevelIntentSuppressedDuringBooking(unittest.TestCase):
    """intent='appointment' during active booking must NOT reset the session."""

    def setUp(self):
        self.conv_id = str(uuid.uuid4())
        self.patient_id = str(uuid.uuid4())

    def _send(self, message, nlu=None):
        if nlu is None:
            nlu = _make_nlu()
        with patch("app.chatbot.classify", return_value=nlu):
            return handle_message(
                conversation_id=self.conv_id,
                patient_id=self.patient_id,
                message=message,
                language="en",
                authorization=None,
            )

    # ── Helpers ─────────────────────────────────────────────────
    def _enter_asking_followup(self):
        """Drive the session to ASKING_FOLLOWUP state."""
        self._send("Book an appointment", _make_nlu(intent="appointment"))
        self._send("heart ache", _make_nlu(intent="symptom", symptoms="heart ache"))
        session = get_session(self.conv_id)
        self.assertEqual(session["state"], S.ASKING_FOLLOWUP)
        return session

    # ── Tests ───────────────────────────────────────────────────

    def test_appointment_intent_during_asking_followup_no_reset(self):
        """intent='appointment' during ASKING_FOLLOWUP must NOT reset to greeting."""
        self._enter_asking_followup()

        # NLU misclassifies follow-up answer as "appointment"
        r = self._send("3 hours ago", _make_nlu(intent="appointment"))
        session = get_session(self.conv_id)

        # State must NOT reset to IDLE or ASKING_SYMPTOMS
        self.assertNotEqual(session["state"], S.IDLE, "State reset to IDLE!")
        self.assertNotEqual(session["state"], S.ASKING_SYMPTOMS, "State reset to ASKING_SYMPTOMS!")
        # Bot must NOT return the greeting
        self.assertNotIn("Hi! I'm", r["bot_message"])
        # Session should advance (ASKING_FOLLOWUP → next follow-up or ASKING_HISTORY)
        self.assertIn(session["state"], (S.ASKING_FOLLOWUP, S.ASKING_HISTORY))

    def test_appointment_intent_during_asking_symptoms_no_reset(self):
        """intent='appointment' during ASKING_SYMPTOMS must NOT reset."""
        self._send("Book an appointment", _make_nlu(intent="appointment"))
        session = get_session(self.conv_id)
        self.assertEqual(session["state"], S.ASKING_SYMPTOMS)

        r = self._send("chest discomfort", _make_nlu(intent="appointment"))
        session = get_session(self.conv_id)

        self.assertNotEqual(session["state"], S.IDLE)
        self.assertNotIn("Hi! I'm", r["bot_message"])

    def test_cancel_intent_during_asking_followup_no_reset(self):
        """intent='cancel' during ASKING_FOLLOWUP must NOT reset."""
        self._enter_asking_followup()

        r = self._send("3 hours ago", _make_nlu(intent="cancel"))
        session = get_session(self.conv_id)

        self.assertNotEqual(session["state"], S.IDLE)
        self.assertNotIn("Hi! I'm", r["bot_message"])

    def test_reschedule_intent_during_asking_followup_no_reset(self):
        """intent='reschedule' during ASKING_FOLLOWUP must NOT reset."""
        self._enter_asking_followup()

        r = self._send("3 hours ago", _make_nlu(intent="reschedule"))
        session = get_session(self.conv_id)

        self.assertNotEqual(session["state"], S.IDLE)
        self.assertNotIn("Hi! I'm", r["bot_message"])

    def test_appointment_intent_from_idle_still_resets(self):
        """intent='appointment' from IDLE MUST still trigger a fresh booking."""
        # First booking
        self._send("Book an appointment", _make_nlu(intent="appointment"))
        self._send("headache", _make_nlu(intent="symptom", symptoms="headache"))

        # Now from a non-active state, user says "book an appointment" again
        # First force back to IDLE by completing the flow or manually setting
        session = get_session(self.conv_id)
        session["state"] = S.IDLE  # simulate post-booking or fresh state

        r = self._send("Book an appointment", _make_nlu(intent="appointment"))
        session = get_session(self.conv_id)

        # From IDLE, "appointment" SHOULD start fresh
        self.assertEqual(session["state"], S.ASKING_SYMPTOMS)
        self.assertIn("What brings you in", r["bot_message"])

    def test_typo_followup_preserves_conversation_state(self):
        """Typo '3 hors ago' with intent='appointment' must preserve state."""
        self._enter_asking_followup()

        # Simulate the exact bug: Groq 400→200 retry returns appointment intent
        r = self._send("3 hors ago", _make_nlu(intent="appointment"))
        session = get_session(self.conv_id)

        # Conversation state must be preserved
        self.assertNotEqual(session["state"], S.IDLE)
        self.assertNotEqual(session["state"], S.ASKING_SYMPTOMS)
        # Symptoms text must still contain original symptoms
        self.assertIn("heart ache", session.get("symptoms_text", ""))


class TestGroqRetryPreservesContext(unittest.TestCase):
    """Groq retry logic must send the same messages on each attempt."""

    def test_retry_sends_same_messages(self):
        """After a failed attempt, retry must use identical messages."""
        call_args = []
        attempt_counter = {"n": 0}

        class FakeMessage:
            def __init__(self, content):
                self.content = content

        class FakeChoice:
            def __init__(self, content):
                self.message = FakeMessage(content)

        class FakeResponse:
            def __init__(self, content):
                self.choices = [FakeChoice(content)]

        class FakeCompletions:
            def create(self, **kwargs):
                attempt_counter["n"] += 1
                call_args.append(kwargs["messages"])
                if attempt_counter["n"] < 3:
                    raise RuntimeError("400 Bad Request")
                return FakeResponse('{"intent":"appointment"}')

        class FakeChat:
            def __init__(self):
                self.completions = FakeCompletions()

        class FakeClient:
            def __init__(self):
                self.chat = FakeChat()

        with patch("app.groq_client._client", return_value=FakeClient()):
            from app.groq_client import complete
            result = complete(
                [{"role": "user", "content": "test"}],
                retries=3,
            )

        # All 3 attempts must have the same messages
        self.assertEqual(len(call_args), 3)
        self.assertEqual(call_args[0], call_args[1])
        self.assertEqual(call_args[1], call_args[2])


if __name__ == "__main__":
    unittest.main()
