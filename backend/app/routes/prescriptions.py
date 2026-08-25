import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.prescription import Prescription
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.user import User
from app.core.auth import get_current_user
from app.schemas.prescription import (
    PrescriptionResponse,
    PrescriptionCreate,
    PrescriptionUpdate
)

router = APIRouter(prefix="/api/prescriptions", tags=["prescriptions"])

@router.get(
    "/{prescription_id}",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Prescription",
    description="Fetch one prescription by ID."
)
def get_prescription(
    prescription_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id, Prescription.deleted_at.is_(None)).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    # Permission check: patient owns OR doctor created OR admin
    if current_user.user_type == "patient" and prescription.patient.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    elif current_user.user_type == "doctor" and prescription.doctor.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return prescription


@router.get(
    "",
    response_model=List[PrescriptionResponse],
    status_code=status.HTTP_200_OK,
    summary="List Prescriptions",
    description="List prescriptions with filters."
)
def list_prescriptions(
    patient_id: Optional[uuid.UUID] = None,
    doctor_id: Optional[uuid.UUID] = None,
    appointment_id: Optional[uuid.UUID] = None,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Prescription).filter(Prescription.deleted_at.is_(None))

    if patient_id:
        query = query.filter(Prescription.patient_id == patient_id)
    if doctor_id:
        query = query.filter(Prescription.doctor_id == doctor_id)
    if appointment_id:
        query = query.filter(Prescription.appointment_id == appointment_id)

    # Permission scoping
    if current_user.user_type == "patient":
        # Ensure patient can only see their own prescriptions
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient:
            return []
        query = query.filter(Prescription.patient_id == patient.id)
    elif current_user.user_type == "doctor":
        # Ensure doctor can only see prescriptions they created
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if not doctor:
            return []
        query = query.filter(Prescription.doctor_id == doctor.id)

    prescriptions = query.offset(offset).limit(limit).all()
    return prescriptions


@router.post(
    "",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Prescription"
)
def create_prescription(
    payload: PrescriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.user_type not in ["doctor", "admin", "receptionist"]:
        raise HTTPException(status_code=403, detail="Only doctors or admins can create prescriptions")

    # Validation
    if not db.query(Patient).filter(Patient.id == payload.patient_id).first():
        raise HTTPException(status_code=400, detail="Invalid patient_id")
    if not db.query(Doctor).filter(Doctor.id == payload.doctor_id).first():
        raise HTTPException(status_code=400, detail="Invalid doctor_id")
    if not db.query(Appointment).filter(Appointment.id == payload.appointment_id).first():
        raise HTTPException(status_code=400, detail="Invalid appointment_id")

    # If user is doctor, ensure they are creating for themselves
    if current_user.user_type == "doctor":
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if not doctor or doctor.id != payload.doctor_id:
            raise HTTPException(status_code=403, detail="Cannot create prescription for another doctor")

    prescription = Prescription(
        patient_id=payload.patient_id,
        doctor_id=payload.doctor_id,
        appointment_id=payload.appointment_id,
        medication=payload.medication,
        dosage=payload.dosage,
        duration=payload.duration,
        notes=payload.notes,
        created_at=datetime.utcnow()
    )
    db.add(prescription)
    db.commit()
    db.refresh(prescription)
    return prescription


@router.put(
    "/{prescription_id}",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Prescription"
)
def update_prescription(
    prescription_id: uuid.UUID,
    payload: PrescriptionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id, Prescription.deleted_at.is_(None)).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    if current_user.user_type not in ["doctor", "admin", "receptionist"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    if current_user.user_type == "doctor" and prescription.doctor.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot edit prescription created by another doctor")

    if payload.medication is not None:
        prescription.medication = payload.medication
    if payload.dosage is not None:
        prescription.dosage = payload.dosage
    if payload.duration is not None:
        prescription.duration = payload.duration
    if payload.notes is not None:
        prescription.notes = payload.notes

    db.commit()
    db.refresh(prescription)
    return prescription


@router.delete(
    "/{prescription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Prescription"
)
def delete_prescription(
    prescription_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id, Prescription.deleted_at.is_(None)).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    if current_user.user_type not in ["doctor", "admin", "receptionist"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    if current_user.user_type == "doctor" and prescription.doctor.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot delete prescription created by another doctor")

    prescription.deleted_at = datetime.utcnow()
    db.commit()
    return None
