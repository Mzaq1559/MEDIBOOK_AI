import uuid
from datetime import datetime, date, time
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from dateutil import parser as date_parser

from app.database import get_db
from app.models.doctor import Doctor
from app.models.doctor_schedule import DoctorSchedule
from app.models.clinic import Clinic
from app.models.user import User
from app.core.auth import get_current_user, require_roles, require_verified_doctor
from app.core.audit import log_audit_event
from app.middleware.rate_limiter import limiter
from app.services.availability import compute_doctor_availability
from app.schemas.doctor import (
    DoctorListResponse, DoctorListItem,
    DoctorDetailResponse, AvailabilityResponse,
    DoctorScheduleUpdate, DoctorScheduleResponse,
    DoctorHolidayRequest, DoctorHolidayResponse,
    DoctorCreate, DoctorUpdate,
    DoctorApplicationItem, DoctorApplicationListResponse,
    DoctorApprovalRequest, DoctorRejectionRequest
)

router = APIRouter(prefix="/api/doctors", tags=["Doctors"])


@router.get(
    "",
    response_model=DoctorListResponse,
    status_code=status.HTTP_200_OK,
    summary="List All Doctors",
    description="Retrieve a paginated list of doctors with optional filtering by clinic, specialization, availability, and language."
)
@limiter.limit("50/minute")
def list_doctors(
    request: Request,
    clinic_id: Optional[uuid.UUID] = Query(None, description="Filter by clinic UUID"),
    specialization: Optional[str] = Query(None, description="Filter by specialization"),
    is_available: Optional[bool] = Query(None, description="Filter by availability"),
    language: Optional[str] = Query(None, description="Filter by spoken language"),
    limit: int = Query(50, ge=1, le=500, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db)
):
    query = db.query(Doctor)

    # Only show verified doctors with clinic assignments in public listings
    query = query.join(User, Doctor.user_id == User.id).filter(
        User.is_verified == True,
        Doctor.clinic_id.isnot(None)
    )

    if clinic_id:
        query = query.filter(Doctor.clinic_id == clinic_id)
    if specialization:
        query = query.filter(Doctor.specialization.ilike(f"%{specialization}%"))
    if is_available is not None:
        query = query.filter(Doctor.is_available == is_available)
    if language:
        query = query.filter(Doctor.languages_spoken.ilike(f"%{language}%"))

    total = query.count()
    doctors = query.offset(offset).limit(limit).all()

    items: List[DoctorListItem] = []
    for d in doctors:
        items.append(
            DoctorListItem(
                doctor_id=d.id,
                user_id=d.user_id,
                name=d.user.name if d.user else "Dr. Unknown",
                email=d.user.email if d.user else "",
                phone=d.user.phone if d.user else None,
                specialization=d.specialization,
                consultation_fee=float(d.consultation_fee),
                bio=d.bio,
                is_available=d.is_available,
                rating=float(d.rating or 0.0),
                total_appointments=d.total_appointments or 0,
                languages_spoken=d.languages_spoken,
                clinic_id=d.clinic_id,
                clinic_name=d.clinic.name if d.clinic else "Central Clinic"
            )
        )

    return DoctorListResponse(
        total=total,
        limit=limit,
        offset=offset,
        doctors=items
    )


# ─── Admin: Doctor Application Management ───────────────────────────────────────
# NOTE: This route MUST be defined before /{doctor_id} to avoid path conflicts.

@router.get(
    "/applications",
    response_model=DoctorApplicationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Doctor Applications",
    description="List all doctor self-registration applications (pending, approved, rejected). Admin only."
)
def list_doctor_applications(
    request: Request,
    status_filter: Optional[str] = Query(None, description="Filter by status: pending, approved, rejected"),
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db)
):
    # Join Doctor with User to find self-registered doctor applications
    query = db.query(Doctor).join(User, Doctor.user_id == User.id)

    if status_filter == "pending":
        query = query.filter(User.is_verified == False, User.is_active == True)
    elif status_filter == "approved":
        query = query.filter(User.is_verified == True, Doctor.clinic_id.isnot(None))
    elif status_filter == "rejected":
        query = query.filter(User.is_verified == False, User.is_active == False)

    doctors = query.order_by(Doctor.created_at.desc()).all()

    applications = []
    for doc in doctors:
        user = doc.user
        applications.append(DoctorApplicationItem(
            id=str(doc.id),
            user_id=str(user.id),
            name=user.name,
            email=user.email,
            phone=user.phone,
            specialization=doc.specialization,
            qualifications=doc.qualifications,
            bio=doc.bio,
            is_verified=user.is_verified,
            created_at=user.created_at.isoformat() if user.created_at else "",
        ))

    return DoctorApplicationListResponse(applications=applications, total=len(applications))


@router.get(
    "/{doctor_id}",
    response_model=DoctorDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Doctor Details",
    description="Retrieve full profile and clinic operating details for a specific doctor."
)
def get_doctor_details(doctor_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Doctor not found", "error_code": "NOT_FOUND"}
        )

    clinic = doc.clinic
    start_str = clinic.working_hours_start.strftime("%H:%M") if clinic and clinic.working_hours_start else "09:00"
    end_str = clinic.working_hours_end.strftime("%H:%M") if clinic and clinic.working_hours_end else "17:00"

    return DoctorDetailResponse(
        doctor_id=doc.id,
        user_id=doc.user_id,
        name=doc.user.name if doc.user else "Dr. Unknown",
        email=doc.user.email if doc.user else "",
        phone=doc.user.phone if doc.user else None,
        specialization=doc.specialization,
        qualifications=doc.qualifications,
        consultation_fee=float(doc.consultation_fee),
        bio=doc.bio,
        is_available=doc.is_available,
        max_patients_per_day=doc.max_patients_per_day,
        appointment_duration_minutes=doc.appointment_duration_minutes,
        rating=float(doc.rating or 0.0),
        total_appointments=doc.total_appointments or 0,
        languages_spoken=doc.languages_spoken,
        clinic_id=doc.clinic_id,
        clinic_name=clinic.name if clinic else "Clinic",
        clinic_address=clinic.address if clinic else "Address",
        working_hours_start=start_str,
        working_hours_end=end_str
    )


@router.get(
    "/{doctor_id}/availability",
    response_model=AvailabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Doctor Availability Slots",
    description="Calculate dynamic, conflict-checked available booking slots for a doctor starting from a given date."
)
def get_doctor_availability(
    doctor_id: uuid.UUID,
    date: str = Query(..., description="Target date in ISO format (YYYY-MM-DD)"),
    next_days: int = Query(1, ge=1, le=14, description="Number of consecutive days to inspect"),
    db: Session = Depends(get_db)
):
    try:
        parsed_date = date_parser.parse(date).date()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid date format. Use YYYY-MM-DD.", "error_code": "INVALID_INPUT"}
        )

    # Check if date is in the past
    today_date = datetime.now().date()
    if parsed_date < today_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Date cannot be in the past", "error_code": "INVALID_INPUT"}
        )

    try:
        return compute_doctor_availability(
            db=db,
            doctor_id=doctor_id,
            start_date=parsed_date,
            next_days=next_days
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": str(e), "error_code": "NOT_FOUND"}
        )


@router.put(
    "/{doctor_id}/schedule",
    response_model=DoctorScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Doctor Daily Schedule / Override",
    description="Set custom working hours, breaks, holiday status, or patient limits for a specific date."
)
def update_doctor_schedule(
    request: Request,
    doctor_id: uuid.UUID,
    payload: DoctorScheduleUpdate,
    current_user: User = Depends(require_roles("doctor", "admin")),
    db: Session = Depends(get_db)
):
    # Enforce verification for doctor role
    if current_user.user_type == "doctor" and not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Your doctor account is awaiting clinical verification.", "error_code": "DOCTOR_UNVERIFIED"}
        )
    doc = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Doctor not found", "error_code": "NOT_FOUND"}
        )

    # If role is doctor, verify that they are editing their own schedule
    if current_user.user_type == "doctor" and doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Cannot modify another doctor's schedule", "error_code": "FORBIDDEN"}
        )

    try:
        target_date = date_parser.parse(payload.date).date()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid date format. Use YYYY-MM-DD.", "error_code": "INVALID_INPUT"}
        )

    def parse_time_str(ts: Optional[str]) -> Optional[time]:
        if not ts:
            return None
        parts = ts.split(":")
        return time(int(parts[0]), int(parts[1]))

    schedule = db.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == doc.id,
        DoctorSchedule.date == target_date
    ).first()

    if not schedule:
        schedule = DoctorSchedule(
            id=uuid.uuid4(),
            doctor_id=doc.id,
            date=target_date,
            created_at=datetime.utcnow()
        )
        db.add(schedule)

    if payload.start_time is not None:
        schedule.start_time = parse_time_str(payload.start_time)
    if payload.end_time is not None:
        schedule.end_time = parse_time_str(payload.end_time)
    if payload.is_holiday is not None:
        schedule.is_holiday = payload.is_holiday
    if payload.holiday_reason is not None:
        schedule.holiday_reason = payload.holiday_reason
    if payload.break_start is not None:
        schedule.break_start = parse_time_str(payload.break_start)
    if payload.break_end is not None:
        schedule.break_end = parse_time_str(payload.break_end)
    if payload.max_patients is not None:
        schedule.max_patients = payload.max_patients

    schedule.updated_at = datetime.utcnow()

    log_audit_event(
        db=db,
        action="updated_schedule",
        table_name="doctor_schedules",
        record_id=schedule.id,
        user_id=current_user.id,
        new_values={"date": str(target_date), "is_holiday": schedule.is_holiday},
        ip_address=request.client.host if request.client else None
    )

    db.commit()
    db.refresh(schedule)

    return DoctorScheduleResponse(
        doctor_id=doc.id,
        date=str(target_date),
        start_time=schedule.start_time.strftime("%H:%M") if schedule.start_time else None,
        end_time=schedule.end_time.strftime("%H:%M") if schedule.end_time else None,
        is_holiday=schedule.is_holiday,
        break_start=schedule.break_start.strftime("%H:%M") if schedule.break_start else None,
        break_end=schedule.break_end.strftime("%H:%M") if schedule.break_end else None,
        max_patients=schedule.max_patients,
        message="Schedule updated successfully"
    )


@router.patch(
    "/{doctor_id}/holiday",
    response_model=DoctorHolidayResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark Doctor as On Holiday",
    description="Quickly toggle a doctor's availability to holiday for a given date."
)
def mark_doctor_holiday(
    request: Request,
    doctor_id: uuid.UUID,
    payload: DoctorHolidayRequest,
    current_user: User = Depends(require_roles("doctor", "admin")),
    db: Session = Depends(get_db)
):
    # Enforce verification for doctor role
    if current_user.user_type == "doctor" and not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Your doctor account is awaiting clinical verification.", "error_code": "DOCTOR_UNVERIFIED"}
        )
    doc = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Doctor not found", "error_code": "NOT_FOUND"}
        )

    if current_user.user_type == "doctor" and doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Cannot modify another doctor's holiday", "error_code": "FORBIDDEN"}
        )

    try:
        target_date = date_parser.parse(payload.date).date()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid date format. Use YYYY-MM-DD.", "error_code": "INVALID_INPUT"}
        )

    schedule = db.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == doc.id,
        DoctorSchedule.date == target_date
    ).first()

    if not schedule:
        schedule = DoctorSchedule(
            id=uuid.uuid4(),
            doctor_id=doc.id,
            date=target_date,
            is_holiday=True,
            holiday_reason=payload.reason or "Leave",
            created_at=datetime.utcnow()
        )
        db.add(schedule)
    else:
        schedule.is_holiday = True
        schedule.holiday_reason = payload.reason or schedule.holiday_reason or "Leave"
        schedule.updated_at = datetime.utcnow()

    log_audit_event(
        db=db,
        action="updated_holiday",
        table_name="doctor_schedules",
        record_id=schedule.id,
        user_id=current_user.id,
        new_values={"date": str(target_date), "is_holiday": True, "reason": payload.reason},
        ip_address=request.client.host if request.client else None
    )

    db.commit()

    return DoctorHolidayResponse(
        doctor_id=doc.id,
        date=str(target_date),
        is_holiday=True,
        reason=payload.reason,
        message="Doctor marked as unavailable for this date"
    )


@router.post(
    "",
    response_model=DoctorListItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create Doctor Profile",
    description="Create a new doctor record and associated user account (Admin required)."
)
def create_doctor(
    request: Request,
    payload: DoctorCreate,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db)
):
    from app.core.security import get_password_hash
    # Check if user with this email already exists
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        user = User(
            id=uuid.uuid4(),
            email=payload.email,
            name=payload.name,
            password_hash=get_password_hash("Doctor123!"),
            user_type="doctor",
            is_active=True,
            is_verified=True,  # Admin-created doctors are immediately verified
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(user)
        db.flush()

    doctor = Doctor(
        id=uuid.uuid4(),
        user_id=user.id,
        clinic_id=payload.clinic_id,
        specialization=payload.specialization,
        consultation_fee=payload.consultation_fee,
        max_patients_per_day=payload.max_patients_per_day,
        bio=payload.bio,
        is_available=payload.is_available,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(doctor)

    log_audit_event(
        db=db,
        action="created_doctor",
        table_name="doctors",
        record_id=doctor.id,
        user_id=current_user.id,
        new_values={"name": payload.name, "specialization": payload.specialization},
        ip_address=request.client.host if request.client else None
    )

    db.commit()
    db.refresh(doctor)
    db.refresh(user)

    clinic = doctor.clinic

    return DoctorListItem(
        doctor_id=doctor.id,
        user_id=user.id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        specialization=doctor.specialization,
        consultation_fee=float(doctor.consultation_fee),
        bio=doctor.bio,
        is_available=doctor.is_available,
        rating=float(doctor.rating or 0.0),
        total_appointments=doctor.total_appointments or 0,
        languages_spoken=doctor.languages_spoken or "[]",
        clinic_id=doctor.clinic_id,
        clinic_name=clinic.name if clinic else "Clinic"
    )


@router.put(
    "/{doctor_id}",
    response_model=DoctorListItem,
    status_code=status.HTTP_200_OK,
    summary="Update Doctor Profile",
    description="Update a doctor's profile, fee, specialization, clinic, or availability."
)
def update_doctor(
    request: Request,
    doctor_id: uuid.UUID,
    payload: DoctorUpdate,
    current_user: User = Depends(require_roles("admin", "doctor")),
    db: Session = Depends(get_db)
):
    # Enforce verification for doctor role
    if current_user.user_type == "doctor" and not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Your doctor account is awaiting clinical verification.", "error_code": "DOCTOR_UNVERIFIED"}
        )
    doc = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Doctor not found", "error_code": "NOT_FOUND"}
        )

    if current_user.user_type == "doctor" and doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Cannot update another doctor's profile", "error_code": "FORBIDDEN"}
        )

    if payload.name and doc.user:
        doc.user.name = payload.name
    if payload.email and doc.user:
        doc.user.email = payload.email
    if payload.specialization is not None:
        doc.specialization = payload.specialization
    if payload.clinic_id is not None:
        doc.clinic_id = payload.clinic_id
    if payload.consultation_fee is not None:
        doc.consultation_fee = payload.consultation_fee
    if payload.max_patients_per_day is not None:
        doc.max_patients_per_day = payload.max_patients_per_day
    if payload.bio is not None:
        doc.bio = payload.bio
    if payload.is_available is not None:
        doc.is_available = payload.is_available

    doc.updated_at = datetime.utcnow()

    log_audit_event(
        db=db,
        action="updated_doctor",
        table_name="doctors",
        record_id=doc.id,
        user_id=current_user.id,
        new_values={"specialization": doc.specialization, "is_available": doc.is_available},
        ip_address=request.client.host if request.client else None
    )

    db.commit()
    db.refresh(doc)

    return DoctorListItem(
        doctor_id=doc.id,
        user_id=doc.user_id,
        name=doc.user.name if doc.user else "Doctor",
        email=doc.user.email if doc.user else "",
        phone=doc.user.phone if doc.user else None,
        specialization=doc.specialization,
        consultation_fee=float(doc.consultation_fee),
        bio=doc.bio,
        is_available=doc.is_available,
        rating=float(doc.rating or 0.0),
        total_appointments=doc.total_appointments or 0,
        languages_spoken=doc.languages_spoken or "[]",
        clinic_id=doc.clinic_id,
        clinic_name=doc.clinic.name if doc.clinic else "Clinic"
    )


@router.post(
    "/{doctor_id}/approve",
    status_code=status.HTTP_200_OK,
    summary="Approve Doctor Application",
    description="Approve a self-registered doctor application, assigning clinic and specialization. Admin only."
)
def approve_doctor_application(
    request: Request,
    doctor_id: uuid.UUID,
    payload: DoctorApprovalRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db)
):
    doc = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Doctor application not found", "error_code": "NOT_FOUND"}
        )

    user = db.query(User).filter(User.id == doc.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "User account not found", "error_code": "NOT_FOUND"}
        )

    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Doctor is already verified", "error_code": "ALREADY_VERIFIED"}
        )

    # Update doctor record with assigned clinic and specialization
    doc.clinic_id = payload.clinic_id
    doc.specialization = payload.specialization
    if payload.consultation_fee is not None:
        doc.consultation_fee = payload.consultation_fee
    if payload.qualifications:
        doc.qualifications = payload.qualifications
    doc.is_available = True
    doc.updated_at = datetime.utcnow()

    # Update user verification status
    user.is_verified = True
    user.updated_at = datetime.utcnow()

    log_audit_event(
        db=db,
        action="approved_doctor_application",
        table_name="doctors",
        record_id=doc.id,
        user_id=current_user.id,
        new_values={"clinic_id": str(payload.clinic_id), "specialization": payload.specialization},
        ip_address=request.client.host if request.client else None
    )

    db.commit()

    # Send approval email (non-blocking)
    try:
        from app.services.email_service import send_doctor_approval_email
        send_doctor_approval_email(user.email, user.name, doc)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to send approval email to {user.email}: {e}")

    return {"message": f"Doctor application for {user.name} has been approved.", "doctor_id": str(doc.id)}


@router.post(
    "/{doctor_id}/reject",
    status_code=status.HTTP_200_OK,
    summary="Reject Doctor Application",
    description="Reject a self-registered doctor application. Admin only."
)
def reject_doctor_application(
    request: Request,
    doctor_id: uuid.UUID,
    payload: DoctorRejectionRequest = None,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db)
):
    doc = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Doctor application not found", "error_code": "NOT_FOUND"}
        )

    user = db.query(User).filter(User.id == doc.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "User account not found", "error_code": "NOT_FOUND"}
        )

    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Cannot reject an already verified doctor", "error_code": "ALREADY_VERIFIED"}
        )

    # Mark user as inactive (rejected) but keep the record
    user.is_active = False
    user.updated_at = datetime.utcnow()

    log_audit_event(
        db=db,
        action="rejected_doctor_application",
        table_name="doctors",
        record_id=doc.id,
        user_id=current_user.id,
        new_values={"reason": payload.reason if payload else None},
        ip_address=request.client.host if request.client else None
    )

    db.commit()

    # Send rejection email (non-blocking)
    try:
        from app.services.email_service import send_doctor_rejection_email
        send_doctor_rejection_email(user.email, user.name, payload.reason if payload else None)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to send rejection email to {user.email}: {e}")

    return {"message": f"Doctor application for {user.name} has been rejected."}

