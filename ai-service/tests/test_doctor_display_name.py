"""
Regression tests for the _doctor_display_name() helper in reminders.py.

The "Dr. Dr." bug: multiple code sites independently prepended "Dr." to
doctor names that already included the prefix, producing "Dr. Dr. Fatima".
The shared _doctor_display_name() helper strips any existing "Dr." prefix
before re-adding it, guaranteeing exactly one.
"""

from integrations.reminders import _doctor_display_name


class TestDoctorDisplayNameReminders:
    """_doctor_display_name (reminders) must always produce exactly one 'Dr.' prefix."""

    def test_plain_name_gets_prefix(self):
        assert _doctor_display_name("Fatima") == "Dr. Fatima"

    def test_name_already_has_prefix_no_duplication(self):
        assert _doctor_display_name("Dr. Fatima") == "Dr. Fatima"

    def test_lowercase_dr_prefix_stripped(self):
        assert _doctor_display_name("dr. Fatima") == "Dr. Fatima"

    def test_dr_prefix_with_extra_space(self):
        assert _doctor_display_name("Dr.  Fatima") == "Dr. Fatima"

    def test_none_input_returns_default(self):
        assert _doctor_display_name(None) == "Dr. Doctor"

    def test_empty_string_returns_default(self):
        assert _doctor_display_name("") == "Dr. Doctor"

    def test_whitespace_only_returns_default(self):
        assert _doctor_display_name("   ") == "Dr. Doctor"

    def test_dr_only_returns_default(self):
        assert _doctor_display_name("Dr.") == "Dr. Doctor"

    def test_name_with_leading_trailing_spaces(self):
        assert _doctor_display_name("  Fatima  ") == "Dr. Fatima"

    def test_multiword_name_preserved(self):
        assert _doctor_display_name("Ahmed Khan") == "Dr. Ahmed Khan"

    def test_no_double_prefix_in_reminder_message(self):
        """The reminder format_reminder_message must not produce 'Dr. Dr.'."""
        stored_name = "Dr. Fatima"
        display = _doctor_display_name(stored_name)
        assert display == "Dr. Fatima"
        assert "Dr. Dr." not in f"{display}"

    def test_no_double_prefix_for_plain_stored_name(self):
        stored_name = "Ahmed Khan"
        display = _doctor_display_name(stored_name)
        assert display == "Dr. Ahmed Khan"
        assert "Dr. Dr." not in f"{display}"
