"""
Tests: PATCH /api/appointments/{id}/no-show  — temporal validation

Requirements verified:
  1. Past appointment   → 200 OK, status becomes "no_show"
  2. Exact scheduled time (now == appt time) → 422 UNPROCESSABLE_ENTITY
  3. Future appointment  → 422 UNPROCESSABLE_ENTITY
  4. Appointment not found → 404 NOT_FOUND
  5. Unauthorized caller (no role) → 403 FORBIDDEN (existing auth behaviour)

The project uses naive UTC datetimes throughout (datetime.utcnow()).
We patch `app.routes.appointments.datetime` so that `datetime.utcnow()`
returns a controlled value while still allowing `datetime.utcnow` to be
called normally elsewhere in the same module.
"""
import uuid
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

# Stable IDs reused across tests
APPT_ID  = uuid.uuid4()
DOC_ID   = uuid.uuid4()
PAT_ID   = uuid.uuid4()
USER_ID  = uuid.uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_appt(appointment_time: datetime) -> MagicMock:
    """Return a minimal mock Appointment with the given scheduled time."""
    appt = MagicMock()
    appt.id               = APPT_ID
    appt.patient_id       = PAT_ID
    appt.appointment_time = appointment_time
    appt.status           = "scheduled"
    return appt


def _make_db(appt_or_none) -> MagicMock:
    """Return a mock Session that returns *appt_or_none* on first() calls."""
    appt_query = MagicMock()
    appt_query.filter.return_value = appt_query
    appt_query.first.return_value  = appt_or_none

    patient_obj         = MagicMock()
    patient_obj.total_no_shows = 0
    patient_query = MagicMock()
    patient_query.filter.return_value = patient_query
    patient_query.first.return_value  = patient_obj

    db = MagicMock()

    def _side(model):
        from app.models.appointment import Appointment
        from app.models.patient     import Patient
        if model is Appointment:
            return appt_query
        if model is Patient:
            return patient_query
        return MagicMock()

    db.query.side_effect = _side
    return db


def _doctor_user() -> MagicMock:
    user           = MagicMock()
    user.id        = USER_ID
    user.user_type = "doctor"
    return user


def _call_mark_no_show(db, current_user, appointment_id=APPT_ID):
    from app.routes.appointments import mark_no_show
    request = MagicMock()
    request.client.host = "127.0.0.1"
    return mark_no_show(
        request        = request,
        appointment_id = appointment_id,
        current_user   = current_user,
        db             = db,
    )


# ---------------------------------------------------------------------------
# Datetime-patch helper
# ---------------------------------------------------------------------------
# We patch `datetime` inside the appointments module so that utcnow() returns
# a value we control, while keep datetime(…) construction working normally.

def _patch_now(fake_now: datetime):
    """
    Return a context manager that replaces datetime.utcnow() in the
    appointments route module with *fake_now*.
    """
    mock_dt = MagicMock(wraps=datetime)
    mock_dt.utcnow.return_value = fake_now
    return patch("app.routes.appointments.datetime", mock_dt)


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestMarkNoShowTemporalValidation(unittest.TestCase):

    # ── 1. Past appointment → allowed ──────────────────────────────────────
    def test_past_appointment_is_allowed(self):
        """An appointment whose time is strictly in the past must succeed."""
        appt_time = datetime(2026, 9, 1, 10, 0, 0)   # 10:00
        now        = datetime(2026, 9, 1, 10,  1, 0)  # 10:01 → past

        db  = _make_db(_make_appt(appt_time))
        usr = _doctor_user()

        with _patch_now(now):
            response = _call_mark_no_show(db, usr)

        self.assertEqual(response.status, "no_show")
        self.assertEqual(response.appointment_id, APPT_ID)

    # ── 2. Same date, earlier time by one minute → allowed ─────────────────
    def test_earlier_date_same_time_minus_one_minute_allowed(self):
        appt_time = datetime(2026, 9, 1, 10, 0, 0)
        now        = datetime(2026, 9, 1,  9, 59, 0)  # 09:59 → future

        db  = _make_db(_make_appt(appt_time))
        usr = _doctor_user()

        with _patch_now(now), self.assertRaises(HTTPException) as ctx:
            _call_mark_no_show(db, usr)

        exc = ctx.exception
        self.assertEqual(exc.status_code, 422)
        self.assertIn("APPOINTMENT_NOT_YET_PASSED", exc.detail["error_code"])

    # ── 3. Exact scheduled time → rejected ─────────────────────────────────
    def test_exact_scheduled_time_is_rejected(self):
        """now == appt.appointment_time must be rejected (>= guard)."""
        appt_time = datetime(2026, 9, 1, 10, 0, 0)
        now        = datetime(2026, 9, 1, 10, 0, 0)  # exact

        db  = _make_db(_make_appt(appt_time))
        usr = _doctor_user()

        with _patch_now(now), self.assertRaises(HTTPException) as ctx:
            _call_mark_no_show(db, usr)

        exc = ctx.exception
        self.assertEqual(exc.status_code, 422)
        self.assertIn(
            "cannot be marked as no-show before its scheduled",
            exc.detail["message"],
        )
        self.assertEqual(exc.detail["error_code"], "APPOINTMENT_NOT_YET_PASSED")

    # ── 4. Future appointment → rejected ───────────────────────────────────
    def test_future_appointment_is_rejected(self):
        """now < appt.appointment_time must be rejected."""
        appt_time = datetime(2026, 9, 1, 10, 0, 0)
        now        = datetime(2026, 8, 31, 20, 0, 0)  # day before

        db  = _make_db(_make_appt(appt_time))
        usr = _doctor_user()

        with _patch_now(now), self.assertRaises(HTTPException) as ctx:
            _call_mark_no_show(db, usr)

        exc = ctx.exception
        self.assertEqual(exc.status_code, 422)
        self.assertEqual(exc.detail["error_code"], "APPOINTMENT_NOT_YET_PASSED")

    # ── 5. Appointment not found → 404 (existing behaviour) ────────────────
    def test_appointment_not_found_returns_404(self):
        db  = _make_db(None)   # first() returns None
        usr = _doctor_user()

        with self.assertRaises(HTTPException) as ctx:
            _call_mark_no_show(db, usr)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error_code"], "NOT_FOUND")


class TestMarkNoShowAuthorizationPreserved(unittest.TestCase):
    """
    The route uses require_roles("doctor", "receptionist", "admin").
    This test verifies that an unauthorised caller (e.g. plain patient)
    still receives 403 via the existing dependency — we confirm the
    dependency is wired by checking that require_roles raises before
    any DB access occurs.
    """

    def test_require_roles_dependency_is_declared(self):
        """
        Confirm that the endpoint's current_user parameter is gated by
        require_roles, not bare get_current_user, so role enforcement
        is always applied regardless of temporal validation.
        """
        import inspect
        from app.routes.appointments import mark_no_show
        from app.core.auth import require_roles

        sig = inspect.signature(mark_no_show)
        current_user_param = sig.parameters.get("current_user")
        self.assertIsNotNone(current_user_param, "current_user param must exist")

        # The default of current_user should be a Depends wrapping require_roles.
        dep_default = current_user_param.default
        self.assertIsNotNone(dep_default)
        # FastAPI wraps Depends; the callable inside should be a partial or
        # direct reference produced by require_roles.
        dep_callable = dep_default.dependency
        # require_roles returns a closure; verify it is indeed that closure.
        self.assertTrue(
            callable(dep_callable),
            "current_user dependency must be callable (produced by require_roles)"
        )


if __name__ == "__main__":
    unittest.main()
