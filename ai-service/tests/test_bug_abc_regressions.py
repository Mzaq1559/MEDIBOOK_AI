"""
Regression tests for Bug A, B, and C (post-Bug-5-fix regressions).

BUG A: "heart ache" was not classified to Cardiologist by recommend_specialty.
BUG B: Doctor flow broken — "Selected Appointment", "Reschedule", "Cancel"
       all returned doctor_unsupported after Bug 5 dispatcher changes.
BUG C: Allergy extraction regex truncated "peanuts and eggs" at "and".
"""

import uuid
import unittest
from unittest.mock import patch, MagicMock


DOCTOR_USER_ID = "user-doctor-321"
DOCTOR_ID = "doc-202"
MOCK_APPTS = [{
    "appointment_id": "appt-001",
    "doctor_id": DOCTOR_ID,
    "patient_id": "pat-3",
    "patient_name": "Alice Smith",
    "appointment_time": "2026-09-04T14:00:00Z",
    "status": "scheduled",
    "symptoms_reported": "headache",
}]
MOCK_DOCTOR_CTX = {
    "doctor_id": DOCTOR_ID,
    "user_id": DOCTOR_USER_ID,
    "name": "Dr. Ahmed Khan",
}


# ──────────────────────────────────────────────────────────────────────
# BUG A: Specialty filtering regression
# ──────────────────────────────────────────────────────────────────────
class TestBugA_SpecialtyFiltering(unittest.TestCase):
    """Verify that heart-related symptoms route to Cardiologist."""

    def test_heart_ache_recommends_cardiologist(self):
        from app.symptom_triage import recommend_specialty
        self.assertEqual(recommend_specialty("heart ache"), "Cardiologist")

    def test_heartache_one_word_recommends_cardiologist(self):
        from app.symptom_triage import recommend_specialty
        self.assertEqual(recommend_specialty("heartache"), "Cardiologist")

    def test_heart_pain_recommends_cardiologist(self):
        from app.symptom_triage import recommend_specialty
        self.assertEqual(recommend_specialty("heart pain"), "Cardiologist")

    def test_heart_problem_recommends_cardiologist(self):
        from app.symptom_triage import recommend_specialty
        self.assertEqual(recommend_specialty("heart problem"), "Cardiologist")

    def test_heart_condition_recommends_cardiologist(self):
        from app.symptom_triage import recommend_specialty
        self.assertEqual(recommend_specialty("heart condition"), "Cardiologist")

    def test_existing_chest_pain_still_cardiologist(self):
        from app.symptom_triage import recommend_specialty
        self.assertEqual(recommend_specialty("chest pain"), "Cardiologist")

    def test_rashes_still_dermatologist(self):
        from app.symptom_triage import recommend_specialty
        self.assertEqual(recommend_specialty("rashes"), "Dermatologist")

    def test_triage_heart_ache_routes_to_cardiology(self):
        from app.symptom_triage import triage
        result = triage("heart ache")
        self.assertFalse(result.is_emergency)
        self.assertEqual(result.specialty, "Cardiologist")

    def test_triage_heart_ache_high_urgency(self):
        from app.symptom_triage import triage
        result = triage("heart ache")
        self.assertEqual(result.urgency_level, "high")


# ──────────────────────────────────────────────────────────────────────
# BUG B: Doctor flow regression
# ──────────────────────────────────────────────────────────────────────
class TestBugB_DoctorFlow(unittest.TestCase):
    """Verify the doctor flow works for show/select/reschedule/cancel."""

    def _call_handle_message(self, message, session_overrides=None):
        """Call handle_message as a doctor user with mocked backend."""
        from app.chatbot import handle_message
        from app.chatbot_state import get_session, new_session
        conv_id = str(uuid.uuid4())

        # Pre-create session so we can inject state
        session = new_session(conv_id, DOCTOR_USER_ID)
        if session_overrides:
            session.update(session_overrides)

        return handle_message(
            conversation_id=conv_id,
            patient_id=DOCTOR_USER_ID,
            message=message,
            language="en",
            authorization="Bearer mock_token",
        )

    @patch("app.backend_client.get_current_user", return_value={"user_id": DOCTOR_USER_ID, "user_type": "doctor"})
    @patch("app.backend_client.list_doctors", return_value=[MOCK_DOCTOR_CTX])
    @patch("app.backend_client.fetch_doctor_appointments", return_value=MOCK_APPTS)
    def test_show_my_appointments_works(self, mock_appts, mock_docs, mock_user):
        res = self._call_handle_message("Show my appointments")
        self.assertEqual(res["next_action"], "doctor_appointments")
        self.assertIn("Alice Smith", res["bot_message"])

    @patch("app.backend_client.get_current_user", return_value={"user_id": DOCTOR_USER_ID, "user_type": "doctor"})
    @patch("app.backend_client.list_doctors", return_value=[MOCK_DOCTOR_CTX])
    @patch("app.backend_client.fetch_doctor_appointments", return_value=MOCK_APPTS)
    @patch("app.backend_client.get_appointment_details", return_value={
        **MOCK_APPTS[0], "urgency_level": "normal", "notes": "test",
    })
    def test_selected_appointment_shows_details(self, mock_detail, mock_appts, mock_docs, mock_user):
        """Clicking 'Selected Appointment' must NOT return doctor_unsupported."""
        # First show appointments to populate session
        res1 = self._call_handle_message("Show my appointments")
        self.assertEqual(res1["next_action"], "doctor_appointments")

        # Now select an appointment using UUID
        from app.chatbot import handle_message
        conv_id2 = str(uuid.uuid4())
        from app.chatbot_state import new_session
        session = new_session(conv_id2, DOCTOR_USER_ID)
        session["doctor_appointments"] = MOCK_APPTS
        session["last_doctor_action"] = "lookup"

        res2 = handle_message(
            conversation_id=conv_id2,
            patient_id=DOCTOR_USER_ID,
            message=f"Selected Appointment {MOCK_APPTS[0]['appointment_id']}",
            language="en",
            authorization="Bearer mock_token",
        )
        # Must NOT be doctor_unsupported
        self.assertNotEqual(res2["next_action"], "doctor_unsupported")

    @patch("app.backend_client.get_current_user", return_value={"user_id": DOCTOR_USER_ID, "user_type": "doctor"})
    @patch("app.backend_client.list_doctors", return_value=[MOCK_DOCTOR_CTX])
    @patch("app.backend_client.fetch_doctor_appointments", return_value=MOCK_APPTS)
    def test_reschedule_patients_appointment_routes_correctly(self, mock_appts, mock_docs, mock_user):
        """'Reschedule a patient's appointment' must enter reschedule flow."""
        res = self._call_handle_message("Reschedule a patient's appointment")
        self.assertNotEqual(res["next_action"], "doctor_unsupported")
        self.assertEqual(res["next_action"], "doctor_reschedule")

    @patch("app.backend_client.get_current_user", return_value={"user_id": DOCTOR_USER_ID, "user_type": "doctor"})
    @patch("app.backend_client.list_doctors", return_value=[MOCK_DOCTOR_CTX])
    @patch("app.backend_client.fetch_doctor_appointments", return_value=MOCK_APPTS)
    def test_cancel_patients_appointment_routes_correctly(self, mock_appts, mock_docs, mock_user):
        """'Cancel a patient's appointment' must enter cancel flow."""
        res = self._call_handle_message("Cancel a patient's appointment")
        self.assertNotEqual(res["next_action"], "doctor_unsupported")
        self.assertEqual(res["next_action"], "doctor_cancel")

    def test_resolve_doctor_selection_accepts_nlu_param(self):
        """_resolve_doctor_selection must accept nlu kwarg without TypeError."""
        from app.chatbot_doctor import _resolve_doctor_selection
        # Call with nlu=None (default) — must not raise
        selected, ambiguous = _resolve_doctor_selection(
            session={},
            appointments=MOCK_APPTS,
            message="selected appointment",
            nlu={"doctor_name": "Alice Smith"},
        )
        # Single appointment + "selected appointment" → selects it
        self.assertIsNotNone(selected)

    def test_resolve_doctor_selection_with_nlu_doctor_name(self):
        """_resolve_doctor_selection uses NLU doctor_name for matching."""
        from app.chatbot_doctor import _resolve_doctor_selection
        appts = [
            {"appointment_id": "a1", "patient_name": "Alice", "appointment_time": "2026-09-04T09:00"},
            {"appointment_id": "a2", "patient_name": "Bob", "appointment_time": "2026-09-04T10:00"},
        ]
        selected, ambiguous = _resolve_doctor_selection(
            session={},
            appointments=appts,
            message="show Alice",
            nlu={"doctor_name": "Alice"},
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected["patient_name"], "Alice")

    @patch("app.backend_client.get_current_user", return_value={"user_id": DOCTOR_USER_ID, "user_type": "doctor"})
    @patch("app.backend_client.list_doctors", return_value=[MOCK_DOCTOR_CTX])
    @patch("app.backend_client.fetch_doctor_appointments", return_value=MOCK_APPTS)
    def test_show_appointments_sets_last_doctor_action(self, mock_appts, mock_docs, mock_user):
        """_doctor_show_appointments must set last_doctor_action='lookup'."""
        from app.chatbot_doctor import _doctor_show_appointments
        session = {}
        result = _doctor_show_appointments(DOCTOR_ID, "Bearer token", "show", session)
        self.assertEqual(session.get("last_doctor_action"), "lookup")


# ──────────────────────────────────────────────────────────────────────
# BUG C: Medical history (allergy) extraction
# ──────────────────────────────────────────────────────────────────────
class TestBugC_AllergyExtraction(unittest.TestCase):
    """Verify extract_medical_history captures compound allergens."""

    def test_allergic_to_peanuts_and_eggs(self):
        from app.chatbot_handlers import extract_medical_history
        history = extract_medical_history("i am allergic to peanuts and eggs")
        self.assertTrue(any("peanuts" in a for a in history["allergies"]))
        self.assertTrue(any("eggs" in a for a in history["allergies"]))

    def test_allergic_to_single_allergen(self):
        from app.chatbot_handlers import extract_medical_history
        history = extract_medical_history("I am allergic to penicillin")
        self.assertEqual(history["allergies"], ["penicillin"])

    def test_allergic_with_period_terminator(self):
        from app.chatbot_handlers import extract_medical_history
        history = extract_medical_history("allergic to shellfish and nuts.")
        self.assertTrue(any("shellfish" in a for a in history["allergies"]))
        self.assertTrue(any("nuts" in a for a in history["allergies"]))

    def test_comma_separated_allergies(self):
        from app.chatbot_handlers import extract_medical_history
        history = extract_medical_history("allergic to peanuts, eggs, and milk")
        # Comma is a separator, so first match captures "peanuts"
        self.assertIn("peanuts", history["allergies"])

    def test_allergy_with_conditions(self):
        from app.chatbot_handlers import extract_medical_history
        history = extract_medical_history("I have diabetes and allergic to penicillin")
        self.assertIn("diabetes", history["conditions"])
        self.assertIn("penicillin", history["allergies"])

    def test_intolerant_to_lactose(self):
        from app.chatbot_handlers import extract_medical_history
        history = extract_medical_history("I am intolerant to lactose and gluten")
        self.assertTrue(any("lactose" in a for a in history["allergies"]))
        self.assertTrue(any("gluten" in a for a in history["allergies"]))

    def test_build_patient_summary_includes_allergies(self):
        from app.chatbot_handlers import build_patient_summary, extract_medical_history
        history = extract_medical_history("i am allergic to peanuts and eggs")
        summary = build_patient_summary("headache", "normal", history)
        # The summary should mention allergies
        self.assertIn("allergies", summary.lower())


if __name__ == "__main__":
    unittest.main()
