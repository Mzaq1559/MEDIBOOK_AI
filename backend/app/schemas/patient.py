import json
from uuid import UUID
from datetime import datetime, date
from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class PatientResponse(BaseModel):
    patient_id: UUID
    user_id: UUID
    name: str
    email: str
    phone: Optional[str] = None
    date_of_birth: str
    age: int
    gender: str
    blood_type: Optional[str] = None
    allergies: List[str] = Field(default_factory=list)
    medical_conditions: List[str] = Field(default_factory=list)
    emergency_contact_name: str
    emergency_contact_phone: str
    emergency_contact_relation: Optional[str] = None
    preferred_notification: str
    total_appointments: int = 0
    total_no_shows: int = 0
    created_at: str

    @field_validator("allergies", "medical_conditions", mode="before")
    @classmethod
    def parse_lists(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else [v]
            except Exception:
                return [v]
        return v or []


class PatientUpdate(BaseModel):
    allergies: Optional[List[str]] = None
    medical_conditions: Optional[List[str]] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    preferred_notification: Optional[str] = None


class PatientUpdateResponse(BaseModel):
    patient_id: UUID
    allergies: Optional[List[str]] = None
    medical_conditions: Optional[List[str]] = None
    preferred_notification: Optional[str] = None
    message: str = "Patient details updated successfully"


class PatientAppointmentItem(BaseModel):
    appointment_id: UUID
    doctor_id: Optional[UUID] = None
    doctor_name: str
    doctor_specialization: Optional[str] = None
    clinic_id: Optional[UUID] = None
    clinic_name: str
    clinic_address: Optional[str] = None
    appointment_time: str
    end_time: Optional[str] = None
    status: str
    symptoms: str
    urgency: str
    urgency_reason: Optional[str] = None
    doctor_notes: Optional[str] = None
    feedback_score: Optional[int] = None
    feedback_text: Optional[str] = None
    feedback_submitted: bool = False


class PatientAppointmentsResponse(BaseModel):
    total: int
    appointments: List[PatientAppointmentItem]
