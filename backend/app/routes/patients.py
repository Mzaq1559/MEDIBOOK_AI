import uuid
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload

logger = logging.getLogger(__name__)

# Karachi timezone offset (UTC+5)
KARACHI_OFFSET = timezone(timedelta(hours=5))


def _utc_to_karachi_iso(naive_utc_dt: datetime) -> str:
    """Convert a naive UTC datetime from the DB to Karachi-local ISO string with +05:00 offset."""
    if naive_utc_dt is None:
        return ""
    karachi_dt = naive_utc_dt + timedelta(hours=5)
    return karachi_dt.isoformat() + "+05:00"

from app.database import get_db
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.user import User
from app.core.auth import get_current_user
from app.core.audit import log_audit_event
from app.schemas.patient import (
    PatientResponse,
    PatientUpdate,
    PatientAppointmentsResponse,
    PatientAppointmentItem
)

router = APIRouter(prefix="/api/patients", tags=["Patients"])


@router.get(
    "/me",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Own Patient Profile",
    description="Retrieve the authenticated patient's own medical and profile details."
)
def get_own_patient_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.user_type != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Only patient users can access this endpoint", "error_code": "FORBIDDEN"}
        )

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Patient record not found", "error_code": "NOT_FOUND"}
        )

    return _build_patient_response(patient)


@router.put(
    "/me",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Own Patient Profile",
    description="Update the authenticated patient's own medical profile including demographics, medical history, and emergency contact."
)
def update_own_patient_profile(
    request: Request,
    payload: PatientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.user_type != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Only patient users can update their own profile", "error_code": "FORBIDDEN"}
        )

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Patient record not found", "error_code": "NOT_FOUND"}
        )

    _apply_patient_update(patient, payload)

    patient.updated_at = datetime.utcnow()

    log_audit_event(
        db=db,
        action="updated_own_profile",
        table_name="patients",
        record_id=patient.id,
        user_id=current_user.id,
        new_values={"fields_updated": [k for k, v in payload.model_dump(exclude_unset=True).items() if v is not None]},
        ip_address=request.client.host if request.client else None
    )

    db.commit()
    db.refresh(patient)

    return _build_patient_response(patient)


def _apply_patient_update(patient: Patient, payload: PatientUpdate) -> None:
    """Apply non-None fields from a PatientUpdate payload to the patient ORM object."""
    import json

    if payload.date_of_birth is not None:
        patient.date_of_birth = date.fromisoformat(payload.date_of_birth)
    if payload.gender is not None:
        patient.gender = payload.gender
    if payload.blood_type is not None:
        patient.blood_type = payload.blood_type if payload.blood_type else None
    if payload.allergies is not None:
        patient.allergies = json.dumps(payload.allergies)
    if payload.medical_conditions is not None:
        patient.medical_conditions = json.dumps(payload.medical_conditions)
    if payload.emergency_contact_name is not None:
        patient.emergency_contact_name = payload.emergency_contact_name if payload.emergency_contact_name else None
    if payload.emergency_contact_phone is not None:
        patient.emergency_contact_phone = payload.emergency_contact_phone if payload.emergency_contact_phone else None
    if payload.emergency_contact_relation is not None:
        patient.emergency_contact_relation = payload.emergency_contact_relation if payload.emergency_contact_relation else None
    if payload.preferred_notification is not None:
        patient.preferred_notification = payload.preferred_notification


def _build_patient_response(patient: Patient) -> PatientResponse:
    """Build a PatientResponse from a Patient ORM object, handling nullable fields."""
    # Calculate age
    age = None
    if patient.date_of_birth:
        today = date.today()
        birth = patient.date_of_birth
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))

    # Determine if profile is considered complete
    profile_completed = bool(
        patient.date_of_birth
        and patient.gender
        and patient.emergency_contact_name
        and patient.emergency_contact_phone
    )

    return PatientResponse(
        patient_id=patient.id,
        user_id=patient.user_id,
        name=patient.user.name if patient.user else "Patient",
        email=patient.user.email if patient.user else "",
        phone=patient.user.phone if patient.user else None,
        date_of_birth=patient.date_of_birth.strftime("%Y-%m-%d") if patient.date_of_birth else None,
        age=age,
        gender=patient.gender,
        blood_type=patient.blood_type,
        allergies=patient.allergies,
        medical_conditions=patient.medical_conditions,
        emergency_contact_name=patient.emergency_contact_name,
        emergency_contact_phone=patient.emergency_contact_phone,
        emergency_contact_relation=patient.emergency_contact_relation,
        preferred_notification=patient.preferred_notification or "whatsapp",
        profile_completed=profile_completed,
        total_appointments=patient.total_appointments or 0,
        total_no_shows=patient.total_no_shows or 0,
        created_at=patient.created_at.isoformat() + "Z" if patient.created_at else ""
    )


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

    return _build_patient_response(patient)


@router.put(
    "/{patient_id}",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Patient Profile",
    description="Update patient demographics, medical history, emergency contact, or notification preferences."
)
def update_patient_profile(
    request: Request,
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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

    _apply_patient_update(patient, payload)

    patient.updated_at = datetime.utcnow()

    log_audit_event(
        db=db,
        action="updated_patient",
        table_name="patients",
        record_id=patient.id,
        user_id=current_user.id,
        new_values={"fields_updated": [k for k, v in payload.model_dump(exclude_unset=True).items() if v is not None]},
        ip_address=request.client.host if request.client else None
    )

    db.commit()
    db.refresh(patient)

    return _build_patient_response(patient)


@router.get(
    "/{patient_id}/appointments",
    response_model=PatientAppointmentsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Patient Appointment History",
    description="Retrieve all past, upcoming, and cancelled appointments for a given patient."
)
def get_patient_appointments(
    patient_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (scheduled, completed, cancelled, no_show)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
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
        if status_filter:
            query = query.filter(Appointment.status == status_filter)

        total = query.count()
        appts = query.options(
            joinedload(Appointment.clinic),
            joinedload(Appointment.doctor).joinedload(Doctor.user),
        ).order_by(Appointment.appointment_time.desc()).offset(offset).limit(limit).all()

        items: List[PatientAppointmentItem] = []
        for a in appts:
            try:
                # --- Safely resolve relationships ---
                doctor = a.doctor
                doctor_user = doctor.user if doctor else None
                clinic = a.clinic

                # Calculate end_time (DB stores naive UTC, convert to Karachi)
                end_time = None
                if a.appointment_time:
                    duration = a.duration_minutes or 30
                    end_dt = a.appointment_time + timedelta(minutes=duration)
                    end_time = _utc_to_karachi_iso(end_dt)

                items.append(
                    PatientAppointmentItem(
                        appointment_id=uuid.UUID(str(a.id)),
                        doctor_id=uuid.UUID(str(a.doctor_id)),
                        doctor_name=doctor_user.name if doctor_user else "Doctor",
                        doctor_specialization=doctor.specialization if doctor else None,
                        clinic_id=uuid.UUID(str(a.clinic_id)),
                        clinic_name=clinic.name if clinic else "Clinic",
                        clinic_address=clinic.address if clinic else None,
                        appointment_time=_utc_to_karachi_iso(a.appointment_time),
                        end_time=end_time,
                        status=a.status or "scheduled",
                        symptoms=a.symptoms_reported or "",
                        urgency=a.urgency_level or "normal",
                        urgency_reason=a.urgency_reason,
                        doctor_notes=a.notes,
                        feedback_score=a.feedback_score,
                        feedback_text=a.feedback_text,
                        feedback_submitted=a.feedback_score is not None,
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping appointment {a.id} due to serialization error: {e}", exc_info=True)
                continue

        return PatientAppointmentsResponse(
            total=total,
            appointments=items
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_patient_appointments failed for patient {patient_id}: {e}", exc_info=True)
        return PatientAppointmentsResponse(total=0, appointments=[])
