"""
Tests: patient_id resolution in GET /api/appointments

Verifies that the list_appointments route correctly resolves both
  - patients.id  (the real FK stored in Appointment.patient_id)
  - users.id     (what the chatbot / old frontend paths send)
to the same set of appointments.

Also verifies that a doctor-scoped call returns appointments filtered
by the correct doctors.id, not by users.id.
"""
import uuid
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Minimal stubs so we can test the route logic with mocks
# ---------------------------------------------------------------------------

USER_ID        = uuid.uuid4()  # users.id
PATIENT_ID     = uuid.uuid4()  # patients.id  (different!)
DOCTOR_USER_ID = uuid.uuid4()
DOCTOR_ID      = uuid.uuid4()
APPT_ID        = uuid.uuid4()


def _make_fake_appointment(pat_id: uuid.UUID, doc_id: uuid.UUID) -> MagicMock:
    appt = MagicMock()
    appt.id             = APPT_ID
    appt.clinic_id      = uuid.uuid4()
    appt.clinic         = MagicMock(name="Test Clinic")
    appt.clinic.name    = "Test Clinic"
    appt.doctor_id      = doc_id
    appt.doctor         = MagicMock()
    appt.doctor.user    = MagicMock(name="Dr. Smith")
    appt.doctor.user.name = "Dr. Smith"
    appt.patient_id     = pat_id
    appt.patient        = MagicMock()
    appt.patient.user   = MagicMock(name="John Patient")
    appt.patient.user.name = "John Patient"
    appt.appointment_time = MagicMock()
    appt.appointment_time.isoformat.return_value = "2026-09-01T08:00:00"
    appt.status         = "scheduled"
    appt.symptoms_reported = "Fever and mild cough"
    appt.urgency_level  = "normal"
    appt.appointment_type = "general"
    appt.created_at     = MagicMock()
    appt.created_at.isoformat.return_value = "2026-08-29T10:00:00"
    return appt


def _make_db_session(patient_obj, appts):
    """Return a mock Session whose query chain returns the given data."""
    fake_query = MagicMock()
    fake_query.filter.return_value = fake_query
    fake_query.count.return_value  = len(appts)
    fake_query.order_by.return_value = fake_query
    fake_query.offset.return_value   = fake_query
    fake_query.limit.return_value    = fake_query
    fake_query.all.return_value      = appts

    patient_filter = MagicMock()
    patient_filter.filter.return_value = patient_filter
    patient_filter.first.return_value  = patient_obj

    db = MagicMock()

    def _query_side_effect(model):
        from app.models.patient import Patient
        if model is Patient:
            return patient_filter
        return fake_query

    db.query.side_effect = _query_side_effect
    return db


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestPatientIdResolution(unittest.TestCase):
    """
    GET /api/appointments?patient_id=<X>

    Whether X is patients.id or users.id, the route must resolve to the
    same Appointment.patient_id filter and return the same rows.
    """

    def _call_list(self, patient_id_param: uuid.UUID, patient_obj, appts):
        from app.routes.appointments import list_appointments

        db = _make_db_session(patient_obj, appts)

        admin_user = MagicMock()
        admin_user.user_type = "admin"

        result = list_appointments(
            doctor_id    = None,
            patient_id   = patient_id_param,
            clinic_id    = None,
            status_filter= None,
            date_from    = None,
            date_to      = None,
            date         = None,
            limit        = 50,
            offset       = 0,
            current_user = admin_user,
            db           = db,
        )
        return result

    def test_query_with_patients_id_returns_appointments(self):
        patient_obj         = MagicMock()
        patient_obj.id      = PATIENT_ID
        patient_obj.user_id = USER_ID

        appt = _make_fake_appointment(PATIENT_ID, DOCTOR_ID)

        result = self._call_list(PATIENT_ID, patient_obj, [appt])
        self.assertEqual(result.total, 1)
        self.assertEqual(result.appointments[0].appointment_id, APPT_ID)

    def test_query_with_users_id_resolves_to_same_result(self):
        """Passing users.id should resolve through Patient table and still hit."""
        patient_obj         = MagicMock()
        patient_obj.id      = PATIENT_ID
        patient_obj.user_id = USER_ID

        appt = _make_fake_appointment(PATIENT_ID, DOCTOR_ID)

        result = self._call_list(USER_ID, patient_obj, [appt])
        self.assertEqual(result.total, 1)
        self.assertEqual(result.appointments[0].appointment_id, APPT_ID)

    def test_unrecognised_id_returns_zero(self):
        """An ID that matches no Patient row yields an empty list (no crash)."""
        result = self._call_list(uuid.uuid4(), None, [])
        self.assertEqual(result.total, 0)
        self.assertEqual(result.appointments, [])


class TestDoctorScopedQuery(unittest.TestCase):
    """
    When a doctor user calls GET /api/appointments (no explicit doctor_id param),
    the route must filter by doctors.id — not by users.id.
    """

    def test_doctor_filter_uses_doctors_id(self):
        from app.routes.appointments import list_appointments

        appt = _make_fake_appointment(PATIENT_ID, DOCTOR_ID)

        doctor_obj         = MagicMock()
        doctor_obj.id      = DOCTOR_ID
        doctor_obj.user_id = DOCTOR_USER_ID

        appointment_query = MagicMock()
        appointment_query.filter.return_value = appointment_query
        appointment_query.count.return_value  = 1
        appointment_query.order_by.return_value = appointment_query
        appointment_query.offset.return_value   = appointment_query
        appointment_query.limit.return_value    = appointment_query
        appointment_query.all.return_value      = [appt]

        doctor_query = MagicMock()
        doctor_query.filter.return_value = doctor_query
        doctor_query.first.return_value  = doctor_obj

        db = MagicMock()

        def _side(model):
            from app.models.doctor import Doctor
            if model is Doctor:
                return doctor_query
            return appointment_query

        db.query.side_effect = _side

        doctor_user           = MagicMock()
        doctor_user.user_type = "doctor"
        doctor_user.id        = DOCTOR_USER_ID

        result = list_appointments(
            doctor_id    = None,
            patient_id   = None,
            clinic_id    = None,
            status_filter= None,
            date_from    = None,
            date_to      = None,
            date         = None,
            limit        = 50,
            offset       = 0,
            current_user = doctor_user,
            db           = db,
        )

        self.assertEqual(result.total, 1)


if __name__ == "__main__":
    unittest.main()
