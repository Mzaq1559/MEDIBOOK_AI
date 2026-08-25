import smtplib
import logging
from uuid import UUID
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment

logger = logging.getLogger(__name__)


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
        doctor_name = appointment.doctor.user.name if (appointment.doctor and appointment.doctor.user) else "Doctor"
        clinic_name = appointment.clinic.name if appointment.clinic else "MediBook Clinic"
        clinic_address = appointment.clinic.address if appointment.clinic else "Clinic Address"

        if not patient_email:
            logger.warning(f"No patient email found for appointment {appointment_id}. Skipping email reminder.")
            return False

        formatted_time = appointment.appointment_time.strftime("%A, %B %d, %Y at %I:%M %p")
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

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_USERNAME or "noreply@primecare.pk"
        msg["To"] = patient_email
        msg.attach(MIMEText(html_content, "html"))

        if not settings.SMTP_SERVER or not settings.SMTP_PASSWORD:
            logger.warning(f"SMTP credentials missing or incomplete. Skipping email delivery for appointment {appointment_id}.")
            return False

        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=10)
        try:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        finally:
            server.quit()

        # Update appointment reminder status in DB
        if reminder_type == "24h":
            appointment.reminder_sent_24h = True
        elif reminder_type == "1h":
            appointment.reminder_sent_1h = True
        db.commit()

        logger.info(f"Successfully sent {reminder_type} email reminder to {patient_email} for appointment {appointment_id}.")
        return True

    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to send {reminder_type} email reminder for appointment {appointment_id}: {e}")
        return False
