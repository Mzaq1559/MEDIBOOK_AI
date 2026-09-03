"""
Regression test: verify the appointment API schemas declare patient_history.
The root cause of Bug C was that the list endpoint didn't populate
patient_history even though the schema and model both had the field.
"""

import unittest


class TestAppointmentSchemaIncludesHistory(unittest.TestCase):
    """Verify the Pydantic schemas declare patient_history."""

    def test_list_item_schema_has_patient_history(self):
        from app.schemas.appointment import AppointmentListItem
        fields = AppointmentListItem.model_fields
        self.assertIn("patient_history", fields)

    def test_detail_response_schema_has_patient_history(self):
        from app.schemas.appointment import AppointmentDetailResponse
        fields = AppointmentDetailResponse.model_fields
        self.assertIn("patient_history", fields)

    def test_create_schema_has_patient_history(self):
        from app.schemas.appointment import AppointmentCreate
        fields = AppointmentCreate.model_fields
        self.assertIn("patient_history", fields)

    def test_list_item_patient_history_defaults_none(self):
        """When patient_history is not supplied, it should be None, not missing."""
        import uuid
        from app.schemas.appointment import AppointmentListItem
        item = AppointmentListItem(
            appointment_id=uuid.uuid4(),
            clinic_id=uuid.uuid4(),
            clinic_name="Clinic",
            doctor_id=uuid.uuid4(),
            doctor_name="Dr. Test",
            patient_id=uuid.uuid4(),
            patient_name="Test Patient",
            appointment_time="2026-09-05T09:00:00Z",
            status="scheduled",
            symptoms_reported="headache",
            urgency_level="normal",
            appointment_type="in_person",
            created_at="2026-09-01T00:00:00Z",
        )
        self.assertIsNone(item.patient_history)


if __name__ == "__main__":
    unittest.main()
