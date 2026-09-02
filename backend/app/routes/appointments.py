import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from dateutil import parser as date_parser

from app.database import get_db
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.core.auth import get_current_user, require_roles
from app.core.audit import log_audit_event
from app.middleware.rate_limiter import limiter
from app.services.appointment_service import (
    create_appointment as svc_create_appointment,
    reschedule_appointment as svc_reschedule_appointment,
    cancel_appointment as svc_cancel_appointment
)
from app.schemas.appointment import (
    AppointmentCreate, AppointmentCreateResponse,
    AppointmentListResponse, AppointmentListItem,
    AppointmentDetailResponse,
    AppointmentRescheduleRequest, AppointmentRescheduleResponse,
    AppointmentCancelResponse,
    AppointmentCompleteRequest, AppointmentCompleteResponse,
    AppointmentNoShowResponse,
    AppointmentFeedbackRequest, AppointmentFeedbackResponse
)

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])


@router.post(
    "",
    response_model=AppointmentCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Appointment",
    description="Book a new clinic appointment with conflict validation, double-booking prevention, and capacity checking."
)
@limiter.limit("30/minute")
def create_new_appointment(
    request: Request,
    payload: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    return svc_create_appointment(
        db=db,
        payload=payload,
        acting_user_id=current_user.id,
        ip_address=ip,
        user_agent=ua
    )


@router.get(
    "",
    response_model=AppointmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Appointments",
    description="Retrieve a paginated and filtered list of system appointments."
)
def list_appointments(
    doctor_id: Optional[uuid.UUID] = Query(None, description="Filter by doctor UUID"),
    patient_id: Optional[uuid.UUID] = Query(None, description="Filter by patient UUID"),
    clinic_id: Optional[uuid.UUID] = Query(None, description="Filter by clinic UUID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    date_from: Optional[str] = Query(None, description="Start date/time (ISO format)"),
    date_to: Optional[str] = Query(None, description="End date/time (ISO format)"),
    date: Optional[str] = Query(None, description="Filter by date ('today' or YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Appointment)

    # Role-based restriction
    if current_user.user_type == "patient":
        # Patients can only see their own appointments
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if patient:
            query = query.filter(Appointment.patient_id == patient.id)
        else:
            return AppointmentListResponse(total=0, limit=limit, offset=offset, appointments=[])
    elif current_user.user_type == "doctor":
        # Doctors can ONLY view their own appointments (force restriction, ignore doctor_id param)
        doc = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if doc:
            query = query.filter(Appointment.doctor_id == doc.id)
        else:
            return AppointmentListResponse(total=0, limit=limit, offset=offset, appointments=[])
        # NOTE: doctor_id query param is ignored for security; doctors cannot view other doctors' appointments
    else:
        # Admin/receptionist can filter by doctor_id if provided
        if doctor_id:
            query = query.filter(Appointment.doctor_id == doctor_id)
    if patient_id:
        # Resolve patient_id: caller may supply patients.id OR users.id (the
        # chatbot and some frontend paths send users.id).  Resolve through the
        # Patient table so both work; fall back to the raw UUID if no row
        # matches, preserving the existing zero-result behaviour for bad IDs.
        resolved_patient = db.query(Patient).filter(
            (Patient.id == patient_id) | (Patient.user_id == patient_id)
        ).first()
        resolved_patient_id = resolved_patient.id if resolved_patient else patient_id
        query = query.filter(Appointment.patient_id == resolved_patient_id)
    if clinic_id:
        query = query.filter(Appointment.clinic_id == clinic_id)
    if status_filter:
        query = query.filter(Appointment.status == status_filter)

    if date:
        try:
            if date.lower() == "today":
                target_d = datetime.utcnow().date()
            else:
                target_d = date_parser.parse(date).date()
            day_start = datetime.combine(target_d, datetime.min.time())
            day_end = datetime.combine(target_d, datetime.max.time())
            query = query.filter(Appointment.appointment_time >= day_start, Appointment.appointment_time <= day_end)
        except Exception:
            pass

    if date_from:
        try:
            df = date_parser.parse(date_from).replace(tzinfo=None)
            query = query.filter(Appointment.appointment_time >= df)
        except Exception:
            pass
    if date_to:
        try:
            dt = date_parser.parse(date_to).replace(tzinfo=None)
            query = query.filter(Appointment.appointment_time <= dt)
        except Exception:
            pass

    total = query.count()
    appts = query.order_by(Appointment.appointment_time.asc()).offset(offset).limit(limit).all()

    items: List[AppointmentListItem] = []
    for a in appts:
        items.append(
            AppointmentListItem(
                appointment_id=a.id,
                clinic_id=a.clinic_id,
                clinic_name=a.clinic.name if a.clinic else "Clinic",
                doctor_id=a.doctor_id,
                doctor_name=a.doctor.user.name if (a.doctor and a.doctor.user) else "Doctor",
                doctor_specialization=a.doctor.specialization if a.doctor else None,
                patient_id=a.patient_id,
                patient_name=a.patient.user.name if (a.patient and a.patient.user) else "Patient",
                appointment_time=a.appointment_time.isoformat() + "Z",
                status=a.status,
                symptoms_reported=a.symptoms_reported,
                urgency_level=a.urgency_level,
                urgency_reason=a.urgency_reason,
                appointment_type=a.appointment_type,
                doctor_notes=a.notes,
                feedback_score=a.feedback_score,
                feedback_text=a.feedback_text,
                feedback_submitted=bool(a.feedback_score),
                created_at=a.created_at.isoformat() + "Z"
            )
        )

    return AppointmentListResponse(
        total=total,
        limit=limit,
        offset=offset,
        appointments=items
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Appointment Details",
    description="Retrieve complete record for an individual appointment."
)
def get_appointment_details(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Appointment not found", "error_code": "NOT_FOUND"}
        )

    # Permission check for patients
    if current_user.user_type == "patient":
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient or appt.patient_id != patient.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"message": "Access forbidden. Cannot view this appointment.", "error_code": "FORBIDDEN"}
            )

    return AppointmentDetailResponse(
        appointment_id=appt.id,
        clinic_id=appt.clinic_id,
        clinic_name=appt.clinic.name if appt.clinic else "Clinic",
        clinic_address=appt.clinic.address if appt.clinic else "Address",
        doctor_id=appt.doctor_id,
        doctor_name=appt.doctor.user.name if (appt.doctor and appt.doctor.user) else "Doctor",
        doctor_specialization=appt.doctor.specialization if appt.doctor else "General",
        patient_id=appt.patient_id,
        patient_name=appt.patient.user.name if (appt.patient and appt.patient.user) else "Patient",
        appointment_time=appt.appointment_time.isoformat() + "Z",
        duration_minutes=appt.duration_minutes or 30,
        status=appt.status,
        symptoms_reported=appt.symptoms_reported,
        urgency_level=appt.urgency_level,
        urgency_reason=appt.urgency_reason,
        appointment_type=appt.appointment_type,
        notes=appt.notes,
        feedback_score=appt.feedback_score,
        feedback_text=appt.feedback_text,
        google_calendar_event_id=appt.google_calendar_event_id,
        created_at=appt.created_at.isoformat() + "Z"
    )


@router.put(
    "/{appointment_id}",
    response_model=AppointmentRescheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Reschedule Appointment",
    description="Update appointment date and time, running full availability and conflict checks."
)
def reschedule_appointment(
    request: Request,
    appointment_id: uuid.UUID,
    payload: AppointmentRescheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    return svc_reschedule_appointment(
        db=db,
        appointment_id=appointment_id,
        new_time_str=payload.appointment_time,
        acting_user_id=current_user.id,
        ip_address=ip,
        user_agent=ua
    )


@router.delete(
    "/{appointment_id}",
    response_model=AppointmentCancelResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel Appointment",
    description="Mark an appointment as cancelled."
)
def cancel_appointment(
    request: Request,
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    return svc_cancel_appointment(
        db=db,
        appointment_id=appointment_id,
        acting_user_id=current_user.id,
        ip_address=ip,
        user_agent=ua
    )


@router.patch(
    "/{appointment_id}/complete",
    response_model=AppointmentCompleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark Appointment Completed",
    description="Mark appointment as completed and attach doctor consultation notes (Doctor or Admin only)."
)
def complete_appointment(
    request: Request,
    appointment_id: uuid.UUID,
    payload: AppointmentCompleteRequest,
    current_user: User = Depends(require_roles("doctor", "admin")),
    db: Session = Depends(get_db)
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Appointment not found", "error_code": "NOT_FOUND"}
        )

    appt.status = "completed"
    if payload.notes:
        appt.notes = payload.notes
    if payload.prescription_id:
        appt.prescription_id = payload.prescription_id
    appt.updated_at = datetime.utcnow()

    log_audit_event(
        db=db,
        action="completed_appointment",
        table_name="appointments",
        record_id=appt.id,
        user_id=current_user.id,
        new_values={"status": "completed", "notes": payload.notes},
        ip_address=request.client.host if request.client else None
    )

    db.commit()
    db.refresh(appt)

    return AppointmentCompleteResponse(
        appointment_id=appt.id,
        status="completed",
        notes=appt.notes,
        completed_at=datetime.utcnow().isoformat() + "Z"
    )


@router.patch(
    "/{appointment_id}/no-show",
    response_model=AppointmentNoShowResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark Appointment as No-Show",
    description="Record that a patient missed their scheduled appointment (Doctor or Receptionist)."
)
def mark_no_show(
    request: Request,
    appointment_id: uuid.UUID,
    current_user: User = Depends(require_roles("doctor", "receptionist", "admin")),
    db: Session = Depends(get_db)
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Appointment not found", "error_code": "NOT_FOUND"}
        )

    appt.status = "no_show"
    appt.updated_at = datetime.utcnow()

    # Increment patient no-show count
    patient = db.query(Patient).filter(Patient.id == appt.patient_id).first()
    if patient:
        patient.total_no_shows = (patient.total_no_shows or 0) + 1

    log_audit_event(
        db=db,
        action="no_show_appointment",
        table_name="appointments",
        record_id=appt.id,
        user_id=current_user.id,
        new_values={"status": "no_show"},
        ip_address=request.client.host if request.client else None
    )

    db.commit()

    return AppointmentNoShowResponse(
        appointment_id=appt.id,
        status="no_show",
        message="Appointment marked as no-show"
    )


@router.patch(
    "/{appointment_id}/feedback",
    response_model=AppointmentFeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Appointment Feedback",
    description="Submit post-consultation rating (1-5) and feedback comment (Patient only)."
)
def submit_appointment_feedback(
    request: Request,
    appointment_id: uuid.UUID,
    payload: AppointmentFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Appointment not found", "error_code": "NOT_FOUND"}
        )

    # Check permission
    patient = db.query(Patient).filter(Patient.id == appt.patient_id).first()
    if not patient or (current_user.user_type == "patient" and patient.user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Cannot submit feedback for another patient's appointment", "error_code": "FORBIDDEN"}
        )

    appt.feedback_score = payload.feedback_score
    appt.feedback_text = payload.feedback_text
    appt.updated_at = datetime.utcnow()

    # Recalculate doctor rating
    doctor = db.query(Doctor).filter(Doctor.id == appt.doctor_id).first()
    if doctor:
        feedbacks = db.query(Appointment.feedback_score).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.feedback_score.isnot(None)
        ).all()
        scores = [f[0] for f in feedbacks if f[0] is not None]
        if scores:
            doctor.rating = round(sum(scores) / len(scores), 2)

    log_audit_event(
        db=db,
        action="submitted_feedback",
        table_name="appointments",
        record_id=appt.id,
        user_id=current_user.id,
        new_values={"score": payload.feedback_score, "text": payload.feedback_text},
        ip_address=request.client.host if request.client else None
    )

    db.commit()
    db.refresh(appt)

    updated_rating = float(doctor.rating if doctor and doctor.rating else payload.feedback_score)

    return AppointmentFeedbackResponse(
        appointment_id=appt.id,
        feedback_score=payload.feedback_score,
        feedback_text=payload.feedback_text,
        doctor_rating_updated=updated_rating,
        message="Thank you for your feedback!"
    )
