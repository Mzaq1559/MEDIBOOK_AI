"""
Tests: Doctor chatbot NLU-based intent detection and Urdu script support.

Verifies fixes for:
1. NLU-based intent routing instead of hardcoded English keywords
2. patient_details intent for viewing specific patient appointments
3. Urdu script patient name matching in _match_appointment_by_patient
4. Pending selection logic preserved after refactoring
"""

import inspect
import uuid
import unittest
from unittest.mock import patch, MagicMock
from app.chatbot_state import S, new_session
from app.chatbot_doctor import handle_doctor_message, _match_appointment_by_patient


class TestDoctorNLUIntentRouting(unittest.TestCase):
    """Test that doctor chatbot routes based on NLU intent, not keywords.

    Each test mocks classify() to return a specific intent and asserts
    the EXACT next_action AND bot_message so the test would fail if
    routing were broken.
    """

    def setUp(self):
        self.doctor_context = {
            "doctor_id": str(uuid.uuid4()),
            "name": "Dr. Test Doctor",
            "user_id": str(uuid.uuid4()),
        }
        self.authorization = "Bearer fake_token"

    @patch("app.backend_client.fetch_doctor_appointments")
    @patch("app.chatbot_doctor.classify")
    def test_reschedule_intent_routes_to_reschedule(self, mock_classify, mock_fetch):
        """NLU intent='reschedule' → _doctor_reschedule → 'doctor_reschedule'."""
        mock_classify.return_value = {"intent": "reschedule", "doctor_name": None}
        mock_fetch.return_value = []

        session = new_session(str(uuid.uuid4()), "test_patient")
        result = handle_doctor_message(
            session=session,
            message="I want to reschedule",
            authorization=self.authorization,
            doctor_context=self.doctor_context,
        )

        self.assertEqual(result["next_action"], "doctor_reschedule")
        # Empty appointments → deterministic "no appointments to reschedule" message
        self.assertIn("no appointments", result["bot_message"].lower())

    @patch("app.backend_client.fetch_doctor_appointments")
    @patch("app.chatbot_doctor.classify")
    def test_cancel_intent_routes_to_cancel(self, mock_classify, mock_fetch):
        """NLU intent='cancel' → _doctor_cancel → 'doctor_cancel'."""
        mock_classify.return_value = {"intent": "cancel", "doctor_name": None}
        mock_fetch.return_value = []

        session = new_session(str(uuid.uuid4()), "test_patient")
        result = handle_doctor_message(
            session=session,
            message="Cancel this appointment",
            authorization=self.authorization,
            doctor_context=self.doctor_context,
        )

        self.assertEqual(result["next_action"], "doctor_cancel")
        self.assertIn("no appointments", result["bot_message"].lower())

    @patch("app.backend_client.fetch_doctor_appointments")
    @patch("app.chatbot_doctor.classify")
    def test_patient_details_intent_routes_to_patient_details(self, mock_classify, mock_fetch):
        """NLU intent='patient_details' → _doctor_patient_details → 'doctor_appointment_details'."""
        mock_classify.return_value = {"intent": "patient_details", "doctor_name": None}
        mock_fetch.return_value = []

        session = new_session(str(uuid.uuid4()), "test_patient")
        result = handle_doctor_message(
            session=session,
            message="Show me Ali's details",
            authorization=self.authorization,
            doctor_context=self.doctor_context,
        )

        self.assertEqual(result["next_action"], "doctor_appointment_details")
        self.assertIn("no appointments", result["bot_message"].lower())

    @patch("app.backend_client.fetch_doctor_appointments")
    @patch("app.chatbot_doctor.classify")
    def test_lookup_intent_routes_to_show_appointments(self, mock_classify, mock_fetch):
        """NLU intent='lookup' → _doctor_show_appointments → 'doctor_appointments'."""
        mock_classify.return_value = {"intent": "lookup", "doctor_name": None}
        mock_fetch.return_value = []

        session = new_session(str(uuid.uuid4()), "test_patient")
        result = handle_doctor_message(
            session=session,
            message="Show my appointments",
            authorization=self.authorization,
            doctor_context=self.doctor_context,
        )

        self.assertEqual(result["next_action"], "doctor_appointments")
        self.assertIn("no appointments", result["bot_message"].lower())

    @patch("app.chatbot_doctor.classify")
    def test_appointment_intent_returns_unsupported(self, mock_classify):
        """NLU intent='appointment' → 'doctor_unsupported' with 'not supported' message."""
        mock_classify.return_value = {"intent": "appointment", "doctor_name": None}

        session = new_session(str(uuid.uuid4()), "test_patient")
        result = handle_doctor_message(
            session=session,
            message="Book a new appointment",
            authorization=self.authorization,
            doctor_context=self.doctor_context,
        )

        self.assertEqual(result["next_action"], "doctor_unsupported")
        self.assertIn("not supported", result["bot_message"].lower())

    @patch("app.chatbot_doctor.classify")
    def test_unknown_intent_returns_fallback(self, mock_classify):
        """Unknown NLU intent → 'doctor_unsupported' with guidance message."""
        mock_classify.return_value = {"intent": "faq", "doctor_name": None}

        session = new_session(str(uuid.uuid4()), "test_patient")
        result = handle_doctor_message(
            session=session,
            message="What are your hours?",
            authorization=self.authorization,
            doctor_context=self.doctor_context,
        )

        self.assertEqual(result["next_action"], "doctor_unsupported")
        self.assertIn("show your appointments", result["bot_message"].lower())

    @patch("app.backend_client.fetch_doctor_appointments")
    @patch("app.chatbot_doctor.classify")
    def test_classify_called_with_correct_args(self, mock_classify, mock_fetch):
        """classify() should be called with (message, history, state) AND result drives routing."""
        mock_classify.return_value = {"intent": "lookup", "doctor_name": None}
        mock_fetch.return_value = []

        conv_id = str(uuid.uuid4())
        session = new_session(conv_id, "test_patient")
        session["state"] = S.ASKING_SYMPTOMS

        result = handle_doctor_message(
            session=session,
            message="test message",
            authorization=self.authorization,
            doctor_context=self.doctor_context,
        )

        mock_classify.assert_called_once_with("test message", [], S.ASKING_SYMPTOMS)
        # Prove the NLU result actually drives routing — lookup → "doctor_appointments"
        self.assertEqual(result["next_action"], "doctor_appointments")

    @patch("app.backend_client.fetch_doctor_appointments")
    @patch("app.chatbot_doctor.classify")
    def test_cancel_sets_last_doctor_action(self, mock_classify, mock_fetch):
        """After cancel routing, session['last_doctor_action'] should be 'cancel'."""
        mock_classify.return_value = {"intent": "cancel", "doctor_name": None}
        mock_fetch.return_value = []

        session = new_session(str(uuid.uuid4()), "test_patient")
        self.assertIsNone(session.get("last_doctor_action"))
        result = handle_doctor_message(
            session=session,
            message="Cancel",
            authorization=self.authorization,
            doctor_context=self.doctor_context,
        )

        self.assertEqual(session["last_doctor_action"], "cancel")
        # Also prove routing reached _doctor_cancel (not just session mutation)
        self.assertEqual(result["next_action"], "doctor_cancel")

    @patch("app.backend_client.fetch_doctor_appointments")
    @patch("app.chatbot_doctor.classify")
    def test_reschedule_sets_last_doctor_action(self, mock_classify, mock_fetch):
        """After reschedule routing, session['last_doctor_action'] should be 'reschedule'."""
        mock_classify.return_value = {"intent": "reschedule", "doctor_name": None}
        mock_fetch.return_value = []

        session = new_session(str(uuid.uuid4()), "test_patient")
        self.assertIsNone(session.get("last_doctor_action"))
        result = handle_doctor_message(
            session=session,
            message="Reschedule",
            authorization=self.authorization,
            doctor_context=self.doctor_context,
        )

        self.assertEqual(session["last_doctor_action"], "reschedule")
        # Also prove routing reached _doctor_reschedule (not just session mutation)
        self.assertEqual(result["next_action"], "doctor_reschedule")


    @patch("app.backend_client.fetch_doctor_appointments")
    @patch("app.chatbot_doctor._match_appointment_by_patient")
    @patch("app.chatbot_doctor.classify")
    def test_patient_details_nlu_name_reaches_matcher(self, mock_classify, mock_match, mock_fetch):
        """NLU patient_name must reach _match_appointment_by_patient even when message has no name tokens."""
        mock_classify.return_value = {"intent": "patient_details", "doctor_name": None, "patient_name": "علی"}
        mock_fetch.return_value = [{"appointment_id": "1", "patient_name": "علی احمد"}]
        mock_match.return_value = []  # No match — we just need to verify the call

        session = new_session(str(uuid.uuid4()), "test_patient")
        handle_doctor_message(
            session=session,
            message="ڈیٹیل دکھاؤ",  # No name in message itself
            authorization=self.authorization,
            doctor_context=self.doctor_context,
        )

        # Verify NLU patient_name was forwarded to the matcher
        _, kwargs = mock_match.call_args
        self.assertEqual(kwargs.get("nlu_patient_name"), "علی")

    @patch("app.chatbot_doctor.classify")
    def test_appointment_intent_not_treated_as_valid_action(self, mock_classify):
        """NLU intent='appointment' should be rejected, not stored as a valid doctor action."""
        mock_classify.return_value = {"intent": "appointment", "doctor_name": None}

        session = new_session(str(uuid.uuid4()), "test_patient")
        result = handle_doctor_message(
            session=session,
            message="Book a new appointment",
            authorization=self.authorization,
            doctor_context=self.doctor_context,
        )

        self.assertEqual(result["next_action"], "doctor_unsupported")
        # Must NOT set last_doctor_action to "appointment" — that would break pending selection
        self.assertNotEqual(session.get("last_doctor_action"), "appointment")


class TestDoctorUrduScriptPatientMatching(unittest.TestCase):
    """Test that _match_appointment_by_patient supports Urdu script via NLU name."""

    def test_latin_name_matching(self):
        """Latin script patient names match via shared tokens."""
        appointments = [
            {"patient_name": "Ali Ahmed", "appointment_id": "1"},
            {"patient_name": "Fatima Khan", "appointment_id": "2"},
        ]
        matches = _match_appointment_by_patient(appointments, "show Ali details")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["appointment_id"], "1")

    def test_urdu_script_name_via_nlu(self):
        """Urdu script NLU name matches Urdu script patient_name via non-Latin chars."""
        appointments = [
            {"patient_name": "علی احمد", "appointment_id": "1"},
            {"patient_name": "فاطمہ خان", "appointment_id": "2"},
        ]
        # NLU extracts "علی" — non-Latin chars ل, ی should match patient_name chars
        matches = _match_appointment_by_patient(
            appointments, "ڈیٹیل دکھاؤ", nlu_patient_name="علی"
        )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["patient_name"], "علی احمد")

    def test_roman_urdu_name_via_nlu(self):
        """Roman Urdu NLU name matches Latin patient_name via shared tokens."""
        appointments = [
            {"patient_name": "Ali Ahmed", "appointment_id": "1"},
            {"patient_name": "Fatima Khan", "appointment_id": "2"},
        ]
        matches = _match_appointment_by_patient(
            appointments, "detail dikhao", nlu_patient_name="Ali"
        )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["patient_name"], "Ali Ahmed")

    def test_no_match_returns_empty(self):
        """No overlapping tokens → empty result."""
        appointments = [
            {"patient_name": "Ali Ahmed", "appointment_id": "1"},
        ]
        matches = _match_appointment_by_patient(appointments, "show Bilal details")
        self.assertEqual(len(matches), 0)

    def test_no_match_short_tokens_ignored(self):
        """Tokens ≤ 2 chars are ignored — single-char message doesn't false-match."""
        appointments = [
            {"patient_name": "Ali Ahmed", "appointment_id": "1"},
        ]
        matches = _match_appointment_by_patient(appointments, "a")
        self.assertEqual(len(matches), 0)


class TestDoctorPendingSelectionLogic(unittest.TestCase):
    """Pending selection logic: if last_doctor_action + selected_id exist,
    route to cancel/reschedule even if NLU returns an unrelated intent.
    """

    def setUp(self):
        self.doctor_context = {
            "doctor_id": str(uuid.uuid4()),
            "name": "Dr. Test Doctor",
            "user_id": str(uuid.uuid4()),
        }
        self.authorization = "Bearer fake_token"

    @patch("app.backend_client.cancel_appointment")
    @patch("app.chatbot_doctor.classify")
    def test_pending_cancel_with_cached_appointments(self, mock_classify, mock_cancel):
        """Pending cancel + cached appointment → routes to _doctor_cancel, not NLU intent."""
        appt_id = str(uuid.uuid4())
        # NLU returns unrelated intent — pending selection should override
        mock_classify.return_value = {"intent": "faq", "doctor_name": None}
        mock_cancel.return_value = {"appointment_id": appt_id, "status": "cancelled"}

        session = new_session(str(uuid.uuid4()), "test_patient")
        session["last_doctor_action"] = "cancel"
        session["doctor_selected_appointment_id"] = appt_id
        session["doctor_appointments"] = [
            {"appointment_id": appt_id, "patient_name": "Test Patient"}
        ]

        result = handle_doctor_message(
            session=session,
            message=f"yes cancel {appt_id}",
            authorization=self.authorization,
            doctor_context=self.doctor_context,
        )

        self.assertEqual(result["next_action"], "doctor_cancel")
        mock_cancel.assert_called_once()

    @patch("app.backend_client.list_doctors")
    @patch("app.chatbot_doctor.classify")
    def test_pending_reschedule_with_cached_appointments(self, mock_classify, mock_list):
        """Pending reschedule + cached appointment → routes to _doctor_reschedule."""
        appt_id = str(uuid.uuid4())
        mock_classify.return_value = {"intent": "faq", "doctor_name": None}
        # list_doctors must return a real iterable (empty) to avoid TypeError
        mock_list.return_value = []

        session = new_session(str(uuid.uuid4()), "test_patient")
        session["last_doctor_action"] = "reschedule"
        session["doctor_selected_appointment_id"] = appt_id
        session["doctor_appointments"] = [
            {"appointment_id": appt_id, "patient_name": "Test Patient", "doctor_id": ""}
        ]

        result = handle_doctor_message(
            session=session,
            message="confirm reschedule",
            authorization=self.authorization,
            doctor_context=self.doctor_context,
        )

        self.assertEqual(result["next_action"], "doctor_reschedule")

    @patch("app.backend_client.cancel_appointment")
    @patch("app.chatbot_doctor.classify")
    def test_pending_cancel_session_only_no_id_in_message(self, mock_classify, mock_cancel):
        """Pending cancel via session state (no ID in message) should still route to _doctor_cancel."""
        appt_id = str(uuid.uuid4())
        mock_classify.return_value = {"intent": "faq", "doctor_name": None}
        mock_cancel.return_value = {"appointment_id": appt_id, "status": "cancelled"}

        session = new_session(str(uuid.uuid4()), "test_patient")
        session["last_doctor_action"] = "cancel"
        session["doctor_selected_appointment_id"] = appt_id  # Only in session, not in message
        session["doctor_appointments"] = [
            {"appointment_id": appt_id, "patient_name": "Test Patient"}
        ]

        # Message has NO appointment ID — pending selection comes from session state only
        result = handle_doctor_message(
            session=session,
            message="yes confirm",
            authorization=self.authorization,
            doctor_context=self.doctor_context,
        )

        self.assertEqual(result["next_action"], "doctor_cancel")
        mock_cancel.assert_called_once()


class TestDoctorNoHardcodedKeywords(unittest.TestCase):
    """Regression guard: verify chatbot_doctor uses NLU, not hardcoded keywords."""

    def test_no_hardcoded_english_keywords(self):
        """handle_doctor_message source must not contain old-style keyword checks,
        and MUST use NLU intent for routing (positive + negative assertions)."""
        source = inspect.getsource(handle_doctor_message)
        # Negative: old keyword patterns must not exist
        self.assertNotIn('"cancel" in lower', source)
        self.assertNotIn('"reschedule" in lower', source)
        self.assertNotIn('"show" in lower', source)
        self.assertNotIn('"detail" in lower', source)
        # Positive: NLU intent must drive routing
        self.assertIn('intent == "cancel"', source)
        self.assertIn('intent == "reschedule"', source)
        self.assertIn('intent == "lookup"', source)
        self.assertIn('intent == "patient_details"', source)

    def test_uses_classify_for_routing(self):
        """handle_doctor_message source must call classify() for intent detection."""
        source = inspect.getsource(handle_doctor_message)
        self.assertIn("classify(", source)
        self.assertIn('nlu.get("intent")', source)


if __name__ == "__main__":
    unittest.main()
