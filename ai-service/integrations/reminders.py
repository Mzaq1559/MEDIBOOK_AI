"""Automated appointment reminder calculation and dispatch for MediBook AI.

Computes 24-hour and 1-hour notification schedules from appointment times,
formats reminder payloads (WhatsApp/Email ready), and dispatches to n8n workflows.
"""

from __future__ import annotations

import logging
import re
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from dateutil import parser as date_parser

from app.config import settings
from integrations.n8n_webhook import send_n8n_webhook, EVENT_REMINDER_TRIGGERED

logger = logging.getLogger("medibook.ai.reminders")


def _doctor_display_name(raw_name: str) -> str:
    """Normalize a doctor's display name to always have exactly one 'Dr.' prefix."""
    name = (raw_name or "Doctor").strip()
    name = re.sub(r"^dr\.\s*", "", name, flags=re.IGNORECASE).strip()
    return f"Dr. {name}" if name else "Dr. Doctor"


def _format_appointment_time(time_value: Any) -> str:
    """Parse and format appointment time to human-readable format.
    
    Handles both datetime objects and ISO 8601 strings.
    Returns formatted string like 'Tuesday, September 02, 2026 at 04:30 PM'.
    Preserves timezone awareness when present.
    """
    if time_value is None:
        return "Scheduled Time"
    
    # If already a datetime object, format directly
    if isinstance(time_value, datetime):
        return time_value.strftime("%A, %B %d, %Y at %I:%M %p")
    
    # Parse ISO string
    try:
        dt = date_parser.parse(str(time_value))
        return dt.strftime("%A, %B %d, %Y at %I:%M %p")
    except Exception as exc:
        logger.warning("Failed to parse appointment_time '%s': %s", time_value, exc)
        return str(time_value)


def send_confirmation_email(appointment: dict[str, Any]) -> bool:
    """Send an immediate appointment confirmation email directly via SMTP."""
    to_email = appointment.get("patient_email") or appointment.get("email") or ""
    if not to_email:
        logger.warning("send_confirmation_email skipped: No recipient email found in appointment payload.")
        return False

    smtp_server = getattr(settings, "SMTP_SERVER", "smtp.gmail.com") or "smtp.gmail.com"
    smtp_port = int(getattr(settings, "SMTP_PORT", 587) or 587)
    smtp_user = getattr(settings, "SMTP_USERNAME", "") or ""
    smtp_pass = getattr(settings, "SMTP_PASSWORD", "") or ""

    if not smtp_server or not smtp_user or not smtp_pass:
        logger.warning("send_confirmation_email skipped: Incomplete SMTP credentials.")
        return False

    try:
        doctor_name = _doctor_display_name(appointment.get("doctor_name"))
        patient_name = appointment.get("patient_name") or "Valued Patient"
        clinic_name = appointment.get("clinic_name") or "MediBook Clinic"
        clinic_address = appointment.get("clinic_address") or "Clinic Address"
        when = _format_appointment_time(appointment.get("appointment_time"))
        appt_id = appointment.get("appointment_id") or appointment.get("id") or ""
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")

        subject = f"✅ Appointment Confirmed: {doctor_name} on {when}"

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ background-color: #2563eb; color: #ffffff; padding: 15px; border-radius: 6px 6px 0 0; text-align: center; }}
        .content {{ padding: 20px 0; line-height: 1.6; }}
        .details-box {{ background-color: #f8fafc; border-left: 4px solid #2563eb; padding: 15px; margin: 15px 0; }}
        .button {{ display: inline-block; padding: 12px 24px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 15px; }}
        .footer {{ font-size: 12px; color: #6b7280; text-align: center; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 15px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0; font-size: 20px;">MediBook AI - Appointment Confirmation</h2>
        </div>
        <div class="content">
            <p>Dear <strong>{patient_name}</strong>,</p>
            <p>Your appointment with <strong>{doctor_name}</strong> has been successfully confirmed.</p>
            
            <div class="details-box">
                <p style="margin: 5px 0;"><strong>Doctor:</strong> {doctor_name}</p>
                <p style="margin: 5px 0;"><strong>Clinic:</strong> {clinic_name}</p>
                <p style="margin: 5px 0;"><strong>Address:</strong> {clinic_address}</p>
                <p style="margin: 5px 0;"><strong>Date & Time:</strong> {when}</p>
                <p style="margin: 5px 0;"><strong>Appointment ID:</strong> {appt_id}</p>
            </div>

            <p style="text-align: center;">
                <a href="{frontend_url}/appointments" class="button" style="color: #ffffff;">View in Patient Portal</a>
            </p>
        </div>
        <div class="footer">
            <p>This is an automated notification from MediBook AI.</p>
        </div>
    </div>
</body>
</html>"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html"))

        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        try:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        finally:
            server.quit()

        logger.info("Successfully sent booking confirmation email via SMTP to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Failed to send booking confirmation email to %s: %s", to_email, exc)
        return False


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
    display_name = _doctor_display_name(doctor_name)
    when = _format_appointment_time(appointment.get("appointment_time"))
    clinic = appointment.get("clinic_name") or "Prime Care Clinic Taxila"
    appt_id = appointment.get("appointment_id") or appointment.get("id") or ""

    window_label = "tomorrow" if reminder_type == "24h" else "in 1 hour"

    return (
        f"📅 MediBook Reminder: You have an appointment {window_label}!\n\n"
        f"👨‍⚕️ Doctor: {display_name}\n"
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
