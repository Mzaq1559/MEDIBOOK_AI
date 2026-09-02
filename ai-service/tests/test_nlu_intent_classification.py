"""
Tests: NLU intent classification and entity extraction for Urdu/Roman Urdu support.

Verifies fixes for:
1. Urdu/Roman Urdu cancel/reschedule/lookup phrases correctly classified via regex overrides
2. Doctor name and specialty extraction from mid-sentence and Urdu script mentions
3. State-based routing uses explicit tuple checks instead of fragile startswith()
4. ASKING_SYMPTOMS/ASKING_FOLLOWUP states properly reset when user sends cancel/reschedule/lookup
5. Confirm/decline fast-path not hijacked by CANCEL_RE/RESCHEDULE_RE overrides
"""

import inspect
import uuid
import unittest
from unittest.mock import patch, MagicMock
from app.chatbot_nlu import classify, CANCEL_RE, RESCHEDULE_RE, LOOKUP_RE
from app.chatbot_handlers import LOGIN_REQ_CANCEL, LOGIN_REQ_RESCHEDULE, LOGIN_REQ_LOOKUP
from app.chatbot_state import S, new_session, get_session
from app.schemas import MessageItem


class TestNLURegexOverrides(unittest.TestCase):
    """Test Bug 1: Urdu/Roman Urdu cancel/reschedule/lookup regex overrides."""

    def test_urdu_cancel_phrase(self):
        """Urdu script cancel phrase should be classified as cancel."""
        text = "میری اپوائنٹمنٹ کینسل کر دو"
        self.assertIsNotNone(CANCEL_RE.search(text))

    def test_urdu_reschedule_phrase(self):
        """Urdu script reschedule phrase should be classified as reschedule."""
        text = "وقت تبدیل کرنا ہے"
        self.assertIsNotNone(RESCHEDULE_RE.search(text))

    def test_roman_urdu_cancel(self):
        """Roman Urdu cancel phrase should be classified as cancel."""
        text = "appointment hata do"
        self.assertIsNotNone(CANCEL_RE.search(text))

    def test_roman_urdu_reschedule(self):
        """Roman Urdu reschedule phrase should be classified as reschedule."""
        text = "appointment reschedule karni hai"
        self.assertIsNotNone(RESCHEDULE_RE.search(text))

    def test_roman_urdu_lookup(self):
        """Roman Urdu lookup phrase should match LOOKUP_RE."""
        text = "meri appointment dikhao"
        self.assertIsNotNone(LOOKUP_RE.search(text))

    def test_urdu_lookup(self):
        """Urdu script lookup phrase should match LOOKUP_RE."""
        text = "میری اپوائنٹمنٹ دکھاؤ"
        self.assertIsNotNone(LOOKUP_RE.search(text))

    @patch("app.groq_client.complete_json")
    def test_classify_urdu_cancel(self, mock_complete_json):
        """classify() should return intent='cancel' for Urdu cancel phrase."""
        mock_complete_json.return_value = {"intent": "symptom", "doctor_name": None}
        history = []
        result = classify("میری اپوائنٹمنٹ کینسل کر دو", history, S.IDLE)
        self.assertEqual(result["intent"], "cancel")

    @patch("app.groq_client.complete_json")
    def test_classify_urdu_reschedule(self, mock_complete_json):
        """classify() should return intent='reschedule' for Urdu reschedule phrase."""
        mock_complete_json.return_value = {"intent": "symptom", "doctor_name": None}
        history = []
        result = classify("وقت تبدیل کرنا ہے", history, S.IDLE)
        self.assertEqual(result["intent"], "reschedule")

    @patch("app.groq_client.complete_json")
    def test_classify_roman_urdu_cancel(self, mock_complete_json):
        """classify() should return intent='cancel' for Roman Urdu cancel phrase."""
        mock_complete_json.return_value = {"intent": "symptom", "doctor_name": None}
        history = []
        result = classify("meri appointment hata do", history, S.IDLE)
        self.assertEqual(result["intent"], "cancel")

    @patch("app.groq_client.complete_json")
    def test_classify_roman_urdu_reschedule(self, mock_complete_json):
        """classify() should return intent='reschedule' for Roman Urdu reschedule phrase."""
        mock_complete_json.return_value = {"intent": "symptom", "doctor_name": None}
        history = []
        result = classify("appointment reschedule karni hai", history, S.IDLE)
        self.assertEqual(result["intent"], "reschedule")

    @patch("app.groq_client.complete_json")
    def test_classify_roman_urdu_lookup(self, mock_complete_json):
        """classify() should return intent='lookup' for Roman Urdu lookup phrase.
        
        FIX A: Mock LLM to return WRONG intent ("symptom") to prove the regex override
        corrects it to "lookup" — this exercises the actual production code path.
        """
        mock_complete_json.return_value = {"intent": "symptom", "doctor_name": None}
        history = []
        result = classify("meri appointment dikhao", history, S.IDLE)
        self.assertEqual(result["intent"], "lookup")

    @patch("app.groq_client.complete_json")
    def test_classify_urdu_lookup(self, mock_complete_json):
        """classify() should return intent='lookup' for Urdu script lookup phrase."""
        mock_complete_json.return_value = {"intent": "symptom", "doctor_name": None}
        history = []
        result = classify("میری اپوائنٹمنٹ دکھاؤ", history, S.IDLE)
        self.assertEqual(result["intent"], "lookup")

    @patch("app.groq_client.complete_json")
    def test_priority_cancel_over_lookup(self, mock_complete_json):
        """Cancel should take priority over lookup when both patterns match."""
        mock_complete_json.return_value = {"intent": "lookup", "doctor_name": None}
        history = []
        # This message matches both CANCEL_RE ("cancel") and LOOKUP_RE ("appointment")
        result = classify("cancel my appointment and show", history, S.IDLE)
        self.assertEqual(result["intent"], "cancel")


class TestNLUEntityExtraction(unittest.TestCase):
    """Test Bug 2: Doctor name and specialty extraction from various contexts."""

    @patch("app.groq_client.complete_json")
    def test_extract_doctor_name_english(self, mock_complete_json):
        """Doctor name in English should be extracted."""
        mock_complete_json.return_value = {
            "intent": "appointment",
            "doctor_name": "Dr. Fatima",
            "specialty": None,
        }
        history = []
        result = classify("book appointment with Dr. Fatima", history, S.IDLE)
        self.assertIn("Fatima", result["doctor_name"])

    @patch("app.groq_client.complete_json")
    def test_extract_doctor_name_roman_urdu(self, mock_complete_json):
        """Doctor name in Roman Urdu should be extracted."""
        mock_complete_json.return_value = {
            "intent": "appointment",
            "doctor_name": "Dr Fatima",
            "specialty": None,
        }
        history = []
        result = classify("Dr Fatima se milna hai", history, S.IDLE)
        self.assertIn("Fatima", result["doctor_name"])

    @patch("app.groq_client.complete_json")
    def test_extract_doctor_name_urdu_script(self, mock_complete_json):
        """Doctor name in Urdu script should be extracted."""
        mock_complete_json.return_value = {
            "intent": "show_doctors",
            "doctor_name": "ڈاکٹر فاطمہ",
            "specialty": None,
        }
        history = []
        result = classify("بس ڈاکٹر فاطمہ کو دکھاؤ", history, S.IDLE)
        self.assertIsNotNone(result["doctor_name"])
        # Should contain either the Urdu script or the transliterated name
        self.assertTrue("فاطمہ" in result["doctor_name"] or "Fatima" in result["doctor_name"])

    @patch("app.groq_client.complete_json")
    def test_extract_specialty_mid_followup(self, mock_complete_json):
        """Specialty mentioned mid-followup should be extracted."""
        mock_complete_json.return_value = {
            "intent": "appointment",
            "doctor_name": None,
            "specialty": "dermatologist",
        }
        history = [
            MessageItem(role="assistant", message="What are your symptoms?", timestamp="2026-09-02T10:00:00Z"),
            MessageItem(role="user", message="skin rash", timestamp="2026-09-02T10:01:00Z"),
            MessageItem(role="assistant", message="Any other symptoms?", timestamp="2026-09-02T10:02:00Z"),
        ]
        result = classify("I need to see a dermatologist", history, S.ASKING_FOLLOWUP)
        self.assertIsNotNone(result["specialty"])
        self.assertIn("dermatologist", result["specialty"].lower())


class TestStateBasedRouting(unittest.TestCase):
    """FIX C: Test that state-based routing actually works end-to-end.
    
    These tests verify that the router in chatbot.py correctly handles
    cancel/reschedule states by calling handle_message() and checking
    that the appropriate handler is reached.
    """

    @patch("app.backend_client.fetch_patient_appointments")
    @patch("app.groq_client.complete_json")
    def test_cancel_pick_state_routes_to_cancel(self, mock_complete_json, mock_fetch_appts):
        """Session in CANCEL_PICK should route to cancel flow even if NLU returns unrelated intent."""
        from app.chatbot import handle_message

        # Mock NLU to return "patient_details" — an intent that doesn't match any early branch,
        # so the router falls through to the state-based cancel check on line 270.
        mock_complete_json.return_value = {"intent": "patient_details", "doctor_name": None}
        mock_fetch_appts.return_value = []

        conv_id = str(uuid.uuid4())
        session = new_session(conv_id, "test_patient")
        session["state"] = S.CANCEL_PICK
        session["patient_appointments"] = []

        result = handle_message(
            conversation_id=conv_id,
            patient_id="test_patient",
            message="which one",
            language="en",
            authorization=None,  # No auth → handle_cancel returns LOGIN_REQ_CANCEL
        )

        # No auth → handle_cancel short-circuits with LOGIN_REQ_CANCEL + "waiting_for_login"
        self.assertEqual(result["next_action"], "waiting_for_login")
        self.assertEqual(result["bot_message"], LOGIN_REQ_CANCEL)

    @patch("app.backend_client.fetch_patient_appointments")
    @patch("app.groq_client.complete_json")
    def test_reschedule_pick_state_routes_to_reschedule(self, mock_complete_json, mock_fetch_appts):
        """Session in RESCHEDULE_PICK should route to reschedule flow even if NLU returns unrelated intent."""
        from app.chatbot import handle_message

        # Mock NLU to return "patient_details" — an intent that doesn't match any early branch,
        # so the router falls through to the state-based reschedule check on line 273.
        mock_complete_json.return_value = {"intent": "patient_details", "doctor_name": None}
        mock_fetch_appts.return_value = []

        conv_id = str(uuid.uuid4())
        session = new_session(conv_id, "test_patient")
        session["state"] = S.RESCHEDULE_PICK
        session["patient_appointments"] = []

        result = handle_message(
            conversation_id=conv_id,
            patient_id="test_patient",
            message="which one",
            language="en",
            authorization=None,
        )

        # No auth → handle_reschedule short-circuits with LOGIN_REQ_RESCHEDULE + "waiting_for_login"
        self.assertEqual(result["next_action"], "waiting_for_login")
        self.assertEqual(result["bot_message"], LOGIN_REQ_RESCHEDULE)

    def test_no_startswith_in_chatbot_source(self):
        """Regression guard: chatbot.py should not use startswith() for state checks."""
        from app import chatbot
        source = inspect.getsource(chatbot.handle_message)
        self.assertNotIn('startswith("cancel")', source)
        self.assertNotIn('startswith("reschedule")', source)


class TestAskingSymptomsStateReset(unittest.TestCase):
    """FIX B: Test that ASKING_SYMPTOMS/ASKING_FOLLOWUP states reset end-to-end.
    
    These tests call handle_message() directly to verify the full routing path,
    not just _reset_patient_workflow in isolation.
    """

    @patch("app.groq_client.complete_json")
    def test_cancel_from_asking_symptoms(self, mock_complete_json):
        """User in ASKING_SYMPTOMS sending cancel should route to handle_cancel."""
        from app.chatbot import handle_message

        mock_complete_json.return_value = {"intent": "cancel", "doctor_name": None}

        conv_id = str(uuid.uuid4())
        session = new_session(conv_id, "test_patient")
        session["state"] = S.ASKING_SYMPTOMS
        session["symptoms_text"] = "chest pain"

        result = handle_message(
            conversation_id=conv_id,
            patient_id="test_patient",
            message="میری اپوائنٹمنٹ کینسل کر دو",
            language="ur",
            authorization=None,  # No auth → handle_cancel returns login required
        )

        # No auth → handle_cancel short-circuits with LOGIN_REQ_CANCEL + "waiting_for_login"
        self.assertEqual(result["next_action"], "waiting_for_login")
        self.assertEqual(result["bot_message"], LOGIN_REQ_CANCEL)

    @patch("app.groq_client.complete_json")
    def test_reschedule_from_asking_followup(self, mock_complete_json):
        """User in ASKING_FOLLOWUP sending reschedule should route to handle_reschedule."""
        from app.chatbot import handle_message

        mock_complete_json.return_value = {"intent": "reschedule", "doctor_name": None}

        conv_id = str(uuid.uuid4())
        session = new_session(conv_id, "test_patient")
        session["state"] = S.ASKING_FOLLOWUP
        session["symptoms_text"] = "headache"

        result = handle_message(
            conversation_id=conv_id,
            patient_id="test_patient",
            message="appointment reschedule karni hai",
            language="en",
            authorization=None,
        )

        # No auth → handle_reschedule short-circuits with LOGIN_REQ_RESCHEDULE + "waiting_for_login"
        self.assertEqual(result["next_action"], "waiting_for_login")
        self.assertEqual(result["bot_message"], LOGIN_REQ_RESCHEDULE)

    @patch("app.groq_client.complete_json")
    def test_lookup_from_asking_symptoms(self, mock_complete_json):
        """User in ASKING_SYMPTOMS sending lookup should route to handle_lookup."""
        from app.chatbot import handle_message

        mock_complete_json.return_value = {"intent": "lookup", "doctor_name": None}

        conv_id = str(uuid.uuid4())
        session = new_session(conv_id, "test_patient")
        session["state"] = S.ASKING_SYMPTOMS
        session["symptoms_text"] = "fever"

        result = handle_message(
            conversation_id=conv_id,
            patient_id="test_patient",
            message="meri appointment dikhao",
            language="en",
            authorization=None,
        )

        # No auth → handle_lookup short-circuits with LOGIN_REQ_LOOKUP + "waiting_for_login"
        self.assertEqual(result["next_action"], "waiting_for_login")
        self.assertEqual(result["bot_message"], LOGIN_REQ_LOOKUP)


class TestConfirmDeclineNotOverridden(unittest.TestCase):
    """FIX D: Test that CANCEL_RE/RESCHEDULE_RE do NOT hijack confirm/decline fast-path.
    
    The fast-path in classify() returns early before reaching the regex override block,
    so "no cancel it" in AWAIT_CONFIRM should return declines=True, not intent="cancel".
    """

    def test_decline_in_await_confirm_not_hijacked(self):
        """'no cancel it' in AWAIT_CONFIRM should return declines=True, not intent='cancel'."""
        history = []
        result = classify("no cancel it", history, S.AWAIT_CONFIRM)
        
        # Fast-path should fire: declines=True, intent="appointment"
        self.assertTrue(result["declines"])
        self.assertEqual(result["intent"], "appointment")
        # Should NOT be overridden to intent="cancel"
        self.assertNotEqual(result["intent"], "cancel")

    def test_decline_in_reschedule_confirm_not_hijacked(self):
        """'no cancel it' in RESCHEDULE_CONFIRM should return declines=True, not intent='cancel'."""
        history = []
        result = classify("no cancel it", history, S.RESCHEDULE_CONFIRM)
        
        self.assertTrue(result["declines"])
        self.assertEqual(result["intent"], "appointment")
        self.assertNotEqual(result["intent"], "cancel")

    def test_decline_in_cancel_confirm_not_hijacked(self):
        """'no cancel it' in CANCEL_CONFIRM should return declines=True, not intent='cancel'."""
        history = []
        result = classify("no cancel it", history, S.CANCEL_CONFIRM)
        
        self.assertTrue(result["declines"])
        self.assertEqual(result["intent"], "appointment")
        self.assertNotEqual(result["intent"], "cancel")

    def test_confirm_in_await_confirm_not_hijacked(self):
        """'yes confirm' in AWAIT_CONFIRM should return confirms=True, not intent='cancel'."""
        history = []
        result = classify("yes confirm", history, S.AWAIT_CONFIRM)
        
        self.assertTrue(result["confirms"])
        self.assertEqual(result["intent"], "appointment")

    def test_reschedule_keyword_in_reschedule_confirm_not_hijacked(self):
        """'reschedule' keyword in RESCHEDULE_CONFIRM should still return declines=True if decline pattern present."""
        history = []
        # "no" triggers decline, "reschedule" would normally trigger RESCHEDULE_RE
        # But fast-path should fire first
        result = classify("no reschedule", history, S.RESCHEDULE_CONFIRM)
        
        self.assertTrue(result["declines"])
        self.assertEqual(result["intent"], "appointment")


if __name__ == "__main__":
    unittest.main()
