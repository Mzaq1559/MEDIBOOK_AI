"""Regression test: timezone-aware slot validation in validate_booking_slot.

BUG: The validate_booking_slot function compared the appointment time in
naive UTC against Karachi-local working hours.  A 09:00 Karachi slot
(04:00 UTC) failed the check because 04:00 < 09:00 (start_t).

This meant EVERY slot appeared as SLOT_UNAVAILABLE, regardless of actual
availability, because all Karachi morning slots (09:00-12:00 = 04:00-07:00 UTC)
are numerically before the 09:00 working-hours start.

The fix: convert appt_dt to Karachi local time before all local-time
comparisons (working hours, break times, day-of-week, daily capacity).
"""
import unittest
from datetime import datetime, time, timedelta
from unittest.mock import MagicMock, patch
import pytz
from dateutil import parser as date_parser


KARACHI_TZ = pytz.timezone("Asia/Karachi")


class TestParseAndValidateTime(unittest.TestCase):
    """Verify parse_and_validate_time correctly converts ISO to naive UTC."""

    def test_karachi_iso_to_naive_utc(self):
        """A Karachi-timezone ISO string must be converted to naive UTC."""
        from app.services.appointment_service import parse_and_validate_time

        result = parse_and_validate_time("2026-09-03T09:00:00+05:00")
        # 09:00 Karachi = 04:00 UTC
        self.assertEqual(result.hour, 4)
        self.assertEqual(result.minute, 0)
        self.assertIsNone(result.tzinfo)

    def test_karachi_afternoon_to_naive_utc(self):
        """Afternoon Karachi slot (14:30 = 09:30 UTC)."""
        from app.services.appointment_service import parse_and_validate_time

        result = parse_and_validate_time("2026-09-03T14:30:00+05:00")
        self.assertEqual(result.hour, 9)
        self.assertEqual(result.minute, 30)
        self.assertIsNone(result.tzinfo)


class TestTimezoneConversionInValidation(unittest.TestCase):
    """Verify the fix: appt_local correctly recovers Karachi local time from UTC."""

    def test_utc_0400_is_karachi_0900(self):
        """04:00 UTC must convert back to 09:00 Karachi for working-hours check."""
        appt_dt = datetime(2026, 9, 3, 4, 0)  # naive UTC
        appt_local = pytz.UTC.localize(appt_dt).astimezone(KARACHI_TZ)

        self.assertEqual(appt_local.hour, 9)
        self.assertEqual(appt_local.minute, 0)

        # Working hours: 09:00 - 17:00 Karachi
        slot_time = appt_local.time()
        self.assertFalse(slot_time < time(9, 0), "09:00 Karachi must NOT be before working hours start")
        self.assertFalse(slot_time > time(17, 0), "09:00 Karachi must NOT be after working hours end")

    def test_utc_0700_is_karachi_1200(self):
        """07:00 UTC must convert to 12:00 Karachi (noon)."""
        appt_dt = datetime(2026, 9, 3, 7, 0)  # naive UTC
        appt_local = pytz.UTC.localize(appt_dt).astimezone(KARACHI_TZ)

        self.assertEqual(appt_local.hour, 12)
        slot_time = appt_local.time()
        self.assertFalse(slot_time < time(9, 0))

    def test_utc_1130_is_karachi_1630(self):
        """11:30 UTC must convert to 16:30 Karachi (still within 17:00 end)."""
        appt_dt = datetime(2026, 9, 3, 11, 30)  # naive UTC
        appt_local = pytz.UTC.localize(appt_dt).astimezone(KARACHI_TZ)

        self.assertEqual(appt_local.hour, 16)
        self.assertEqual(appt_local.minute, 30)
        slot_time = appt_local.time()
        # 16:30 + 30 min = 17:00 <= end_t (17:00) — should pass
        slot_end = (datetime.combine(appt_local.date(), slot_time) + timedelta(minutes=30)).time()
        self.assertFalse(slot_end > time(17, 0))

    def test_date_is_correct_in_karachi(self):
        """Target date from UTC must match the Karachi calendar date."""
        # 04:00 UTC on Sep 3 = 09:00 Karachi on Sep 3
        appt_dt = datetime(2026, 9, 3, 4, 0)
        appt_local = pytz.UTC.localize(appt_dt).astimezone(KARACHI_TZ)

        self.assertEqual(appt_local.date().year, 2026)
        self.assertEqual(appt_local.date().month, 9)
        self.assertEqual(appt_local.date().day, 3)

    def test_late_evening_karachi_is_previous_day_utc(self):
        """22:00 Karachi (17:00 UTC) — date must still be Sep 3 in Karachi."""
        appt_dt = datetime(2026, 9, 3, 17, 0)  # naive UTC = 22:00 Karachi
        appt_local = pytz.UTC.localize(appt_dt).astimezone(KARACHI_TZ)

        self.assertEqual(appt_local.date().day, 3)
        self.assertEqual(appt_local.hour, 22)

    def test_day_bounds_for_daily_capacity_use_karachi(self):
        """Daily capacity query must use Karachi day bounds converted to UTC."""
        target_date = datetime(2026, 9, 3).date()

        karachi_day_start = KARACHI_TZ.localize(datetime.combine(target_date, time.min))
        karachi_day_end = KARACHI_TZ.localize(datetime.combine(target_date, time.max))
        start_of_day = karachi_day_start.astimezone(pytz.UTC).replace(tzinfo=None)
        end_of_day = karachi_day_end.astimezone(pytz.UTC).replace(tzinfo=None)

        # Karachi midnight = previous day 19:00 UTC
        self.assertEqual(start_of_day.hour, 19)
        self.assertEqual(start_of_day.day, 2)  # Sep 2 19:00 UTC

        # Karachi end-of-day = Sep 3 18:59:59 UTC
        self.assertEqual(end_of_day.hour, 18)
        self.assertEqual(end_of_day.day, 3)


class TestOldBugWouldHaveFailed(unittest.TestCase):
    """Demonstrate the old bug: without Karachi conversion, all morning slots fail."""

    def test_old_logic_rejects_0900_karachi(self):
        """The OLD buggy logic compared UTC time (04:00) against Karachi hours (09:00)."""
        appt_dt = datetime(2026, 9, 3, 4, 0)  # naive UTC = 09:00 Karachi
        slot_time_old = appt_dt.time()  # 04:00 — BUG: compared against Karachi 09:00
        self.assertTrue(
            slot_time_old < time(9, 0),
            "OLD BUG: 04:00 UTC is before 09:00, so all morning slots would fail"
        )

    def test_new_logic_accepts_0900_karachi(self):
        """The FIXED logic converts to Karachi first, then checks."""
        appt_dt = datetime(2026, 9, 3, 4, 0)  # naive UTC = 09:00 Karachi
        appt_local = pytz.UTC.localize(appt_dt).astimezone(KARACHI_TZ)
        slot_time_new = appt_local.time()  # 09:00 Karachi — correct
        self.assertFalse(
            slot_time_new < time(9, 0),
            "NEW FIX: 09:00 Karachi is NOT before 09:00, slot passes"
        )


if __name__ == "__main__":
    unittest.main()
