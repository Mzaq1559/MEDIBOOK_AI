"""
Bug 2 regression test: validate_booking_slot must use Karachi time
(not naive UTC) for working days, working hours, and break checks.

The DB stores naive UTC datetimes, but the clinic's local time (Karachi,
UTC+5) determines which day and what hours are valid.  A slot at 10:00 AM
Karachi on a Friday is stored as 05:00 UTC Friday — but a slot at 02:00 AM
Karachi Friday is stored as 21:00 UTC *Thursday*, and the old code extracted
target_date from the UTC value, checking Thursday's working-day status
instead of Friday's.
"""

import uuid
from datetime import datetime, time, timedelta
from unittest.mock import MagicMock

import pytest
import pytz

from app.services.appointment_service import validate_booking_slot

KARACHI_TZ = pytz.timezone("Asia/Karachi")


def _make_clinic(working_days="Mon,Tue,Wed,Thu,Fri,Sat"):
    clinic = MagicMock()
    clinic.id = uuid.uuid4()
    clinic.working_days = working_days
    clinic.working_hours_start = time(9, 0)
    clinic.working_hours_end = time(17, 0)
    clinic.timezone = "Asia/Karachi"
    return clinic


def _make_doctor():
    doctor = MagicMock()
    doctor.id = uuid.uuid4()
    doctor.is_available = True
    doctor.appointment_duration_minutes = 30
    doctor.max_patients_per_day = 20
    return doctor


def _make_db():
    db = MagicMock()
    # All queries return empty (no holidays, no schedules, no existing appointments)
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.all.return_value = []
    return db


class TestBug2_TimezoneSlotValidation:

    def test_friday_10am_karachi_validates_as_friday(self):
        """10:00 AM Karachi on Friday Sep 4 (= 05:00 UTC Sep 4) must
        validate against Friday, not Thursday."""
        clinic = _make_clinic("Fri")  # Only Friday is a working day
        doctor = _make_doctor()
        db = _make_db()
        patient_id = uuid.uuid4()

        karachi_slot = KARACHI_TZ.localize(datetime(2026, 9, 4, 10, 0))  # Fri 10 AM PKT
        utc_slot = karachi_slot.astimezone(pytz.UTC).replace(tzinfo=None)  # Fri 05:00 UTC

        # Should NOT raise — Friday is a working day, 10 AM is within 9-17
        # (but the slot is in the past relative to 2026-09-03, so mock the
        # future check by patching datetime.utcnow)
        from unittest.mock import patch
        past_now = datetime(2026, 9, 1, 0, 0)  # well before the slot
        with patch("app.services.appointment_service.datetime") as mock_dt:
            mock_dt.utcnow.return_value = past_now
            mock_dt.combine = datetime.combine
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            validate_booking_slot(
                db=db, doctor=doctor, clinic=clinic,
                patient_id=patient_id, appt_dt=utc_slot, duration_mins=30,
            )

    def test_friday_2am_karachi_still_validates_as_friday(self):
        """02:00 AM Karachi on Friday Sep 4 (= 21:00 UTC Thu Sep 3) must
        validate against Friday (Karachi date), NOT Thursday (UTC date)."""
        clinic = _make_clinic("Fri")  # Only Friday is a working day
        doctor = _make_doctor()
        db = _make_db()
        patient_id = uuid.uuid4()

        karachi_slot = KARACHI_TZ.localize(datetime(2026, 9, 4, 2, 0))  # Fri 02 AM PKT
        utc_slot = karachi_slot.astimezone(pytz.UTC).replace(tzinfo=None)  # Thu 21:00 UTC

        # Old bug: target_date = utc_slot.date() → Sep 3 (Thursday)
        # Clinic closed on Thursday → "Clinic is closed on Thu" error
        # Fixed: target_date = karachi date → Sep 4 (Friday)
        # 2 AM is outside 9-17 working hours → "outside working hours" error
        # That's expected — the point is we get the CORRECT error, not wrong day
        from unittest.mock import patch
        past_now = datetime(2026, 9, 1, 0, 0)
        with patch("app.services.appointment_service.datetime") as mock_dt:
            mock_dt.utcnow.return_value = past_now
            mock_dt.combine = datetime.combine
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            try:
                validate_booking_slot(
                    db=db, doctor=doctor, clinic=clinic,
                    patient_id=patient_id, appt_dt=utc_slot, duration_mins=30,
                )
                pytest.fail("Expected HTTPException for outside working hours")
            except Exception as e:
                error_msg = str(e)
                # Must NOT say "closed on Thu" — must say "outside working hours"
                assert "closed on Thu" not in error_msg, \
                    f"Bug still present: validated against UTC date (Thursday). Error: {error_msg}"

    def test_sunday_only_clinic_rejects_friday_slot(self):
        """A clinic open only on Sunday should reject a Friday slot."""
        clinic = _make_clinic("Sun")
        doctor = _make_doctor()
        db = _make_db()
        patient_id = uuid.uuid4()

        karachi_slot = KARACHI_TZ.localize(datetime(2026, 9, 4, 10, 0))  # Friday
        utc_slot = karachi_slot.astimezone(pytz.UTC).replace(tzinfo=None)

        from unittest.mock import patch
        past_now = datetime(2026, 9, 1, 0, 0)
        with patch("app.services.appointment_service.datetime") as mock_dt:
            mock_dt.utcnow.return_value = past_now
            mock_dt.combine = datetime.combine
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            with pytest.raises(Exception) as exc_info:
                validate_booking_slot(
                    db=db, doctor=doctor, clinic=clinic,
                    patient_id=patient_id, appt_dt=utc_slot, duration_mins=30,
                )
            assert "closed" in str(exc_info.value).lower() or "SLOT_UNAVAILABLE" in str(exc_info.value)
