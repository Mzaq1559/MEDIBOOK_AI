from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID


class PrescriptionBase(BaseModel):
    medication: str
    dosage: str
    duration: str
    notes: Optional[str] = None


class PrescriptionCreate(PrescriptionBase):
    patient_id: UUID
    doctor_id: UUID
    appointment_id: UUID


class PrescriptionUpdate(BaseModel):
    medication: Optional[str] = None
    dosage: Optional[str] = None
    duration: Optional[str] = None
    notes: Optional[str] = None


class PrescriptionResponse(PrescriptionBase):
    id: UUID
    patient_id: UUID
    doctor_id: UUID
    appointment_id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
