"""Regression test: booking confirmation error response shape.

Covers the white-screen crash caused by double-nested booking data
in the AWAIT_CONFIRM error handler:
    ui = {"booking": {"doctor": doc, ...}}  # ← already wrapped
    return ..., {"booking": ui}             # ← double wrap!

The frontend expects: ui_data.booking.doctor (not ui_data.booking.booking.doctor).
"""
import uuid
import unittest
from unittest.mock import patch, MagicMock

from app.chatbot_handlers import handle_new_booking
from app.chatbot_state import S
from app import backend_client


def _make_session(**overrides):
    """Build a session in AWAIT_CONFIRM state with valid doctor + slot."""
    doc_id = str(uuid.uuid4())
    session = {
        "state": S.AWAIT_CONFIRM,
        "patient_id": str(uuid.uuid4()),
        "selected_doctor": {
            "doctor_id": doc_id,
            "name": "Dr. Test",
            "specialization": "General Medicine",
            "consultation_fee": 2000,
            "rating": 4.5,
            "clinic_name": "Test Clinic",
            "clinic_address": "123 Test St",
            "slots": [{"time": "09:00", "date": "2026-09-05", "timestamp": "2026-09-05T09:00:00+05:00", "label": "Sep 05 at 09:00 AM"}],
        },
        "selected_timestamp": "2026-09-05T09:00:00+05:00",
        "selected_slot_label": "Sep 05 at 09:00 AM",
        "symptoms_text": "headache",
        "urgency_level": "normal",
        "urgency_reason": None,
        "medical_history": None,
        "patient_email": "test@test.com",
        "patient_name": "Test Patient",
        "candidate_doctors": [],
        "follow_ups": [],
        "follow_up_index": 0,
        "specialty": None,
        "messages": [],
    }
    session.update(overrides)
    return session


def _make_nlu(**overrides):
    base = {
        "intent": "appointment", "doctor_name": None, "doctor_id": None,
        "specialty": None, "wants_doctor_list": False, "date": None,
        "symptoms": None, "appointment_id": None, "confirms": True,
        "declines": False, "faq_topic": None, "option_id": None,
    }
    base.update(overrides)
    return base


class TestBookingConfirmationErrorShape(unittest.TestCase):
    """When create_appointment fails, the booking UI data must NOT be double-nested."""

    @patch("app.chatbot_handlers.reminders")
    @patch("app.chatbot_handlers.n8n_webhook")
    @patch("app.chatbot_handlers.google_calendar")
    @patch("app.chatbot_handlers.backend_client.create_appointment")
    def test_error_response_has_flat_booking_shape(self, mock_create, mock_gcal, mock_n8n, mock_rem):
        """booking response on BackendError must be {doctor, selectedSlot, isConfirmed} — NOT {booking: {...}}."""
        mock_create.side_effect = backend_client.BackendError(
            409, "SLOT_UNAVAILABLE", "That time slot is not available.",
        )

        session = _make_session()
        nlu = _make_nlu()

        msg, action, options, ui_data = handle_new_booking(
            session, "yes, confirm", nlu, "Bearer test-token"
        )

        # Must have booking key
        self.assertIn("booking", ui_data)
        booking = ui_data["booking"]

        # booking must NOT have a nested "booking" key (double-wrap bug)
        self.assertNotIn("booking", booking,
                         "Double-nested booking! ui_data.booking.booking exists (crash cause)")

        # booking must have the fields the frontend ConfirmationCard expects
        self.assertIn("doctor", booking)
        self.assertIn("selectedSlot", booking)
        self.assertIn("isConfirmed", booking)

        # doctor must be a dict with required fields
        self.assertIsInstance(booking["doctor"], dict)
        self.assertIn("name", booking["doctor"])
        self.assertIn("doctor_id", booking["doctor"])

        # isConfirmed must be False (error case)
        self.assertFalse(booking["isConfirmed"])

    @patch("app.chatbot_handlers.reminders")
    @patch("app.chatbot_handlers.n8n_webhook")
    @patch("app.chatbot_handlers.google_calendar")
    @patch("app.chatbot_handlers.backend_client.create_appointment")
    def test_success_response_has_flat_booking_shape(self, mock_create, mock_gcal, mock_n8n, mock_rem):
        """booking response on success must also be flat (not double-nested)."""
        appt_id = str(uuid.uuid4())
        mock_create.return_value = {"appointment_id": appt_id, "patient_id": str(uuid.uuid4())}

        session = _make_session()
        nlu = _make_nlu()

        msg, action, options, ui_data = handle_new_booking(
            session, "yes, confirm", nlu, "Bearer test-token"
        )

        self.assertIn("booking", ui_data)
        booking = ui_data["booking"]
        self.assertNotIn("booking", booking)
        self.assertTrue(booking["isConfirmed"])
        self.assertIsInstance(booking["doctor"], dict)
        self.assertIn("name", booking["doctor"])


if __name__ == "__main__":
    unittest.main()
