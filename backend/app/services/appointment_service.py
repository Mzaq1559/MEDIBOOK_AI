import uuid
from datetime import datetime, date, timedelta, time, timezone
from typing import Optional, Tuple
import pytz
from dateutil import parser as date_parser
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.clinic import Clinic
from app.models.doctor_schedule import DoctorSchedule
from app.models.clinic_holiday import ClinicHoliday
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentCreateResponse,
    AppointmentRescheduleResponse,
    AppointmentCancelResponse,
    AppointmentCompleteResponse,
    AppointmentNoShowResponse,
    AppointmentFeedbackResponse
)
from app.core.audit import log_audit_event

KARACHI_TZ = pytz.timezone(settings.TIMEZONE)

DAY_ABBR_MAP = {
    0: "Mon",
    1: "Tue",
    2: "Wed",
    3: "Thu",
    4: "Fri",
    5: "Sat",
    6: "Sun"
}


def parse_and_validate_time(time_str: str) -> datetime:
    """Parse ISO 8601 string and convert to naive UTC datetime."""
    try:
        dt = date_parser.parse(time_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone(pytz.UTC).replace(tzinfo=None)
        return dt
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid appointment_time format. Use ISO 8601.", "error_code": "INVALID_TIME"}
        )


SESSION_CAPACITY = {"morning": 10, "evening": 5}


def validate_session_booking(
    db: Session,
    doctor: Doctor,
    clinic: Clinic,
    patient_id: uuid.UUID,
    target_date: date,
    session: str,
    exclude_appointment_id: Optional[uuid.UUID] = None
) -> Tuple[datetime, str]:
    """Validate all clinic, doctor, schedule, capacity, and double-booking constraints for session booking."""
    session = session.lower().strip()
    if session not in {"morning", "evening"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Invalid session '{session}'. Must be 'morning' or 'evening'.", "error_code": "INVALID_SESSION"}
        )

    clinic_tz_name = (clinic.timezone if clinic and clinic.timezone else None) or settings.TIMEZONE or "Asia/Karachi"
    try:
        clinic_tz = pytz.timezone(clinic_tz_name)
    except Exception:
        clinic_tz = pytz.timezone("Asia/Karachi")

    now_clinic = datetime.now(clinic_tz)
    today_clinic = now_clinic.date()

    if target_date < today_clinic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Appointment date cannot be in the past", "error_code": "INVALID_DATE"}
        )

    if target_date == today_clinic:
        if session == "morning" and now_clinic.time() >= time(14, 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": "Morning session has already passed for today", "error_code": "SESSION_UNAVAILABLE"}
            )
        if session == "evening" and now_clinic.time() >= time(21, 0):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": "Evening session has already passed for today", "error_code": "SESSION_UNAVAILABLE"}
            )

    # 1. Clinic working days
    weekday_idx = target_date.weekday()
    day_abbr = DAY_ABBR_MAP[weekday_idx]
    working_days = [d.strip() for d in clinic.working_days.split(",") if d.strip()]

    if day_abbr not in working_days:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": f"Clinic is closed on {day_abbr}", "error_code": "SLOT_UNAVAILABLE"}
        )

    # 2. Clinic holiday
    clinic_holiday = db.query(ClinicHoliday).filter(
        ClinicHoliday.clinic_id == clinic.id,
        ClinicHoliday.holiday_date == target_date
    ).first()
    if clinic_holiday:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": f"Clinic is closed for holiday: {clinic_holiday.holiday_name}", "error_code": "SLOT_UNAVAILABLE"}
        )

    # 3. Doctor availability
    if not doctor.is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Doctor is currently not available for bookings", "error_code": "SLOT_UNAVAILABLE"}
        )

    # 4. Doctor schedule override
    schedule = db.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == doctor.id,
        DoctorSchedule.date == target_date
    ).first()

    if schedule and schedule.is_holiday:
        reason = schedule.holiday_reason or "Leave"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": f"Doctor is on holiday: {reason}", "error_code": "SLOT_UNAVAILABLE"}
        )

    # 5. Concurrency control:
    # On PostgreSQL, acquire transactional advisory lock strictly scoped to doctor_id + target_date + session.
    # The lock is held until transaction commit/rollback. Do not suppress unexpected locking errors.
    bind = db.get_bind()
    if bind and bind.dialect.name == "postgresql":
        from sqlalchemy import text
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('medibook_booking'), hashtext(:lock_key))"),
            {"lock_key": f"{doctor.id}:{target_date}:{session}"}
        )

    # 6. Session capacity check: Morning max 10, Evening max 5
    # Calculate exact UTC boundaries for the clinic calendar day
    start_local = clinic_tz.localize(datetime.combine(target_date, time.min))
    end_local = clinic_tz.localize(datetime.combine(target_date, time.max))
    utc_start = start_local.astimezone(pytz.UTC).replace(tzinfo=None)
    utc_end = end_local.astimezone(pytz.UTC).replace(tzinfo=None)

    limit = 10 if session == "morning" else 5

    booked_query = db.query(Appointment).filter(
        Appointment.doctor_id == doctor.id,
        Appointment.status == "scheduled",
        Appointment.session == session,
        Appointment.appointment_time >= utc_start,
        Appointment.appointment_time <= utc_end
    )
    if exclude_appointment_id:
        booked_query = booked_query.filter(Appointment.id != exclude_appointment_id)

    if booked_query.count() >= limit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"{session.capitalize()} session is fully booked for this doctor on the selected date.",
                "error_code": "SESSION_FULL"
            }
        )

    # 7. Patient double-booking check (same session on the same clinic date)
    pat_overlap_query = db.query(Appointment).filter(
        Appointment.patient_id == patient_id,
        Appointment.status == "scheduled",
        Appointment.session == session,
        Appointment.appointment_time >= utc_start,
        Appointment.appointment_time <= utc_end
    )
    if exclude_appointment_id:
        pat_overlap_query = pat_overlap_query.filter(Appointment.id != exclude_appointment_id)

    if pat_overlap_query.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"Patient already has an appointment booked for the {session} session on this date",
                "error_code": "DOUBLE_BOOKING"
            }
        )

    # 8. Assign internal session anchor time (Clinic local time converted to naive UTC for DB storage)
    # Morning -> 09:00 clinic time
    # Evening -> 17:00 clinic time
    anchor_hour = 9 if session == "morning" else 17
    anchor_local = clinic_tz.localize(datetime.combine(target_date, time(anchor_hour, 0)))
    anchor_utc_naive = anchor_local.astimezone(pytz.UTC).replace(tzinfo=None)

    return anchor_utc_naive, session


def validate_booking_slot(
    db: Session,
    doctor: Doctor,
    clinic: Clinic,
    patient_id: uuid.UUID,
    appt_dt: datetime,
    duration_mins: int,
    exclude_appointment_id: Optional[uuid.UUID] = None
):
    """Legacy compatibility validator mapping datetime to session-based validation."""
    karachi_hour = (appt_dt + timedelta(hours=5)).hour
    session = "morning" if karachi_hour < 14 else "evening"
    validate_session_booking(
        db=db,
        doctor=doctor,
        clinic=clinic,
        patient_id=patient_id,
        target_date=appt_dt.date(),
        session=session,
        exclude_appointment_id=exclude_appointment_id
    )


def create_appointment(
    db: Session,
    payload: AppointmentCreate,
    acting_user_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AppointmentCreateResponse:
    """Create a new appointment with authoritative session capacity validation and safe concurrency."""
    patient = None
    if payload.patient_id:
        patient = db.query(Patient).filter(
            or_(Patient.id == payload.patient_id, Patient.user_id == payload.patient_id)
        ).first()

    if not patient and acting_user_id:
        patient = db.query(Patient).filter(Patient.user_id == acting_user_id).first()

    if not patient:
        target_id = payload.patient_id or acting_user_id
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"Patient record not found for patient_id/user_id '{target_id}'", "error_code": "NOT_FOUND"}
        )

    doctor = None
    if payload.doctor_id:
        doctor = db.query(Doctor).filter(
            or_(Doctor.id == payload.doctor_id, Doctor.user_id == payload.doctor_id)
        ).first()

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"Doctor record not found for doctor_id/user_id '{payload.doctor_id}'", "error_code": "NOT_FOUND"}
        )

    clinic = db.query(Clinic).filter(Clinic.id == doctor.clinic_id).first()
    if not clinic or not clinic.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"Clinic not found or inactive for clinic_id '{doctor.clinic_id}'", "error_code": "NOT_FOUND"}
        )

    clinic_tz_name = (clinic.timezone if clinic and clinic.timezone else None) or settings.TIMEZONE or "Asia/Karachi"
    try:
        clinic_tz = pytz.timezone(clinic_tz_name)
    except Exception:
        clinic_tz = pytz.timezone("Asia/Karachi")

    # Determine target_date and session
    target_date = None
    session = payload.session.lower().strip() if payload.session else None

    raw_date = payload.appointment_date or getattr(payload, "date", None)
    if raw_date:
        try:
            if isinstance(raw_date, date):
                target_date = raw_date
            else:
                target_date = date_parser.parse(str(raw_date)).date()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Invalid appointment_date format. Use YYYY-MM-DD.", "error_code": "INVALID_DATE"}
            )
    elif payload.appointment_time:
        try:
            target_dt = parse_and_validate_time(payload.appointment_time)
            target_dt_local = target_dt.replace(tzinfo=pytz.UTC).astimezone(clinic_tz)
            target_date = target_dt_local.date()
            if not session:
                session = "morning" if target_dt_local.hour < 14 else "evening"
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Invalid appointment_time format. Use ISO 8601.", "error_code": "INVALID_TIME"}
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "appointment_date or appointment_time is required", "error_code": "INVALID_INPUT"}
        )

    if not session or session not in {"morning", "evening"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Invalid session '{session}'. Must be 'morning' or 'evening'.", "error_code": "INVALID_SESSION"}
        )

    duration = doctor.appointment_duration_minutes or 30

    # Perform session validation and concurrency locking
    anchor_utc_naive, valid_session = validate_session_booking(
        db=db,
        doctor=doctor,
        clinic=clinic,
        patient_id=patient.id,
        target_date=target_date,
        session=session
    )

    # Create appointment
    appt = Appointment(
        id=uuid.uuid4(),
        clinic_id=clinic.id,
        doctor_id=doctor.id,
        patient_id=patient.id,
        session=valid_session,
        appointment_time=anchor_utc_naive,
        duration_minutes=duration,
        status="scheduled",
        appointment_type=payload.appointment_type or "in_person",
        symptoms_reported=payload.symptoms_reported,
        urgency_level=payload.urgency_level.lower(),
        urgency_reason=payload.urgency_reason,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(appt)

    # Update patient & doctor stats
    patient.total_appointments = (patient.total_appointments or 0) + 1
    doctor.total_appointments = (doctor.total_appointments or 0) + 1

    # Log audit event
    log_audit_event(
        db=db,
        action="created_appointment",
        table_name="appointments",
        record_id=appt.id,
        user_id=acting_user_id,
        new_values={
            "doctor_id": str(doctor.id),
            "patient_id": str(patient.id),
            "session": valid_session,
            "appointment_time": anchor_utc_naive.isoformat(),
            "status": "scheduled"
        },
        ip_address=ip_address,
        user_agent=user_agent
    )

    db.commit()
    db.refresh(appt)

    doc_name = doctor.user.name if doctor.user else "Doctor"
    appt_local = anchor_utc_naive.replace(tzinfo=pytz.UTC).astimezone(clinic_tz)
    reminder_1 = (appt_local - timedelta(hours=24)).isoformat()
    reminder_2 = (appt_local - timedelta(hours=1)).isoformat()
    session_title = valid_session.capitalize()

    return AppointmentCreateResponse(
        appointment_id=appt.id,
        clinic_id=clinic.id,
        doctor_id=doctor.id,
        doctor_name=doc_name,
        patient_id=patient.id,
        session=valid_session,
        appointment_time=appt_local.isoformat(),
        status=appt.status,
        symptoms_reported=appt.symptoms_reported,
        urgency_level=appt.urgency_level,
        urgency_reason=appt.urgency_reason,
        confirmation_message=f"Your appointment with {doc_name} is confirmed for {target_date.strftime('%A, %B %d, %Y')} ({session_title} Session)",
        reminder_time_1=reminder_1,
        reminder_time_2=reminder_2,
        created_at=appt.created_at.isoformat() + "Z"
    )


def reschedule_appointment(
    db: Session,
    appointment_id: uuid.UUID,
    new_time_str: Optional[str] = None,
    payload: Optional[AppointmentRescheduleRequest] = None,
    acting_user_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AppointmentRescheduleResponse:
    """Reschedule an existing appointment respecting session capacity."""
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Appointment not found", "error_code": "NOT_FOUND"}
        )

    if appt.status in {"completed", "cancelled"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Cannot reschedule a {appt.status} appointment", "error_code": "INVALID_INPUT"}
        )

    doctor = db.query(Doctor).filter(Doctor.id == appt.doctor_id).first()
    clinic = db.query(Clinic).filter(Clinic.id == appt.clinic_id).first()
    clinic_tz_name = (clinic.timezone if clinic and clinic.timezone else None) or settings.TIMEZONE or "Asia/Karachi"
    try:
        clinic_tz = pytz.timezone(clinic_tz_name)
    except Exception:
        clinic_tz = pytz.timezone("Asia/Karachi")

    # Determine target_date and session
    target_date = None
    new_session = None

    if payload:
        if payload.appointment_date:
            try:
                target_date = date_parser.parse(payload.appointment_date).date()
            except Exception:
                pass
        if payload.session:
            new_session = payload.session.lower().strip()
        if not target_date and payload.appointment_time:
            new_time_str = payload.appointment_time

    if new_time_str and not target_date:
        dt = parse_and_validate_time(new_time_str)
        local_dt = dt.replace(tzinfo=pytz.UTC).astimezone(clinic_tz)
        target_date = local_dt.date()
        if not new_session:
            new_session = "morning" if local_dt.hour < 14 else "evening"

    if not target_date:
        appt_local = appt.appointment_time.replace(tzinfo=pytz.UTC).astimezone(clinic_tz)
        target_date = appt_local.date()
    if not new_session:
        new_session = appt.session or "morning"

    anchor_utc_naive, valid_session = validate_session_booking(
        db=db,
        doctor=doctor,
        clinic=clinic,
        patient_id=appt.patient_id,
        target_date=target_date,
        session=new_session,
        exclude_appointment_id=appt.id
    )

    old_time = appt.appointment_time
    old_session = appt.session
    appt.appointment_time = anchor_utc_naive
    appt.session = valid_session
    appt.updated_at = datetime.utcnow()

    log_audit_event(
        db=db,
        action="updated_appointment",
        table_name="appointments",
        record_id=appt.id,
        user_id=acting_user_id,
        old_values={"appointment_time": old_time.isoformat(), "session": old_session},
        new_values={"appointment_time": anchor_utc_naive.isoformat(), "session": valid_session},
        ip_address=ip_address,
        user_agent=user_agent
    )

    db.commit()
    db.refresh(appt)

    # DB stores naive UTC; convert to clinic timezone for response
    new_local = anchor_utc_naive.replace(tzinfo=pytz.UTC).astimezone(clinic_tz)
    reminder_1 = (new_local - timedelta(hours=24)).isoformat()
    reminder_2 = (new_local - timedelta(hours=1)).isoformat()

    return AppointmentRescheduleResponse(
        appointment_id=appt.id,
        session=valid_session,
        appointment_time=new_local.isoformat(),
        status=appt.status,
        message="Appointment rescheduled successfully",
        new_reminder_time_1=reminder_1,
        new_reminder_time_2=reminder_2
    )


def cancel_appointment(
    db: Session,
    appointment_id: uuid.UUID,
    acting_user_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AppointmentCancelResponse:
    """Cancel an appointment."""
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Appointment not found", "error_code": "NOT_FOUND"}
        )

    if appt.status == "cancelled":
        return AppointmentCancelResponse(
            appointment_id=appt.id,
            status="cancelled",
            message="Appointment is already cancelled",
            cancelled_at=(appt.cancelled_at or datetime.utcnow()).isoformat() + "Z"
        )

    appt.status = "cancelled"
    appt.cancelled_at = datetime.utcnow()
    appt.updated_at = datetime.utcnow()

    log_audit_event(
        db=db,
        action="cancelled_appointment",
        table_name="appointments",
        record_id=appt.id,
        user_id=acting_user_id,
        new_values={"status": "cancelled", "cancelled_at": appt.cancelled_at.isoformat()},
        ip_address=ip_address,
        user_agent=user_agent
    )

    db.commit()
    db.refresh(appt)

    return AppointmentCancelResponse(
        appointment_id=appt.id,
        status="cancelled",
        message="Appointment cancelled successfully",
        cancelled_at=appt.cancelled_at.isoformat() + "Z"
    )
