from uuid import UUID
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class AppointmentCreate(BaseModel):
    patient_id: UUID
    doctor_id: UUID
    appointment_time: str  # ISO 8601 string
    symptoms_reported: str = Field(..., min_length=3, max_length=1000)
    urgency_level: str = Field(..., description="low, normal, high, critical")
    urgency_reason: Optional[str] = Field(None, max_length=100, description="Machine-readable triage reason code")
    appointment_type: Optional[str] = "in_person"

    @field_validator("urgency_level")
    @classmethod
    def validate_urgency(cls, v: str) -> str:
        valid = {"low", "normal", "high", "critical"}
        if v.lower() not in valid:
            raise ValueError(f"urgency_level must be one of {valid}")
        return v.lower()

    @field_validator("appointment_type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> str:
        if not v:
            return "in_person"
        valid = {"in_person", "video", "phone"}
        if v.lower() not in valid:
            raise ValueError(f"appointment_type must be one of {valid}")
        return v.lower()


class AppointmentCreateResponse(BaseModel):
    appointment_id: UUID
    clinic_id: UUID
    doctor_id: UUID
    doctor_name: str
    patient_id: UUID
    appointment_time: str
    status: str
    symptoms_reported: str
    urgency_level: str
    urgency_reason: Optional[str] = None
    confirmation_message: str
    reminder_time_1: str
    reminder_time_2: str
    created_at: str


class AppointmentListItem(BaseModel):
    appointment_id: UUID
    clinic_id: UUID
    clinic_name: str
    doctor_id: UUID
    doctor_name: str
    doctor_specialization: Optional[str] = None
    patient_id: UUID
    patient_name: str
    appointment_time: str
    status: str
    symptoms_reported: str
    urgency_level: str
    urgency_reason: Optional[str] = None
    appointment_type: str
    doctor_notes: Optional[str] = None
    feedback_score: Optional[int] = None
    feedback_text: Optional[str] = None
    feedback_submitted: Optional[bool] = None
    created_at: str


class AppointmentListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    appointments: List[AppointmentListItem]


class AppointmentDetailResponse(BaseModel):
    appointment_id: UUID
    clinic_id: UUID
    clinic_name: str
    clinic_address: str
    doctor_id: UUID
    doctor_name: str
    doctor_specialization: str
    patient_id: UUID
    patient_name: str
    appointment_time: str
    duration_minutes: int
    status: str
    symptoms_reported: str
    urgency_level: str
    urgency_reason: Optional[str] = None
    appointment_type: str
    notes: Optional[str] = None
    feedback_score: Optional[int] = None
    feedback_text: Optional[str] = None
    google_calendar_event_id: Optional[str] = None
    created_at: str


class AppointmentRescheduleRequest(BaseModel):
    appointment_time: str


class AppointmentRescheduleResponse(BaseModel):
    appointment_id: UUID
    appointment_time: str
    status: str
    message: str = "Appointment rescheduled successfully"
    new_reminder_time_1: str
    new_reminder_time_2: str


class AppointmentCancelResponse(BaseModel):
    appointment_id: UUID
    status: str = "cancelled"
    message: str = "Appointment cancelled successfully"
    cancelled_at: str


class AppointmentCompleteRequest(BaseModel):
    notes: Optional[str] = None
    prescription_id: Optional[UUID] = None


class AppointmentCompleteResponse(BaseModel):
    appointment_id: UUID
    status: str = "completed"
    notes: Optional[str] = None
    completed_at: str
    follow_up_scheduled: Optional[str] = None


class AppointmentNoShowResponse(BaseModel):
    appointment_id: UUID
    status: str = "no_show"
    message: str = "Appointment marked as no-show"


class AppointmentFeedbackRequest(BaseModel):
    feedback_score: int = Field(..., ge=1, le=5)
    feedback_text: Optional[str] = None


class AppointmentFeedbackResponse(BaseModel):
    appointment_id: UUID
    feedback_score: int
    feedback_text: Optional[str] = None
    doctor_rating_updated: float
    message: str = "Thank you for your feedback!"
