import uuid
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional
import pytz
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.doctor import Doctor
from app.models.clinic import Clinic
from app.models.doctor_schedule import DoctorSchedule
from app.models.clinic_holiday import ClinicHoliday
from app.models.appointment import Appointment
from app.schemas.doctor import AvailabilityResponse, DayAvailability, AvailabilitySlot, SessionAvailability

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

DAY_FULL_MAP = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday"
}


def compute_doctor_availability(
    db: Session,
    doctor_id: uuid.UUID,
    start_date: date,
    next_days: int = 1
) -> AvailabilityResponse:
    """Calculate session availability for a doctor over next_days starting from start_date."""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise ValueError("Doctor not found")

    clinic = db.query(Clinic).filter(Clinic.id == doctor.clinic_id).first()
    if not clinic:
        raise ValueError("Clinic not found")

    clinic_tz_name = (clinic.timezone if clinic and clinic.timezone else None) or settings.TIMEZONE or "Asia/Karachi"
    try:
        clinic_tz = pytz.timezone(clinic_tz_name)
    except Exception:
        clinic_tz = KARACHI_TZ

    now_local = datetime.now(clinic_tz)
    working_days_list = [d.strip() for d in clinic.working_days.split(",") if d.strip()]

    duration_mins = doctor.appointment_duration_minutes or 30

    day_availabilities: List[DayAvailability] = []

    for day_offset in range(max(1, next_days)):
        target_date = start_date + timedelta(days=day_offset)
        weekday_idx = target_date.weekday()
        day_abbr = DAY_ABBR_MAP[weekday_idx]
        day_full = DAY_FULL_MAP[weekday_idx]

        # 1. Check if clinic is open on this weekday
        if day_abbr not in working_days_list:
            day_availabilities.append(
                DayAvailability(
                    date=target_date.strftime("%Y-%m-%d"),
                    day=day_full,
                    working_hours="CLOSED",
                    sessions=[
                        SessionAvailability(session="morning", capacity=10, booked=0, remaining=0, available=False),
                        SessionAvailability(session="evening", capacity=5, booked=0, remaining=0, available=False)
                    ],
                    slots=[],
                    booked_count=0,
                    available_count=0
                )
            )
            continue

        # 2. Check clinic holidays
        clinic_holiday = db.query(ClinicHoliday).filter(
            ClinicHoliday.clinic_id == clinic.id,
            ClinicHoliday.holiday_date == target_date
        ).first()

        if clinic_holiday:
            day_availabilities.append(
                DayAvailability(
                    date=target_date.strftime("%Y-%m-%d"),
                    day=day_full,
                    working_hours="HOLIDAY",
                    sessions=[
                        SessionAvailability(session="morning", capacity=10, booked=0, remaining=0, available=False),
                        SessionAvailability(session="evening", capacity=5, booked=0, remaining=0, available=False)
                    ],
                    slots=[],
                    booked_count=0,
                    available_count=0
                )
            )
            continue

        # 3. Check doctor active availability
        if not doctor.is_available:
            day_availabilities.append(
                DayAvailability(
                    date=target_date.strftime("%Y-%m-%d"),
                    day=day_full,
                    working_hours="UNAVAILABLE",
                    sessions=[
                        SessionAvailability(session="morning", capacity=10, booked=0, remaining=0, available=False),
                        SessionAvailability(session="evening", capacity=5, booked=0, remaining=0, available=False)
                    ],
                    slots=[],
                    booked_count=0,
                    available_count=0
                )
            )
            continue

        # 4. Check doctor schedule override for this date
        schedule = db.query(DoctorSchedule).filter(
            DoctorSchedule.doctor_id == doctor.id,
            DoctorSchedule.date == target_date
        ).first()

        if schedule and schedule.is_holiday:
            day_availabilities.append(
                DayAvailability(
                    date=target_date.strftime("%Y-%m-%d"),
                    day=day_full,
                    working_hours="HOLIDAY",
                    sessions=[
                        SessionAvailability(session="morning", capacity=10, booked=0, remaining=0, available=False),
                        SessionAvailability(session="evening", capacity=5, booked=0, remaining=0, available=False)
                    ],
                    slots=[],
                    booked_count=0,
                    available_count=0
                )
            )
            continue

        # Determine working hours string
        start_t = (schedule.start_time if schedule and schedule.start_time else clinic.working_hours_start) or time(9, 0)
        end_t = (schedule.end_time if schedule and schedule.end_time else clinic.working_hours_end) or time(17, 0)
        working_hours_str = f"{start_t.strftime('%H:%M')}-{end_t.strftime('%H:%M')}"

        # 5. Fetch existing active scheduled appointments on target_date for Morning and Evening
        # Map target_date calendar day in clinic_tz to naive UTC range in DB
        start_local = clinic_tz.localize(datetime.combine(target_date, time.min))
        end_local = clinic_tz.localize(datetime.combine(target_date, time.max))
        utc_start = start_local.astimezone(pytz.UTC).replace(tzinfo=None)
        utc_end = end_local.astimezone(pytz.UTC).replace(tzinfo=None)

        booked_morning = db.query(Appointment).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status == "scheduled",
            Appointment.session == "morning",
            Appointment.appointment_time >= utc_start,
            Appointment.appointment_time <= utc_end
        ).count()

        booked_evening = db.query(Appointment).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status == "scheduled",
            Appointment.session == "evening",
            Appointment.appointment_time >= utc_start,
            Appointment.appointment_time <= utc_end
        ).count()

        morning_capacity = 10
        evening_capacity = 5

        morning_remaining = max(0, morning_capacity - booked_morning)
        evening_remaining = max(0, evening_capacity - booked_evening)

        morning_available = morning_remaining > 0
        evening_available = evening_remaining > 0

        # Check if session has already passed if target_date is today or in past
        if target_date == now_local.date():
            # Morning cutoff: 14:00 local time
            if now_local.time() >= time(14, 0):
                morning_available = False
            # Evening cutoff: 21:00 local time
            if now_local.time() >= time(21, 0):
                evening_available = False
        elif target_date < now_local.date():
            morning_available = False
            evening_available = False

        sessions = [
            SessionAvailability(
                session="morning",
                capacity=morning_capacity,
                booked=booked_morning,
                remaining=morning_remaining,
                available=morning_available
            ),
            SessionAvailability(
                session="evening",
                capacity=evening_capacity,
                booked=booked_evening,
                remaining=evening_remaining,
                available=evening_available
            )
        ]

        total_booked = booked_morning + booked_evening
        total_available = (morning_remaining if morning_available else 0) + (evening_remaining if evening_available else 0)

        day_availabilities.append(
            DayAvailability(
                date=target_date.strftime("%Y-%m-%d"),
                day=day_full,
                working_hours=working_hours_str,
                sessions=sessions,
                slots=[],
                booked_count=total_booked,
                available_count=total_available
            )
        )

    return AvailabilityResponse(
        doctor_id=doctor.id,
        doctor_name=doctor.user.name if doctor.user else f"Doctor {doctor.id}",
        specialization=doctor.specialization,
        clinic_name=clinic.name,
        consultation_fee=float(doctor.consultation_fee),
        max_patients_per_day=doctor.max_patients_per_day,
        appointment_duration_minutes=duration_mins,
        availability=day_availabilities
    )
