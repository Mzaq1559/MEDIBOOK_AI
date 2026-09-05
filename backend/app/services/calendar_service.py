import os
import logging
from uuid import UUID
from datetime import timedelta
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']


def get_calendar_service():
    """Initialize Google Calendar API client using Service Account credentials."""
    credentials_path = settings.GOOGLE_CALENDAR_SERVICE_ACCOUNT_PATH

    # Fall back to alternative relative paths if specified path doesn't exist
    if not os.path.exists(credentials_path):
        alt_paths = ['credentials.json', 'backend/credentials.json', './credentials.json']
        found_path = None
        for path in alt_paths:
            if os.path.exists(path):
                found_path = path
                break
        if found_path:
            credentials_path = found_path
        else:
            logger.warning(f"Google Calendar credentials file not found at: {credentials_path}")
            return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        logger.warning(f"Failed to authenticate Google Calendar service account: {e}")
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

        doctor_name = appointment.doctor.user.name if (appointment.doctor and appointment.doctor.user) else "Doctor"
        patient_name = appointment.patient.user.name if (appointment.patient and appointment.patient.user) else "Patient"
        patient_email = appointment.patient.user.email if (appointment.patient and appointment.patient.user) else None
        doctor_email = appointment.doctor.user.email if (appointment.doctor and appointment.doctor.user) else None
        clinic_name = appointment.clinic.name if appointment.clinic else "MediBook Clinic"
        clinic_tz = appointment.clinic.timezone if (appointment.clinic and appointment.clinic.timezone) else settings.TIMEZONE

        start_dt = appointment.appointment_time
        duration = appointment.duration_minutes or 30
        end_dt = start_dt + timedelta(minutes=duration)

        # Note: attendees removed - service accounts cannot invite attendees
        # without Domain-Wide Delegation of Authority
        event_payload = {
            'summary': f"Appointment with Dr. {doctor_name} ({clinic_name})",
            'description': (
                f"Patient: {patient_name}\n"
                f"Symptoms: {appointment.symptoms_reported or 'N/A'}\n"
                f"Urgency: {appointment.urgency_level or 'normal'}\n"
                f"Type: {appointment.appointment_type or 'in_person'}"
            ),
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': clinic_tz,
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': clinic_tz,
            },
        }

        created_event = service.events().insert(calendarId='primary', body=event_payload).execute()
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
