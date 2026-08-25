from uuid import UUID
from typing import List, Optional, Dict
from pydantic import BaseModel


class SymptomStat(BaseModel):
    symptom: str
    count: int


class DashboardResponse(BaseModel):
    date: str
    clinic_id: Optional[UUID] = None
    clinic_name: str
    total_appointments_today: int
    completed_today: int
    cancelled_today: int
    no_show_today: int
    upcoming_today: int
    total_patients: int
    average_wait_time_minutes: int
    doctor_utilization_percent: float
    no_show_rate_percent: float
    average_rating: float
    high_urgency_appointments: int
    critical_urgency_appointments: int
    common_symptoms: List[SymptomStat]


class DailySummaryResponse(BaseModel):
    date: str
    clinic_id: Optional[UUID] = None
    doctor_id: Optional[UUID] = None
    total_appointments: int
    appointments_by_status: Dict[str, int]
    appointments_by_urgency: Dict[str, int]
    average_wait_time_minutes: int
    earliest_appointment: Optional[str] = None
    latest_appointment: Optional[str] = None
    total_patients_seen: int
    new_patients: int
    repeat_patients: int
    summary: str
