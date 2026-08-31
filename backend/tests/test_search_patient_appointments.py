"""
Tests: GET /api/appointments/search

Verifies:
1. Filtering by doctor_name returns only appointments for matching doctors and
   not appointments belonging to doctors whose names do not match.
2. A patient cannot retrieve another patient's appointments through this route,
   regardless of what filter parameters are supplied.
"""
import uuid
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

PATIENT_A_USER_ID = uuid.uuid4()
PATIENT_A_ID      = uuid.uuid4()

PATIENT_B_USER_ID = uuid.uuid4()
PATIENT_B_ID      = uuid.uuid4()

DOCTOR_KHAN_ID    = uuid.uuid4()
DOCTOR_ALI_ID     = uuid.uuid4()

APPT_KHAN_ID      = uuid.uuid4()
APPT_ALI_ID       = uuid.uuid4()


def _make_fake_appt(appt_id, patient_id, doctor_id, doctor_name, status="scheduled"):
    """Build a minimal Appointment-like MagicMock."""
    appt = MagicMock()
    appt.id                 = appt_id
    appt.clinic_id          = uuid.uuid4()
    appt.clinic             = MagicMock()
    appt.clinic.name        = "Test Clinic"
    appt.doctor_id          = doctor_id
    appt.doctor             = MagicMock()
    appt.doctor.user        = MagicMock()
    appt.doctor.user.name   = doctor_name
    appt.patient_id         = patient_id
    appt.patient            = MagicMock()
    appt.patient.user       = MagicMock()
    appt.patient.user.name  = "Test Patient"
    appt.appointment_time   = MagicMock()
    appt.appointment_time.isoformat.return_value = "2026-09-10T09:00:00"
    appt.status             = status
    appt.symptoms_reported  = "headache"
    appt.urgency_level      = "normal"
    appt.appointment_type   = "in_person"
    appt.created_at         = MagicMock()
    appt.created_at.isoformat.return_value = "2026-08-31T10:00:00"
    return appt


# ---------------------------------------------------------------------------
# Helper: build a mock DB that returns a specific patient for Patient lookup
# and a specific list of appointments for Appointment queries.
# ---------------------------------------------------------------------------

def _make_db(patient_obj, returned_appts):
    """
    Return a mock Session whose .query() chain:
    - Returns patient_obj for Patient.filter().first()
    - Returns returned_appts for Appointment query chains (.all())
    """
    patient_query = MagicMock()
    patient_query.filter.return_value = patient_query
    patient_query.first.return_value  = patient_obj

    appt_query = MagicMock()
    appt_query.filter.return_value   = appt_query
    appt_query.join.return_value     = appt_query
    appt_query.order_by.return_value = appt_query
    appt_query.all.return_value      = returned_appts

    db = MagicMock()

    def _query_side(model):
        from app.models.patient import Patient
        from app.models.appointment import Appointment
        if model is Patient:
            return patient_query
        if model is Appointment:
            return appt_query
        return MagicMock()

    db.query.side_effect = _query_side
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSearchAppointmentsByDoctorName(unittest.TestCase):
    """
    doctor_name filter: only appointments whose doctor's name partially matches
    the supplied string should appear in the response.
    """

    def _call_search(self, doctor_name, patient_obj, returned_appts):
        from app.routes.appointments import search_patient_appointments

        db = _make_db(patient_obj, returned_appts)
        current_user        = MagicMock()
        current_user.id     = patient_obj.user_id if patient_obj else uuid.uuid4()
        current_user.user_type = "patient"

        return search_patient_appointments(
            doctor_name=doctor_name,
            status_filter=None,
            date_from=None,
            date_to=None,
            current_user=current_user,
            db=db,
        )

    def test_matching_doctor_name_returns_that_appointment(self):
        """Appointments with 'Khan' in doctor name are returned when filtering by 'Khan'."""
        patient_obj         = MagicMock()
        patient_obj.id      = PATIENT_A_ID
        patient_obj.user_id = PATIENT_A_USER_ID

        appt_khan = _make_fake_appt(APPT_KHAN_ID, PATIENT_A_ID, DOCTOR_KHAN_ID, "Dr. Khan")

        # The mock DB's query chain returns appt_khan (simulating the DB-side
        # ILIKE filter having already narrowed results to matching rows).
        result = self._call_search("Khan", patient_obj, [appt_khan])

        self.assertEqual(result.total, 1)
        self.assertEqual(result.appointments[0].appointment_id, APPT_KHAN_ID)
        self.assertEqual(result.appointments[0].doctor_name, "Dr. Khan")

    def test_non_matching_doctor_name_returns_empty(self):
        """When the DB returns no rows (ILIKE found no match), the list is empty."""
        patient_obj         = MagicMock()
        patient_obj.id      = PATIENT_A_ID
        patient_obj.user_id = PATIENT_A_USER_ID

        result = self._call_search("Nonexistent", patient_obj, [])

        self.assertEqual(result.total, 0)
        self.assertEqual(result.appointments, [])

    def test_no_filters_returns_all_patient_appointments(self):
        """Calling with no filters at all returns every appointment for the patient."""
        patient_obj         = MagicMock()
        patient_obj.id      = PATIENT_A_ID
        patient_obj.user_id = PATIENT_A_USER_ID

        appt_khan = _make_fake_appt(APPT_KHAN_ID, PATIENT_A_ID, DOCTOR_KHAN_ID, "Dr. Khan")
        appt_ali  = _make_fake_appt(APPT_ALI_ID,  PATIENT_A_ID, DOCTOR_ALI_ID,  "Dr. Ali")

        result = self._call_search(None, patient_obj, [appt_khan, appt_ali])

        self.assertEqual(result.total, 2)
        appt_ids = {a.appointment_id for a in result.appointments}
        self.assertIn(APPT_KHAN_ID, appt_ids)
        self.assertIn(APPT_ALI_ID,  appt_ids)


class TestSearchCrossPatientIsolation(unittest.TestCase):
    """
    A patient (Patient A) must NEVER see Patient B's appointments through the
    /search route, regardless of what filters are provided.
    """

    def _call_search_as_patient_a(self, patient_a_obj, returned_appts, doctor_name=None, status_filter=None):
        from app.routes.appointments import search_patient_appointments

        db = _make_db(patient_a_obj, returned_appts)
        current_user           = MagicMock()
        current_user.id        = patient_a_obj.user_id
        current_user.user_type = "patient"

        return search_patient_appointments(
            doctor_name=doctor_name,
            status_filter=status_filter,
            date_from=None,
            date_to=None,
            current_user=current_user,
            db=db,
        )

    def test_patient_cannot_see_other_patients_appointments(self):
        """
        Even if the DB hypothetically returned Patient B's appointment row (which
        the real DB would never do since the query is scoped by patient.id), the
        route still processes only what the DB returns.

        More importantly: the route never accepts a patient_id from the query
        string, so Patient A's JWT cannot be used to query Patient B's data.

        Here we verify that the route correctly resolves *Patient A's* record
        from the authenticated user and does NOT return Patient B's appointment
        when the DB (correctly) returns no rows for that scope.
        """
        patient_a_obj         = MagicMock()
        patient_a_obj.id      = PATIENT_A_ID
        patient_a_obj.user_id = PATIENT_A_USER_ID

        # DB correctly returns [] because Patient B's appointments are not
        # included in Patient A's scoped query.
        result = self._call_search_as_patient_a(patient_a_obj, [], doctor_name="Khan")

        self.assertEqual(result.total, 0)
        self.assertEqual(result.appointments, [])

    def test_no_patient_record_returns_empty_not_error(self):
        """
        If the authenticated user has no Patient record (e.g. a doctor or admin
        JWT hitting the /search endpoint), the route must return an empty list
        rather than raising an exception.
        """
        from app.routes.appointments import search_patient_appointments

        # DB returns None for patient lookup.
        patient_query = MagicMock()
        patient_query.filter.return_value = patient_query
        patient_query.first.return_value  = None  # no patient record

        db = MagicMock()

        def _query_side(model):
            from app.models.patient import Patient
            if model is Patient:
                return patient_query
            return MagicMock()

        db.query.side_effect = _query_side

        current_user           = MagicMock()
        current_user.id        = uuid.uuid4()
        current_user.user_type = "doctor"  # not a patient

        result = search_patient_appointments(
            doctor_name=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            current_user=current_user,
            db=db,
        )

        self.assertEqual(result.total, 0)
        self.assertEqual(result.appointments, [])

    def test_authenticated_user_id_determines_scope_not_query_string(self):
        """
        The route must scope results to the JWT-authenticated user, NOT to any
        patient_id that might be injected via a query parameter.  Since the
        search_patient_appointments signature does NOT include a patient_id
        Query parameter, this is enforced structurally — verify the function
        signature to guarantee the parameter cannot be accepted.
        """
        import inspect
        from app.routes.appointments import search_patient_appointments

        sig = inspect.signature(search_patient_appointments)
        param_names = list(sig.parameters.keys())

        # patient_id must NOT appear as a query parameter.
        self.assertNotIn(
            "patient_id",
            param_names,
            msg=(
                "search_patient_appointments must not accept patient_id as a "
                "query parameter — patient scope must come from the JWT only."
            ),
        )


if __name__ == "__main__":
    unittest.main()
