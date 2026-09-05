import json
from uuid import UUID
from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class DoctorListItem(BaseModel):
    doctor_id: UUID
    user_id: UUID
    name: str
    email: str
    phone: Optional[str] = None
    specialization: str
    consultation_fee: float
    bio: Optional[str] = None
    is_available: bool
    rating: float = 0.0
    total_appointments: int = 0
    languages_spoken: List[str] = Field(default_factory=list)
    clinic_id: UUID
    clinic_name: str

    @field_validator("languages_spoken", mode="before")
    @classmethod
    def parse_languages(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else [v]
            except Exception:
                return [v]
        return v or []


class DoctorListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    doctors: List[DoctorListItem]


class DoctorDetailResponse(BaseModel):
    doctor_id: UUID
    user_id: UUID
    name: str
    email: str
    phone: Optional[str] = None
    specialization: str
    qualifications: List[str] = Field(default_factory=list)
    consultation_fee: float
    bio: Optional[str] = None
    is_available: bool
    max_patients_per_day: int
    appointment_duration_minutes: int
    rating: float = 0.0
    total_appointments: int = 0
    languages_spoken: List[str] = Field(default_factory=list)
    clinic_id: UUID
    clinic_name: str
    clinic_address: str
    working_hours_start: str
    working_hours_end: str

    @field_validator("qualifications", "languages_spoken", mode="before")
    @classmethod
    def parse_json_lists(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else [v]
            except Exception:
                return [v]
        return v or []


class AvailabilitySlot(BaseModel):
    time: str
    timestamp: str
    available: bool
    status: str  # 'free' or 'booked'


class DayAvailability(BaseModel):
    date: str
    day: str
    working_hours: str
    slots: List[AvailabilitySlot]
    booked_count: int
    available_count: int


class AvailabilityResponse(BaseModel):
    doctor_id: UUID
    doctor_name: str
    specialization: str
    clinic_name: str
    consultation_fee: float
    max_patients_per_day: int
    appointment_duration_minutes: int
    availability: List[DayAvailability]


class DoctorScheduleUpdate(BaseModel):
    date: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_holiday: Optional[bool] = False
    holiday_reason: Optional[str] = None
    break_start: Optional[str] = None
    break_end: Optional[str] = None
    max_patients: Optional[int] = None


class DoctorScheduleResponse(BaseModel):
    doctor_id: UUID
    date: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_holiday: bool = False
    break_start: Optional[str] = None
    break_end: Optional[str] = None
    max_patients: Optional[int] = None
    message: str = "Schedule updated successfully"


class DoctorHolidayRequest(BaseModel):
    date: str
    reason: Optional[str] = None


class DoctorHolidayResponse(BaseModel):
    doctor_id: UUID
    date: str
    is_holiday: bool
    reason: Optional[str] = None
    message: str = "Doctor marked as unavailable for this date"


class DoctorCreate(BaseModel):
    name: str
    email: str
    specialization: str
    clinic_id: UUID
    consultation_fee: float = 2000.0
    max_patients_per_day: int = 20
    bio: Optional[str] = None
    is_available: bool = True


class DoctorUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    specialization: Optional[str] = None
    clinic_id: Optional[UUID] = None
    consultation_fee: Optional[float] = None
    max_patients_per_day: Optional[int] = None
    bio: Optional[str] = None
    is_available: Optional[bool] = None


class DoctorApplicationItem(BaseModel):
    """Represents a pending/approved/rejected doctor self-registration application."""
    id: str  # doctor record id
    user_id: str
    name: str
    email: str
    phone: Optional[str] = None
    specialization: Optional[str] = None
    qualifications: Optional[str] = None
    bio: Optional[str] = None
    is_verified: bool
    created_at: str


class DoctorApplicationListResponse(BaseModel):
    applications: List[DoctorApplicationItem]
    total: int


class DoctorApprovalRequest(BaseModel):
    clinic_id: UUID
    specialization: str
    consultation_fee: Optional[float] = 2000.0
    qualifications: Optional[str] = None


class DoctorRejectionRequest(BaseModel):
    reason: Optional[str] = None

