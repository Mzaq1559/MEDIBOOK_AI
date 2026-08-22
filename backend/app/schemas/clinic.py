from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class ClinicCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: str = Field(..., min_length=1, max_length=500)
    city: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=15)
    email: EmailStr
    working_hours_start: str = "09:00"
    working_hours_end: str = "17:00"
    working_days: str = "Mon,Tue,Wed,Thu,Fri"
    timezone: str = "Asia/Karachi"
    is_active: bool = True


class ClinicListItem(BaseModel):
    clinic_id: UUID
    name: str
    address: str
    city: str
    phone: str
    email: str
    working_hours_start: str
    working_hours_end: str
    working_days: str
    timezone: str
    is_active: bool
    total_doctors: int = 0
    total_appointments_this_month: int = 0


class ClinicListResponse(BaseModel):
    total: int
    clinics: List[ClinicListItem]


class ClinicDoctorItem(BaseModel):
    doctor_id: UUID
    name: str
    specialization: str
    rating: float = 0.0


class ClinicHolidayItem(BaseModel):
    holiday_date: str
    holiday_name: str
    reason: Optional[str] = None


class ClinicDetailResponse(BaseModel):
    clinic_id: UUID
    name: str
    address: str
    city: str
    phone: str
    email: str
    working_hours_start: str
    working_hours_end: str
    working_days: str
    timezone: str
    is_active: bool
    doctors: List[ClinicDoctorItem] = Field(default_factory=list)
    holidays: List[ClinicHolidayItem] = Field(default_factory=list)
