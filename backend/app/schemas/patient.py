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
    date_of_birth: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_type: Optional[str] = None
    allergies: List[str] = Field(default_factory=list)
    medical_conditions: List[str] = Field(default_factory=list)
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    preferred_notification: str
    profile_completed: bool = False
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
    date_of_birth: Optional[str] = None  # ISO date string YYYY-MM-DD
    gender: Optional[str] = None  # 'M', 'F', 'Other'
    blood_type: Optional[str] = None
    allergies: Optional[List[str]] = None
    medical_conditions: Optional[List[str]] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    preferred_notification: Optional[str] = None

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("M", "F", "Other", ""):
            raise ValueError("gender must be 'M', 'F', or 'Other'")
        return v if v != "" else None

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v != "":
            from datetime import date as _date
            try:
                parsed = _date.fromisoformat(v)
                # Sanity check: not in the future, not absurdly old
                today = _date.today()
                if parsed > today:
                    raise ValueError("date_of_birth cannot be in the future")
                if (today.year - parsed.year) > 150:
                    raise ValueError("date_of_birth is not plausible")
            except ValueError as e:
                if "date_of_birth" in str(e):
                    raise
                raise ValueError("date_of_birth must be ISO format YYYY-MM-DD")
        return v if v != "" else None


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
