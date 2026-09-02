import smtplib
import logging
from datetime import datetime
from uuid import UUID
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.orm import Session
from dateutil import parser as date_parser
import pytz

from app.core.config import settings
from app.models.appointment import Appointment

logger = logging.getLogger(__name__)

KARACHI_TZ = pytz.timezone(settings.TIMEZONE)


def _format_appointment_time(time_value) -> str:
    """Format appointment time to human-readable string in Karachi timezone.
    
    Handles both datetime objects and ISO 8601 strings defensively.
    DB stores naive UTC, so we convert to Karachi time before formatting.
    Returns formatted string like 'Tuesday, September 02, 2026 at 04:30 PM'.
    """
    if time_value is None:
        return "Scheduled Time"
    
    if isinstance(time_value, datetime):
        dt = time_value
        # Naive datetime from DB is stored as UTC — convert to Karachi
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt).astimezone(KARACHI_TZ)
        return dt.strftime("%A, %B %d, %Y at %I:%M %p")
    
    # Parse ISO string defensively
    try:
        dt = date_parser.parse(str(time_value))
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt).astimezone(KARACHI_TZ)
        return dt.strftime("%A, %B %d, %Y at %I:%M %p")
    except Exception as exc:
        logger.warning("Failed to parse appointment_time '%s': %s", time_value, exc)
        return str(time_value)


def _send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Helper to send an HTML email via configured SMTP server."""
    if not settings.SMTP_SERVER or not settings.SMTP_PASSWORD or not settings.SMTP_USERNAME:
        logger.warning(
            "SMTP configuration incomplete (server=%s, user=%s, password_configured=%s). Skipping email delivery.",
            settings.SMTP_SERVER,
            settings.SMTP_USERNAME,
            bool(settings.SMTP_PASSWORD)
        )
        return False

    try:
        logger.info("Connecting to SMTP server %s:%s to send email to %s...", settings.SMTP_SERVER, settings.SMTP_PORT, to_email)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_USERNAME or "noreply@primecare.pk"
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html"))

        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=10)
        try:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        finally:
            server.quit()
        logger.info("Successfully sent email via SMTP to %s with subject '%s'", to_email, subject)
        return True
    except Exception as e:
        logger.error("SMTP delivery failed for recipient %s (server=%s:%s): %s", to_email, settings.SMTP_SERVER, settings.SMTP_PORT, e)
        return False


def send_appointment_confirmation(appointment_id: UUID, db: Session) -> bool:
    """
    Send an immediate appointment confirmation email upon successful booking.
    Returns True on success, False on failure without raising exceptions.
    """
    try:
        logger.info("Triggered appointment confirmation email dispatch for appointment %s", appointment_id)
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            logger.warning(f"Appointment {appointment_id} not found for confirmation email.")
            return False

        patient_email = appointment.patient.user.email if (appointment.patient and appointment.patient.user) else None
        patient_name = appointment.patient.user.name if (appointment.patient and appointment.patient.user) else "Valued Patient"
        raw_doc_name = appointment.doctor.user.name if (appointment.doctor and appointment.doctor.user) else "Doctor"
        doctor_name = raw_doc_name if raw_doc_name.startswith("Dr.") else f"Dr. {raw_doc_name}"
        doctor_spec = appointment.doctor.specialization if appointment.doctor else "General Physician"
        clinic_name = appointment.clinic.name if appointment.clinic else "MediBook Clinic"
        clinic_address = appointment.clinic.address if appointment.clinic else "Clinic Address"

        if not patient_email:
            logger.warning(f"No patient email found for appointment {appointment_id}. Skipping confirmation email.")
            return False

        formatted_time = _format_appointment_time(appointment.appointment_time)
        portal_url = f"{settings.FRONTEND_URL}/appointments"
        subject = f"✅ Appointment Confirmed: {doctor_name} on {formatted_time}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .header {{ background-color: #16a34a; color: #ffffff; padding: 15px; border-radius: 6px 6px 0 0; text-align: center; }}
                .content {{ padding: 20px 0; line-height: 1.6; }}
                .details-box {{ background-color: #f8fafc; border-left: 4px solid #16a34a; padding: 15px; margin: 15px 0; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #16a34a; color: #ffffff; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 15px; }}
                .footer {{ font-size: 12px; color: #6b7280; text-align: center; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 15px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2 style="margin: 0; font-size: 20px;">MediBook AI — Appointment Confirmed</h2>
                </div>
                <div class="content">
                    <p>Dear <strong>{patient_name}</strong>,</p>
                    <p>Your appointment has been successfully booked and confirmed. Below are your appointment details:</p>

                    <div class="details-box">
                        <p style="margin: 5px 0;"><strong>Doctor:</strong> Dr. {doctor_name} ({doctor_spec})</p>
                        <p style="margin: 5px 0;"><strong>Date & Time:</strong> {formatted_time}</p>
                        <p style="margin: 5px 0;"><strong>Clinic:</strong> {clinic_name}</p>
                        <p style="margin: 5px 0;"><strong>Address:</strong> {clinic_address}</p>
                        <p style="margin: 5px 0;"><strong>Type:</strong> {appointment.appointment_type.replace('_', ' ').title() if appointment.appointment_type else 'In Person'}</p>
                        <p style="margin: 5px 0;"><strong>Symptoms:</strong> {appointment.symptoms_reported or 'General Consultation'}</p>
                        <p style="margin: 5px 0;"><strong>Appointment ID:</strong> {appointment.id}</p>
                    </div>

                    <p>You will also receive automated reminders 24 hours and 1 hour prior to your visit. If you need to view or manage your appointment, please click below:</p>
                    <p style="text-align: center;">
                        <a href="{portal_url}" class="button" style="color: #ffffff;">View in Portal</a>
                    </p>
                </div>
                <div class="footer">
                    <p>This is an automated confirmation from MediBook AI. Please do not reply directly to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """

        success = _send_email(patient_email, subject, html_content)
        if success:
            logger.info(f"Successfully sent appointment confirmation email to {patient_email} for appointment {appointment_id}.")
        return success

    except Exception as e:
        logger.warning(f"Error sending confirmation email for appointment {appointment_id}: {e}")
        return False


def send_appointment_rescheduled(appointment_id: UUID, db: Session) -> bool:
    """Send an appointment rescheduled notification email."""
    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            return False

        patient_email = appointment.patient.user.email if (appointment.patient and appointment.patient.user) else None
        patient_name = appointment.patient.user.name if (appointment.patient and appointment.patient.user) else "Valued Patient"
        raw_doc_name = appointment.doctor.user.name if (appointment.doctor and appointment.doctor.user) else "Doctor"
        doctor_name = raw_doc_name if raw_doc_name.startswith("Dr.") else f"Dr. {raw_doc_name}"
        clinic_name = appointment.clinic.name if appointment.clinic else "MediBook Clinic"

        if not patient_email:
            return False

        formatted_time = _format_appointment_time(appointment.appointment_time)
        portal_url = f"{settings.FRONTEND_URL}/appointments"
        subject = f"📅 Appointment Rescheduled: {doctor_name} on {formatted_time}"

        html_content = f"""
        <!DOCTYPE html>
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
                    <h2 style="margin: 0; font-size: 20px;">MediBook AI — Appointment Rescheduled</h2>
                </div>
                <div class="content">
                    <p>Dear <strong>{patient_name}</strong>,</p>
                    <p>Your appointment with <strong>{doctor_name}</strong> at <strong>{clinic_name}</strong> has been successfully rescheduled.</p>

                    <div class="details-box">
                        <p style="margin: 5px 0;"><strong>New Date & Time:</strong> {formatted_time}</p>
                        <p style="margin: 5px 0;"><strong>Appointment ID:</strong> {appointment.id}</p>
                    </div>

                    <p style="text-align: center;">
                        <a href="{portal_url}" class="button" style="color: #ffffff;">Manage Appointment</a>
                    </p>
                </div>
                <div class="footer">
                    <p>This is an automated notification from MediBook AI.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return _send_email(patient_email, subject, html_content)
    except Exception as e:
        logger.warning(f"Error sending reschedule email for appointment {appointment_id}: {e}")
        return False


def send_appointment_cancelled(appointment_id: UUID, db: Session) -> bool:
    """Send an appointment cancellation notification email."""
    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            return False

        patient_email = appointment.patient.user.email if (appointment.patient and appointment.patient.user) else None
        patient_name = appointment.patient.user.name if (appointment.patient and appointment.patient.user) else "Valued Patient"
        raw_doc_name = appointment.doctor.user.name if (appointment.doctor and appointment.doctor.user) else "Doctor"
        doctor_name = raw_doc_name if raw_doc_name.startswith("Dr.") else f"Dr. {raw_doc_name}"

        if not patient_email:
            return False

        formatted_time = _format_appointment_time(appointment.appointment_time)
        subject = f"❌ Appointment Cancelled: {doctor_name}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .header {{ background-color: #dc2626; color: #ffffff; padding: 15px; border-radius: 6px 6px 0 0; text-align: center; }}
                .content {{ padding: 20px 0; line-height: 1.6; }}
                .footer {{ font-size: 12px; color: #6b7280; text-align: center; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 15px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2 style="margin: 0; font-size: 20px;">MediBook AI — Appointment Cancelled</h2>
                </div>
                <div class="content">
                    <p>Dear <strong>{patient_name}</strong>,</p>
                    <p>Your appointment scheduled for <strong>{formatted_time}</strong> with <strong>{doctor_name}</strong> has been cancelled.</p>
                    <p>If this was a mistake or you wish to schedule a new visit, please visit the MediBook AI portal.</p>
                </div>
                <div class="footer">
                    <p>This is an automated notification from MediBook AI.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return _send_email(patient_email, subject, html_content)
    except Exception as e:
        logger.warning(f"Error sending cancellation email for appointment {appointment_id}: {e}")
        return False


def send_reminder(appointment_id: UUID, reminder_type: str, db: Session) -> bool:
    """
    Send an appointment reminder email (24h or 1h before appointment).
    Returns True on success, False on failure without raising exceptions.
    """
    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            logger.warning(f"Appointment {appointment_id} not found for email reminder.")
            return False

        patient_email = appointment.patient.user.email if (appointment.patient and appointment.patient.user) else None
        patient_name = appointment.patient.user.name if (appointment.patient and appointment.patient.user) else "Valued Patient"
        raw_doc_name = appointment.doctor.user.name if (appointment.doctor and appointment.doctor.user) else "Doctor"
        doctor_name = raw_doc_name if raw_doc_name.startswith("Dr.") else f"Dr. {raw_doc_name}"
        clinic_name = appointment.clinic.name if appointment.clinic else "MediBook Clinic"
        clinic_address = appointment.clinic.address if appointment.clinic else "Clinic Address"

        if not patient_email:
            logger.warning(f"No patient email found for appointment {appointment_id}. Skipping email reminder.")
            return False

        formatted_time = _format_appointment_time(appointment.appointment_time)
        reschedule_url = f"{settings.FRONTEND_URL}/appointments"

        time_frame = "24 hours" if reminder_type == "24h" else "1 hour"
        subject = f"Reminder: Upcoming Appointment with Dr. {doctor_name} in {time_frame}"

        html_content = f"""
        <!DOCTYPE html>
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
                    <h2 style="margin: 0; font-size: 20px;">MediBook AI - Appointment Reminder</h2>
                </div>
                <div class="content">
                    <p>Dear <strong>{patient_name}</strong>,</p>
                    <p>This is a friendly reminder that your appointment is scheduled in approximately <strong>{time_frame}</strong>.</p>

                    <div class="details-box">
                        <p style="margin: 5px 0;"><strong>Doctor:</strong> Dr. {doctor_name}</p>
                        <p style="margin: 5px 0;"><strong>Date & Time:</strong> {formatted_time}</p>
                        <p style="margin: 5px 0;"><strong>Clinic:</strong> {clinic_name}</p>
                        <p style="margin: 5px 0;"><strong>Address:</strong> {clinic_address}</p>
                        <p style="margin: 5px 0;"><strong>Type:</strong> {appointment.appointment_type.replace('_', ' ').title() if appointment.appointment_type else 'In Person'}</p>
                    </div>

                    <p>If you need to reschedule or view appointment details, please access your MediBook portal below:</p>
                    <p style="text-align: center;">
                        <a href="{reschedule_url}" class="button" style="color: #ffffff;">Manage Appointment</a>
                    </p>
                </div>
                <div class="footer">
                    <p>This is an automated notification from MediBook AI. Please do not reply directly to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """

        success = _send_email(patient_email, subject, html_content)
        if success:
            # Update appointment reminder status in DB
            if reminder_type == "24h":
                appointment.reminder_sent_24h = True
            elif reminder_type == "1h":
                appointment.reminder_sent_1h = True
            db.commit()
            logger.info(f"Successfully sent {reminder_type} email reminder to {patient_email} for appointment {appointment_id}.")
        return success

    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to send {reminder_type} email reminder for appointment {appointment_id}: {e}")
        return False


def send_doctor_approval_email(doctor_email: str, doctor_name: str) -> bool:
    """
    Send an email notifying the doctor that their registration application has been verified and approved by the clinic administrator.
    """
    try:
        if not doctor_email:
            return False

        raw_name = doctor_name or "Doctor"
        formatted_name = raw_name if raw_name.startswith("Dr.") else f"Dr. {raw_name}"
        login_url = f"{settings.FRONTEND_URL}/login"
        subject = f"🎉 Doctor Application Approved: Welcome to MediBook AI, {formatted_name}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .header {{ background-color: #006B5F; color: #ffffff; padding: 15px; border-radius: 6px 6px 0 0; text-align: center; }}
                .content {{ padding: 20px 0; line-height: 1.6; }}
                .details-box {{ background-color: #f8fafc; border-left: 4px solid #006B5F; padding: 15px; margin: 15px 0; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #006B5F; color: #ffffff; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 15px; }}
                .footer {{ font-size: 12px; color: #6b7280; text-align: center; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 15px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2 style="margin: 0; font-size: 20px;">MediBook AI — Doctor Application Approved</h2>
                </div>
                <div class="content">
                    <p>Dear <strong>{formatted_name}</strong>,</p>
                    <p>Congratulations! Your doctor credentials have been reviewed and approved by clinic administration.</p>
                    <div class="details-box">
                        <p style="margin: 5px 0;"><strong>Status:</strong> Verified & Active Physician</p>
                        <p style="margin: 5px 0;"><strong>Email:</strong> {doctor_email}</p>
                    </div>
                    <p>You can now sign in to your Doctor Clinical Portal to view patient queues, manage consultation schedules, and record clinical notes.</p>
                    <p style="text-align: center;">
                        <a href="{login_url}" class="button" style="color: #ffffff;">Login to Doctor Portal</a>
                    </p>
                </div>
                <div class="footer">
                    <p>This is an automated notification from MediBook AI. Please do not reply directly to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return _send_email(doctor_email, subject, html_content)
    except Exception as e:
        logger.warning(f"Error sending doctor approval email to {doctor_email}: {e}")
        return False
