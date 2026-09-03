"""Regression tests for defensive data handling in slot/doctor serialization
and graceful error recovery in the booking flow.

Covers:
1. slots_ui_data() does not crash on malformed slot dicts (missing fields).
2. doctors_ui_data() does not crash on malformed doctor dicts (missing fields).
3. _proceed_to_show_doctors() returns a friendly error instead of crashing
   when the backend returns unexpected data, and the session state is NOT
   silently reset to the greeting.
4. Doctor selection with malformed slot data returns a friendly in-chat
   error instead of bubbling a 500 to the generic handler.
"""

import uuid
import unittest
from unittest.mock import patch, MagicMock

from app.chatbot_slots import doctors_ui_data, slots_ui_data
from app.chatbot_state import S


class TestSlotsUiDataDefensive(unittest.TestCase):
    """slots_ui_data must not raise KeyError on malformed slot dicts."""

    def test_missing_time_field_is_skipped(self):
        doc = {"slots": [{"date": "2026-09-05", "timestamp": "2026-09-05T09:00:00+05:00", "label": "Sep 05 at 09:00 AM"}]}
        result = slots_ui_data(doc)
        self.assertEqual(result, [])

    def test_missing_timestamp_field_is_skipped(self):
        doc = {"slots": [{"time": "09:00 AM", "date": "2026-09-05", "label": "Sep 05 at 09:00 AM"}]}
        result = slots_ui_data(doc)
        self.assertEqual(result, [])

    def test_missing_date_defaults_to_empty_string(self):
        doc = {"slots": [{"time": "09:00 AM", "timestamp": "2026-09-05T09:00:00+05:00", "label": "Sep 05 at 09:00 AM"}]}
        result = slots_ui_data(doc)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["date"], "")
        self.assertEqual(result[0]["time"], "09:00 AM")

    def test_missing_label_is_generated(self):
        doc = {"slots": [{"time": "09:00 AM", "date": "2026-09-05", "timestamp": "2026-09-05T09:00:00+05:00"}]}
        result = slots_ui_data(doc)
        self.assertEqual(len(result), 1)
        self.assertIn("09:00 AM", result[0]["label"])

    def test_empty_slots_list(self):
        self.assertEqual(slots_ui_data({"slots": []}), [])
        self.assertEqual(slots_ui_data({}), [])
        self.assertEqual(slots_ui_data({"slots": None}), [])

    def test_mixed_valid_and_malformed_slots(self):
        doc = {"slots": [
            {"time": "09:00 AM", "date": "2026-09-05", "timestamp": "ts1", "label": "slot1"},
            {"date": "2026-09-05"},  # missing time and timestamp — skip
            {"time": "10:00 AM", "timestamp": "ts3", "label": "slot3"},
        ]}
        result = slots_ui_data(doc)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["time"], "09:00 AM")
        self.assertEqual(result[1]["time"], "10:00 AM")


class TestDoctorsUiDataDefensive(unittest.TestCase):
    """doctors_ui_data must not raise KeyError on malformed doctor dicts."""

    def test_missing_doctor_id_is_skipped(self):
        result = doctors_ui_data([{"name": "Dr. X", "specialization": "Cardiology"}])
        self.assertEqual(result, [])

    def test_missing_optional_fields_use_defaults(self):
        doc_id = str(uuid.uuid4())
        result = doctors_ui_data([{"doctor_id": doc_id}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Doctor")
        self.assertEqual(result[0]["specialization"], "")
        self.assertEqual(result[0]["rating"], 0.0)
        self.assertEqual(result[0]["consultation_fee"], 0)

    def test_empty_list(self):
        self.assertEqual(doctors_ui_data([]), [])

    def test_mixed_valid_and_malformed(self):
        doc_id = str(uuid.uuid4())
        result = doctors_ui_data([
            {"doctor_id": doc_id, "name": "Dr. Valid", "specialization": "ENT"},
            {"name": "Dr. NoID"},  # missing doctor_id — skip
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Dr. Valid")


class TestProceedToShowDoctorsGraceful(unittest.TestCase):
    """_proceed_to_show_doctors must catch backend errors and return
    a friendly message instead of crashing the session."""

    @patch("app.chatbot_handlers.fetch_doctor_slots", side_effect=Exception("Backend timeout"))
    @patch("app.chatbot_handlers.backend_client.list_doctors", return_value=[])
    def test_backend_error_returns_friendly_message(self, mock_list, mock_fetch):
        from app.chatbot_handlers import _proceed_to_show_doctors

        session = {"state": S.ASKING_HISTORY, "specialty": None}
        msg, action, options, ui = _proceed_to_show_doctors(session)

        self.assertIn("couldn't load", msg.lower())
        self.assertIn("try again", msg.lower())
        self.assertEqual(action, "waiting_for_input")
        # State should be IDLE (safe reset), NOT silently swallowed
        self.assertEqual(session["state"], S.IDLE)

    @patch("app.chatbot_handlers.fetch_doctor_slots", side_effect=KeyError("unexpected_field"))
    @patch("app.chatbot_handlers.backend_client.list_doctors", return_value=[{"doctor_id": "123"}])
    def test_key_error_does_not_bubble_up(self, mock_list, mock_fetch):
        from app.chatbot_handlers import _proceed_to_show_doctors

        session = {"state": S.ASKING_HISTORY, "specialty": "Cardiology"}
        # Must not raise
        msg, action, options, ui = _proceed_to_show_doctors(session)
        self.assertIn("couldn't load", msg.lower())
        self.assertEqual(session["state"], S.IDLE)


class TestDoctorSelectionSlotError(unittest.TestCase):
    """Doctor selection in SHOWING_DOCTORS must catch slots_ui_data errors
    and return a friendly message instead of a hard 500."""

    @patch("app.chatbot_handlers.slots_ui_data", side_effect=KeyError("timestamp"))
    @patch("app.chatbot_handlers.find_doctor_by_id")
    def test_slots_error_returns_friendly_message(self, mock_find, mock_slots):
        from app.chatbot_handlers import handle_new_booking

        doc_id = str(uuid.uuid4())
        mock_find.return_value = {
            "doctor_id": doc_id,
            "name": "Dr. Test",
            "slots": [{"time": "9AM"}],  # malformed — missing timestamp
        }

        session = {
            "state": S.SHOWING_DOCTORS,
            "candidate_doctors": [mock_find.return_value],
            "specialty": None,
        }
        nlu = {"intent": "select_option", "option_id": doc_id}

        # Must not raise
        msg, action, options, ui = handle_new_booking(session, f"selected appointment {doc_id}", nlu, None)

        self.assertIn("couldn't load", msg.lower())
        self.assertEqual(action, "waiting_for_doctor_selection")
        # State should stay at SHOWING_DOCTORS, NOT reset to IDLE/greeting
        self.assertEqual(session["state"], S.SHOWING_DOCTORS)


class TestMainHandlerReturns500(unittest.TestCase):
    """The generic exception handler in main.py must return 500 (not 400)
    with an accurate error message."""

    @patch("app.main.handle_message", side_effect=RuntimeError("unexpected"))
    def test_generic_error_returns_500(self, mock_handle):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/chat/message",
            json={"message": "test", "conversation_id": str(uuid.uuid4())},
        )
        self.assertEqual(resp.status_code, 500)
        body = resp.json()
        self.assertEqual(body["error_code"], "INTERNAL_ERROR")
        self.assertIn("unexpected", body["message"].lower())


if __name__ == "__main__":
    unittest.main()
