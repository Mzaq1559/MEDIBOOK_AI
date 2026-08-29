"""
Tests: chatbot patient_id resolution via the backend_client layer

Verifies that fetch_patient_appointments works correctly when given either
users.id or patients.id (both should succeed now that the backend resolves them),
and that the cancel/reschedule handlers propagate the patient_id correctly.
"""
import uuid
import unittest
from unittest.mock import patch, MagicMock

USER_ID    = str(uuid.uuid4())  # users.id (what old frontend/chatbot sent)
PATIENT_ID = str(uuid.uuid4())  # patients.id (real FK in appointments table)
AUTH_TOKEN = "Bearer test-token"
APPT_ID    = str(uuid.uuid4())

FAKE_APPOINTMENT = {
    "appointment_id": APPT_ID,
    "patient_id":     PATIENT_ID,
    "doctor_name":    "Dr. Smith",
    "appointment_time": "2026-09-01T08:00:00Z",
    "status":         "scheduled",
}


# ---------------------------------------------------------------------------
# Tests for fetch_patient_appointments
# ---------------------------------------------------------------------------

class TestFetchPatientAppointments(unittest.TestCase):
    """
    The backend now resolves users.id → patients.id transparently.
    fetch_patient_appointments should return results regardless of which ID is sent.
    """

    def _mock_response(self, appts: list) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"appointments": appts, "total": len(appts)}
        return resp

    def test_fetch_with_patients_id_returns_appointments(self):
        from app.backend_client import fetch_patient_appointments

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = self._mock_response([FAKE_APPOINTMENT])

            result = fetch_patient_appointments(PATIENT_ID, AUTH_TOKEN)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["appointment_id"], APPT_ID)

    def test_fetch_with_users_id_returns_appointments(self):
        """
        When users.id is sent, the backend still resolves and returns results.
        fetch_patient_appointments just passes through the ID; resolution is on the backend.
        """
        from app.backend_client import fetch_patient_appointments

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = self._mock_response([FAKE_APPOINTMENT])

            result = fetch_patient_appointments(USER_ID, AUTH_TOKEN)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["appointment_id"], APPT_ID)

    def test_fetch_returns_empty_on_404(self):
        from app.backend_client import fetch_patient_appointments

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            bad_resp = MagicMock()
            bad_resp.status_code = 404
            mock_client.get.return_value = bad_resp

            result = fetch_patient_appointments(USER_ID, AUTH_TOKEN)

        self.assertEqual(result, [])

    def test_fetch_returns_empty_on_network_error(self):
        import httpx
        from app.backend_client import fetch_patient_appointments

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.side_effect = httpx.HTTPError("timeout")

            result = fetch_patient_appointments(USER_ID, AUTH_TOKEN)

        self.assertEqual(result, [])

    def test_params_include_patient_id_and_status(self):
        """Verify the correct query params are forwarded to the backend."""
        from app.backend_client import fetch_patient_appointments

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = self._mock_response([])

            fetch_patient_appointments(PATIENT_ID, AUTH_TOKEN, status_filter="scheduled")

        call_kwargs = mock_client.get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", {})
        self.assertEqual(params.get("patient_id"), PATIENT_ID)
        self.assertEqual(params.get("status"), "scheduled")


# ---------------------------------------------------------------------------
# Tests for cancel_appointment (integration point)
# ---------------------------------------------------------------------------

class TestCancelAppointment(unittest.TestCase):
    """cancel_appointment should forward the appointment_id and auth token correctly."""

    def test_cancel_calls_delete_with_correct_id(self):
        from app.backend_client import cancel_appointment

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {
            "appointment_id": APPT_ID,
            "status": "cancelled",
            "message": "Appointment cancelled successfully",
        }

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.delete.return_value = success_resp

            result = cancel_appointment(APPT_ID, AUTH_TOKEN)

        self.assertEqual(result["status"], "cancelled")
        call_args = mock_client.delete.call_args
        url = call_args.args[0] if call_args.args else call_args[0][0]
        self.assertIn(APPT_ID, url)

    def test_cancel_raises_on_404(self):
        from app.backend_client import cancel_appointment, BackendError

        not_found = MagicMock()
        not_found.status_code = 404
        not_found.json.return_value = {
            "detail": {"message": "Appointment not found", "error_code": "NOT_FOUND"}
        }

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.delete.return_value = not_found

            with self.assertRaises(BackendError) as ctx:
                cancel_appointment(APPT_ID, AUTH_TOKEN)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.error_code, "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
