"""Automated appointment reminder calculation and dispatch for MediBook AI.

Computes 24-hour and 1-hour notification schedules from appointment times,
formats reminder payloads (WhatsApp/Email ready), and dispatches to n8n workflows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from dateutil import parser as date_parser

from integrations.n8n_webhook import send_n8n_webhook, EVENT_REMINDER_TRIGGERED

logger = logging.getLogger("medibook.ai.reminders")


def calculate_reminder_times(appointment_time_iso: str) -> dict[str, Any]:
    """Calculate 24-hour and 1-hour reminder timestamps from an appointment time.

    Returns ISO 8601 formatted reminder strings and default sent statuses
    matching specification field names (reminder_sent_24h, reminder_sent_1h,
    reminder_time_1, reminder_time_2).
    """
    try:
        appt_dt = date_parser.parse(appointment_time_iso)
        if appt_dt.tzinfo is None:
            appt_dt = appt_dt.replace(tzinfo=timezone.utc)
    except Exception as exc:
        logger.warning(
            "Failed to parse appointment_time '%s' for reminders: %s",
            appointment_time_iso,
            exc,
        )
        return {
            "appointment_time": appointment_time_iso,
            "reminder_time_24h": None,
            "reminder_time_1h": None,
            "reminder_time_1": None,
            "reminder_time_2": None,
            "reminder_sent_24h": False,
            "reminder_sent_1h": False,
        }

    dt_24h = appt_dt - timedelta(hours=24)
    dt_1h = appt_dt - timedelta(hours=1)

    iso_24h = dt_24h.strftime("%Y-%m-%dT%H:%M:%SZ")
    iso_1h = dt_1h.strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "appointment_time": appt_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reminder_time_24h": iso_24h,
        "reminder_time_1h": iso_1h,
        "reminder_time_1": iso_24h,
        "reminder_time_2": iso_1h,
        "reminder_sent_24h": False,
        "reminder_sent_1h": False,
    }


def format_reminder_message(
    appointment: dict[str, Any],
    reminder_type: str = "24h",
) -> str:
    """Format human-readable reminder text suitable for WhatsApp or Email."""
    doctor_name = appointment.get("doctor_name") or "Doctor"
    when = appointment.get("appointment_time") or "your scheduled time"
    clinic = appointment.get("clinic_name") or "Prime Care Clinic Taxila"
    appt_id = appointment.get("appointment_id") or appointment.get("id") or ""

    window_label = "tomorrow" if reminder_type == "24h" else "in 1 hour"

    return (
        f"📅 MediBook Reminder: You have an appointment {window_label}!\n\n"
        f"👨‍⚕️ Doctor: Dr. {doctor_name}\n"
        f"⏰ Date & Time: {when}\n"
        f"📍 Location: {clinic}\n"
        f"🔖 Appointment ID: {appt_id}\n\n"
        f"Please arrive 10 minutes early with your ID and previous medical records. "
        f"Reply to this message if you need to reschedule."
    )


def trigger_reminder(
    appointment: dict[str, Any],
    reminder_type: str = "24h",
    *,
    non_blocking: bool = True,
) -> bool:
    """Trigger a 24h or 1h reminder by dispatching to n8n webhook workflow."""
    if reminder_type not in ("24h", "1h"):
        logger.warning("Invalid reminder_type '%s', must be '24h' or '1h'", reminder_type)
        return False

    message = format_reminder_message(appointment, reminder_type)
    payload = {
        "reminder_type": reminder_type,
        "appointment_id": str(appointment.get("appointment_id") or appointment.get("id") or ""),
        "patient_id": str(appointment.get("patient_id") or ""),
        "patient_phone": appointment.get("patient_phone") or appointment.get("phone") or "",
        "patient_email": appointment.get("patient_email") or appointment.get("email") or "",
        "patient_name": appointment.get("patient_name") or "Patient",
        "doctor_name": appointment.get("doctor_name") or "Doctor",
        "clinic_name": appointment.get("clinic_name") or "Prime Care Clinic",
        "clinic_address": appointment.get("clinic_address") or "Ground Floor, ABC Plaza, Taxila",
        "appointment_time": appointment.get("appointment_time"),
        "formatted_message": message,
        "reminder_sent_24h": True if reminder_type == "24h" else False,
        "reminder_sent_1h": True if reminder_type == "1h" else False,
    }

    return send_n8n_webhook(
        EVENT_REMINDER_TRIGGERED,
        payload,
        non_blocking=non_blocking,
    )
