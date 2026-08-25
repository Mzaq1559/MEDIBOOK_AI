import uuid
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.user import User
from app.core.auth import get_current_user
from app.core.audit import log_audit_event
from app.schemas.patient import (
    PatientResponse,
    PatientUpdate,
    PatientUpdateResponse,
    PatientAppointmentsResponse,
    PatientAppointmentItem
)

router = APIRouter(prefix="/api/patients", tags=["Patients"])


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Patient Profile",
    description="Retrieve comprehensive medical and profile details of a patient."
)
def get_patient_profile(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    patient = db.query(Patient).filter((Patient.id == patient_id) | (Patient.user_id == patient_id)).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Patient not found", "error_code": "NOT_FOUND"}
        )

    # Permission check: patient self, doctor, receptionist, or admin
    if current_user.user_type == "patient" and patient.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Access forbidden. Cannot view other patient profiles.", "error_code": "FORBIDDEN"}
        )

    # Calculate age
    today = date.today()
    birth = patient.date_of_birth or date(1990, 1, 1)
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))

    return PatientResponse(
        patient_id=patient.id,
        user_id=patient.user_id,
        name=patient.user.name if patient.user else "Patient",
        email=patient.user.email if patient.user else "",
        phone=patient.user.phone if patient.user else None,
        date_of_birth=birth.strftime("%Y-%m-%d"),
        age=age,
        gender=patient.gender or "M",
        blood_type=patient.blood_type,
        allergies=patient.allergies,
        medical_conditions=patient.medical_conditions,
        emergency_contact_name=patient.emergency_contact_name,
        emergency_contact_phone=patient.emergency_contact_phone,
        emergency_contact_relation=patient.emergency_contact_relation,
        preferred_notification=patient.preferred_notification or "whatsapp",
        total_appointments=patient.total_appointments or 0,
        total_no_shows=patient.total_no_shows or 0,
        created_at=patient.created_at.isoformat() + "Z"
    )


@router.put(
    "/{patient_id}",
    response_model=PatientUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Patient Profile",
    description="Update allergies, medical conditions, emergency contact, or notification preferences."
)
def update_patient_profile(
    request: Request,
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    import json
    patient = db.query(Patient).filter((Patient.id == patient_id) | (Patient.user_id == patient_id)).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Patient not found", "error_code": "NOT_FOUND"}
        )

    # Permission: only patient self or admin
    if current_user.user_type not in ("admin", "receptionist") and patient.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Access forbidden. Cannot edit another patient's data.", "error_code": "FORBIDDEN"}
        )

    if payload.allergies is not None:
        patient.allergies = json.dumps(payload.allergies)
    if payload.medical_conditions is not None:
        patient.medical_conditions = json.dumps(payload.medical_conditions)
    if payload.emergency_contact_name is not None:
        patient.emergency_contact_name = payload.emergency_contact_name
    if payload.emergency_contact_phone is not None:
        patient.emergency_contact_phone = payload.emergency_contact_phone
    if payload.emergency_contact_relation is not None:
        patient.emergency_contact_relation = payload.emergency_contact_relation
    if payload.preferred_notification is not None:
        patient.preferred_notification = payload.preferred_notification

    patient.updated_at = datetime.utcnow()

    log_audit_event(
        db=db,
        action="updated_patient",
        table_name="patients",
        record_id=patient.id,
        user_id=current_user.id,
        new_values={"preferred_notification": patient.preferred_notification},
        ip_address=request.client.host if request.client else None
    )

    db.commit()
    db.refresh(patient)

    return PatientUpdateResponse(
        patient_id=patient.id,
        allergies=payload.allergies,
        medical_conditions=payload.medical_conditions,
        preferred_notification=patient.preferred_notification,
        message="Patient details updated successfully"
    )


@router.get(
    "/{patient_id}/appointments",
    response_model=PatientAppointmentsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Patient Appointment History",
    description="Retrieve all past, upcoming, and cancelled appointments for a given patient."
)
def get_patient_appointments(
    patient_id: uuid.UUID,
    status: Optional[str] = Query(None, description="Filter by status (scheduled, completed, cancelled, no_show)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    patient = db.query(Patient).filter((Patient.id == patient_id) | (Patient.user_id == patient_id)).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Patient not found", "error_code": "NOT_FOUND"}
        )

    if current_user.user_type == "patient" and patient.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Access forbidden. Cannot view another patient's appointments.", "error_code": "FORBIDDEN"}
        )

    query = db.query(Appointment).filter(Appointment.patient_id == patient.id)
    if status:
        query = query.filter(Appointment.status == status)

    total = query.count()
    appts = query.order_by(Appointment.appointment_time.desc()).offset(offset).limit(limit).all()

    items: List[PatientAppointmentItem] = []
    for a in appts:
        items.append(
            PatientAppointmentItem(
                appointment_id=a.id,
                doctor_name=a.doctor.user.name if (a.doctor and a.doctor.user) else "Doctor",
                specialization=a.doctor.specialization if a.doctor else "General",
                clinic_name=a.clinic.name if a.clinic else "Clinic",
                appointment_time=a.appointment_time.isoformat() + "Z",
                status=a.status,
                symptoms=a.symptoms_reported,
                urgency=a.urgency_level
            )
        )

    return PatientAppointmentsResponse(
        total=total,
        appointments=items
    )
