import os
import logging
from uuid import UUID
from datetime import timedelta
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment
from app.services.email_service import _doctor_display_name

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']


def get_calendar_service():
    """Initialize Google Calendar API client using Service Account credentials."""
    credentials_path = settings.GOOGLE_CALENDAR_SERVICE_ACCOUNT_PATH

    # Search comprehensive relative, container, and fallback paths
    alt_paths = [
        credentials_path,
        '/app/credentials.json',
        '/app/google-calendar-credentials.json',
        'credentials.json',
        'google-calendar-credentials.json',
        './credentials.json',
        './google-calendar-credentials.json',
        'backend/credentials.json',
        'backend/google-calendar-credentials.json',
        '../credentials.json',
        '../google-calendar-credentials.json',
    ]

    found_path = None
    for path in alt_paths:
        if path and os.path.exists(path) and os.path.isfile(path):
            found_path = path
            break

    if not found_path:
        logger.warning(f"Google Calendar credentials file not found at: {credentials_path}")
        return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            found_path, scopes=SCOPES
        )
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        logger.warning(f"Failed to authenticate Google Calendar service account from {found_path}: {e}")
        return None


def sync_appointment(appointment_id: UUID, db: Session) -> bool:
    """
    Sync an appointment with Google Calendar.
    Returns True on success, False on failure without raising exceptions.
    """
    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            logger.warning(f"Appointment {appointment_id} not found for Google Calendar sync.")
            return False

        if appointment.google_calendar_event_id:
            # Already synced
            return True

        service = get_calendar_service()
        if not service:
            logger.warning(f"Skipping Google Calendar sync for appointment {appointment_id}: Service unavailable.")
            return False

        calendar_id = getattr(settings, 'GOOGLE_CALENDAR_ID', 'primary') or 'primary'
        doctor_name = _doctor_display_name(
            appointment.doctor.user.name if (appointment.doctor and appointment.doctor.user) else "Doctor"
        )
        patient_name = appointment.patient.user.name if (appointment.patient and appointment.patient.user) else "Patient"
        patient_email = appointment.patient.user.email if (appointment.patient and appointment.patient.user) else None
        doctor_email = appointment.doctor.user.email if (appointment.doctor and appointment.doctor.user) else None
        clinic_name = appointment.clinic.name if appointment.clinic else "MediBook Clinic"
        clinic_tz = appointment.clinic.timezone if (appointment.clinic and appointment.clinic.timezone) else settings.TIMEZONE

        start_dt = appointment.appointment_time
        duration = appointment.duration_minutes or 30
        end_dt = start_dt + timedelta(minutes=duration)

        event_payload = {
            'summary': f"Appointment with {doctor_name} ({clinic_name})",
            'description': (
                f"Patient: {patient_name}" + (f" ({patient_email})" if patient_email else "") + "\n"
                f"Doctor: {doctor_name}" + (f" ({doctor_email})" if doctor_email else "") + "\n"
                f"Clinic: {clinic_name}\n"
                f"Symptoms: {appointment.symptoms_reported or 'N/A'}\n"
                f"Urgency: {appointment.urgency_level or 'normal'}\n"
                f"Type: {appointment.appointment_type or 'in_person'}\n"
                f"Appointment ID: {appointment.id}"
            ),
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'UTC',
            },
        }

        try:
            created_event = service.events().insert(calendarId=calendar_id, body=event_payload).execute()
        except Exception as insert_err:
            if calendar_id != 'primary':
                logger.info(f"Retrying Google Calendar insert with primary calendar (original failed: {insert_err})")
                created_event = service.events().insert(calendarId='primary', body=event_payload).execute()
            else:
                raise insert_err

        event_id = created_event.get('id')

        if event_id:
            appointment.google_calendar_event_id = event_id
            db.commit()
            logger.info(f"Successfully synced appointment {appointment_id} to Google Calendar. Event ID: {event_id}")
            return True
        else:
            logger.warning(f"Google Calendar API created event for appointment {appointment_id} but returned no ID.")
            return False

    except Exception as e:
        db.rollback()
        logger.warning(f"Error syncing appointment {appointment_id} to Google Calendar: {e}")
        return False


def update_calendar_appointment(appointment_id: UUID, db: Session) -> bool:
    """Update event time in Google Calendar when appointment is rescheduled."""
    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment or not appointment.google_calendar_event_id:
            return False

        service = get_calendar_service()
        if not service:
            return False

        calendar_id = getattr(settings, 'GOOGLE_CALENDAR_ID', 'primary') or 'primary'
        clinic_tz = appointment.clinic.timezone if (appointment.clinic and appointment.clinic.timezone) else settings.TIMEZONE
        start_dt = appointment.appointment_time
        duration = appointment.duration_minutes or 30
        end_dt = start_dt + timedelta(minutes=duration)

        patch_payload = {
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': clinic_tz,
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': clinic_tz,
            },
        }

        try:
            service.events().patch(
                calendarId=calendar_id,
                eventId=appointment.google_calendar_event_id,
                body=patch_payload
            ).execute()
        except Exception as patch_err:
            if calendar_id != 'primary':
                service.events().patch(
                    calendarId='primary',
                    eventId=appointment.google_calendar_event_id,
                    body=patch_payload
                ).execute()
            else:
                raise patch_err

        logger.info(f"Successfully updated Google Calendar event {appointment.google_calendar_event_id} for appointment {appointment_id}.")
        return True
    except Exception as e:
        logger.warning(f"Error updating Google Calendar event for appointment {appointment_id}: {e}")
        return False


def cancel_calendar_appointment(appointment_id: UUID, db: Session) -> bool:
    """Delete/cancel event in Google Calendar when appointment is cancelled."""
    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment or not appointment.google_calendar_event_id:
            return False

        service = get_calendar_service()
        if not service:
            return False

        calendar_id = getattr(settings, 'GOOGLE_CALENDAR_ID', 'primary') or 'primary'
        try:
            service.events().delete(
                calendarId=calendar_id,
                eventId=appointment.google_calendar_event_id
            ).execute()
        except Exception as del_err:
            if calendar_id != 'primary':
                service.events().delete(
                    calendarId='primary',
                    eventId=appointment.google_calendar_event_id
                ).execute()
            else:
                raise del_err

        logger.info(f"Successfully deleted Google Calendar event {appointment.google_calendar_event_id} for appointment {appointment_id}.")
        return True
    except Exception as e:
        logger.warning(f"Error deleting Google Calendar event for appointment {appointment_id}: {e}")
        return False
