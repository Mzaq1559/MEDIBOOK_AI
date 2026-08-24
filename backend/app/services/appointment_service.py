import uuid
from datetime import datetime, timedelta, time
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
    """Parse ISO 8601 string and convert to naive UTC/Karachi-normalized datetime."""
    try:
        dt = date_parser.parse(time_str)
        if dt.tzinfo is not None:
            # Convert to UTC or strip tz while normalizing
            dt = dt.astimezone(pytz.utc).replace(tzinfo=None)
        return dt
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid appointment_time format. Use ISO 8601.", "error_code": "INVALID_TIME"}
        )


def validate_booking_slot(
    db: Session,
    doctor: Doctor,
    clinic: Clinic,
    patient_id: uuid.UUID,
    appt_dt: datetime,
    duration_mins: int,
    exclude_appointment_id: Optional[uuid.UUID] = None
):
    """Validate all clinic, doctor, schedule, overlap, and capacity constraints."""
    now_utc = datetime.utcnow()
    if appt_dt <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Appointment time must be in the future", "error_code": "INVALID_TIME"}
        )

    # 1. Clinic working days
    target_date = appt_dt.date()
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

    # 5. Working hours & break times
    start_t = (schedule.start_time if schedule and schedule.start_time else clinic.working_hours_start) or time(9, 0)
    end_t = (schedule.end_time if schedule and schedule.end_time else clinic.working_hours_end) or time(17, 0)
    break_start_t = schedule.break_start if schedule else None
    break_end_t = schedule.break_end if schedule else None

    slot_time = appt_dt.time()
    slot_end_time = (datetime.combine(target_date, slot_time) + timedelta(minutes=duration_mins)).time()

    if slot_time < start_t or slot_end_time > end_t:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Requested slot is outside doctor working hours", "error_code": "SLOT_UNAVAILABLE"}
        )

    if break_start_t and break_end_t:
        if not (slot_end_time <= break_start_t or slot_time >= break_end_t):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": "Requested slot is during doctor break time", "error_code": "SLOT_UNAVAILABLE"}
            )

    # 6. Max daily capacity
    daily_limit = (schedule.max_patients if schedule and schedule.max_patients else doctor.max_patients_per_day) or 20
    start_of_day = datetime.combine(target_date, time.min)
    end_of_day = datetime.combine(target_date, time.max)

    booked_query = db.query(Appointment).filter(
        Appointment.doctor_id == doctor.id,
        Appointment.status == "scheduled",
        Appointment.appointment_time >= start_of_day,
        Appointment.appointment_time <= end_of_day
    )
    if exclude_appointment_id:
        booked_query = booked_query.filter(Appointment.id != exclude_appointment_id)

    if booked_query.count() >= daily_limit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Doctor has reached maximum patient capacity for this date", "error_code": "SLOT_UNAVAILABLE"}
        )

    # 7. Doctor overlapping appointment check
    appt_end_dt = appt_dt + timedelta(minutes=duration_mins)

    # Check for doctor overlapping appointments
    doc_overlap_query = db.query(Appointment).filter(
        Appointment.doctor_id == doctor.id,
        Appointment.status == "scheduled",
        Appointment.appointment_time < appt_end_dt
    )
    if exclude_appointment_id:
        doc_overlap_query = doc_overlap_query.filter(Appointment.id != exclude_appointment_id)

    for ex in doc_overlap_query.all():
        ex_end = ex.appointment_time + timedelta(minutes=ex.duration_minutes or 30)
        if ex_end > appt_dt:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": "Time slot is not available", "error_code": "SLOT_UNAVAILABLE"}
            )

    # 8. Patient overlapping appointment check (DOUBLE_BOOKING)
    pat_overlap_query = db.query(Appointment).filter(
        Appointment.patient_id == patient_id,
        Appointment.status == "scheduled",
        Appointment.appointment_time < appt_end_dt
    )
    if exclude_appointment_id:
        pat_overlap_query = pat_overlap_query.filter(Appointment.id != exclude_appointment_id)

    for ex in pat_overlap_query.all():
        ex_end = ex.appointment_time + timedelta(minutes=ex.duration_minutes or 30)
        if ex_end > appt_dt:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": "Patient already has appointment at this time", "error_code": "DOUBLE_BOOKING"}
            )


def create_appointment(
    db: Session,
    payload: AppointmentCreate,
    acting_user_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AppointmentCreateResponse:
    """Create a new appointment with full transactional validation."""
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

    appt_dt = parse_and_validate_time(payload.appointment_time)
    duration = doctor.appointment_duration_minutes or 30

    # Perform validation
    validate_booking_slot(
        db=db,
        doctor=doctor,
        clinic=clinic,
        patient_id=patient.id,
        appt_dt=appt_dt,
        duration_mins=duration
    )

    # Create appointment
    appt = Appointment(
        id=uuid.uuid4(),
        clinic_id=clinic.id,
        doctor_id=doctor.id,
        patient_id=patient.id,
        appointment_time=appt_dt,
        duration_minutes=duration,
        status="scheduled",
        appointment_type=payload.appointment_type or "in_person",
        symptoms_reported=payload.symptoms_reported,
        urgency_level=payload.urgency_level.lower(),
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
            "appointment_time": appt_dt.isoformat(),
            "status": "scheduled"
        },
        ip_address=ip_address,
        user_agent=user_agent
    )

    db.commit()
    db.refresh(appt)

    doc_name = doctor.user.name if doctor.user else "Doctor"
    reminder_1 = (appt_dt - timedelta(hours=24)).isoformat() + "Z"
    reminder_2 = (appt_dt - timedelta(hours=1)).isoformat() + "Z"

    return AppointmentCreateResponse(
        appointment_id=appt.id,
        clinic_id=clinic.id,
        doctor_id=doctor.id,
        doctor_name=doc_name,
        patient_id=patient.id,
        appointment_time=appt_dt.isoformat() + "Z",
        status=appt.status,
        symptoms_reported=appt.symptoms_reported,
        urgency_level=appt.urgency_level,
        confirmation_message=f"Your appointment with {doc_name} is confirmed for {appt_dt.strftime('%A, %B %d at %I:%M %p')}",
        reminder_time_1=reminder_1,
        reminder_time_2=reminder_2,
        created_at=appt.created_at.isoformat() + "Z"
    )


def reschedule_appointment(
    db: Session,
    appointment_id: uuid.UUID,
    new_time_str: str,
    acting_user_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AppointmentRescheduleResponse:
    """Reschedule an existing appointment."""
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

    new_dt = parse_and_validate_time(new_time_str)
    doctor = db.query(Doctor).filter(Doctor.id == appt.doctor_id).first()
    clinic = db.query(Clinic).filter(Clinic.id == appt.clinic_id).first()

    validate_booking_slot(
        db=db,
        doctor=doctor,
        clinic=clinic,
        patient_id=appt.patient_id,
        appt_dt=new_dt,
        duration_mins=appt.duration_minutes or 30,
        exclude_appointment_id=appt.id
    )

    old_time = appt.appointment_time
    appt.appointment_time = new_dt
    appt.updated_at = datetime.utcnow()

    log_audit_event(
        db=db,
        action="updated_appointment",
        table_name="appointments",
        record_id=appt.id,
        user_id=acting_user_id,
        old_values={"appointment_time": old_time.isoformat()},
        new_values={"appointment_time": new_dt.isoformat()},
        ip_address=ip_address,
        user_agent=user_agent
    )

    db.commit()
    db.refresh(appt)

    reminder_1 = (new_dt - timedelta(hours=24)).isoformat() + "Z"
    reminder_2 = (new_dt - timedelta(hours=1)).isoformat() + "Z"

    return AppointmentRescheduleResponse(
        appointment_id=appt.id,
        appointment_time=new_dt.isoformat() + "Z",
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
