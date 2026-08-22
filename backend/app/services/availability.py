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
from app.schemas.doctor import AvailabilityResponse, DayAvailability, AvailabilitySlot

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
    """Calculate slot availability for a doctor over next_days starting from start_date."""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise ValueError("Doctor not found")

    clinic = db.query(Clinic).filter(Clinic.id == doctor.clinic_id).first()
    if not clinic:
        raise ValueError("Clinic not found")

    now_karachi = datetime.now(KARACHI_TZ)
    working_days_list = [d.strip() for d in clinic.working_days.split(",") if d.strip()]

    duration_mins = doctor.appointment_duration_minutes or 30
    duration_delta = timedelta(minutes=duration_mins)

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
                    slots=[],
                    booked_count=0,
                    available_count=0
                )
            )
            continue

        # Determine start time, end time, breaks, and max capacity
        start_t = (schedule.start_time if schedule and schedule.start_time else clinic.working_hours_start) or time(9, 0)
        end_t = (schedule.end_time if schedule and schedule.end_time else clinic.working_hours_end) or time(17, 0)
        break_start_t = schedule.break_start if schedule else None
        break_end_t = schedule.break_end if schedule else None
        daily_max_patients = (schedule.max_patients if schedule and schedule.max_patients else doctor.max_patients_per_day) or 20

        working_hours_str = f"{start_t.strftime('%H:%M')}-{end_t.strftime('%H:%M')}"

        # 5. Fetch existing active appointments for this doctor on target_date
        start_of_day = datetime.combine(target_date, time.min)
        end_of_day = datetime.combine(target_date, time.max)

        existing_appts = db.query(Appointment).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status == "scheduled",
            Appointment.appointment_time >= start_of_day,
            Appointment.appointment_time <= end_of_day
        ).all()

        booked_appointments_count = len(existing_appts)
        capacity_exhausted = booked_appointments_count >= daily_max_patients

        # 6. Generate time slots
        slots: List[AvailabilitySlot] = []
        current_dt = datetime.combine(target_date, start_t)
        end_dt = datetime.combine(target_date, end_t)

        while current_dt + duration_delta <= end_dt:
            slot_start_time = current_dt.time()
            slot_end_time = (current_dt + duration_delta).time()

            # Timezone-aware representation
            slot_localized = KARACHI_TZ.localize(current_dt)
            slot_iso = slot_localized.isoformat()
            time_str = slot_start_time.strftime("%H:%M")

            is_slot_available = True
            slot_status = "free"

            # Check if in past
            if slot_localized <= now_karachi:
                is_slot_available = False
                slot_status = "booked"

            # Check if during doctor break
            if break_start_t and break_end_t:
                # If slot overlaps break
                if not (slot_end_time <= break_start_t or slot_start_time >= break_end_t):
                    is_slot_available = False
                    slot_status = "booked"

            # Check if overlapping any scheduled appointment
            if is_slot_available:
                for appt in existing_appts:
                    appt_start = appt.appointment_time
                    appt_duration = timedelta(minutes=appt.duration_minutes or 30)
                    appt_end = appt_start + appt_duration

                    # Overlap check
                    if current_dt < appt_end and (current_dt + duration_delta) > appt_start:
                        is_slot_available = False
                        slot_status = "booked"
                        break

            # If daily capacity is reached, all slots become unavailable
            if capacity_exhausted:
                is_slot_available = False
                slot_status = "booked"

            slots.append(
                AvailabilitySlot(
                    time=time_str,
                    timestamp=slot_iso,
                    available=is_slot_available,
                    status=slot_status
                )
            )

            current_dt += duration_delta

        available_slots_count = sum(1 for s in slots if s.available)

        day_availabilities.append(
            DayAvailability(
                date=target_date.strftime("%Y-%m-%d"),
                day=day_full,
                working_hours=working_hours_str,
                slots=slots,
                booked_count=booked_appointments_count,
                available_count=available_slots_count
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
