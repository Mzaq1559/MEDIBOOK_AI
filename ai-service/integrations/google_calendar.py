"""Google Calendar API v3 integration for MediBook AI.

Handles event creation, update (rescheduling), and cancellation using Google Service Account
authentication (GOOGLE_CALENDAR_CREDENTIALS_PATH) or API key/secret fallback.
Designed to be fail-safe: missing or invalid credentials will log a warning
and skip calendar sync without interrupting the appointment flow.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
from dateutil import parser as date_parser

try:
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request as GoogleAuthRequest
except ImportError:
    service_account = None
    GoogleAuthRequest = None

from app.config import settings

logger = logging.getLogger("medibook.ai.google_calendar")

CALENDAR_BASE_URL = "https://www.googleapis.com/calendar/v3/calendars"
TIMEOUT_SECONDS = 6.0
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar",
]


def _resolve_credentials_path() -> Optional[Path]:
    """Find and validate the service account credentials JSON file."""
    if not settings.GOOGLE_CALENDAR_CREDENTIALS_PATH:
        return None
    p = Path(settings.GOOGLE_CALENDAR_CREDENTIALS_PATH)
    if p.is_file():
        return p
    # Try resolving relative to ai-service root
    base_dir = Path(__file__).resolve().parent.parent
    candidate = base_dir / settings.GOOGLE_CALENDAR_CREDENTIALS_PATH
    if candidate.is_file():
        return candidate
    # Try resolving relative to project root
    candidate_root = base_dir.parent / settings.GOOGLE_CALENDAR_CREDENTIALS_PATH
    if candidate_root.is_file():
        return candidate_root
    return None


def _get_service_account_token() -> Optional[str]:
    """Generate an OAuth2 access token from service account credentials."""
    creds_path = _resolve_credentials_path()
    if not creds_path or service_account is None:
        return None
    try:
        creds = service_account.Credentials.from_service_account_file(
            str(creds_path),
            scopes=SCOPES,
        )
        auth_req = GoogleAuthRequest() if GoogleAuthRequest else None
        creds.refresh(auth_req)
        return creds.token
    except Exception as exc:
        logger.warning(
            "Failed to obtain Google service account access token from %s: %s",
            creds_path,
            exc,
        )
        return None


def _is_configured() -> bool:
    """Check if Google Calendar integration credentials are provided."""
    if _resolve_credentials_path() is not None:
        return True
    return bool(settings.GOOGLE_CALENDAR_API_KEY or settings.GOOGLE_CALENDAR_SECRET)


def _get_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    token = _get_service_account_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif settings.GOOGLE_CALENDAR_SECRET:
        headers["Authorization"] = f"Bearer {settings.GOOGLE_CALENDAR_SECRET}"
    return headers


def _compute_end_time(start_time_iso: str, duration_minutes: int = 30) -> str:
    """Parse start ISO time and compute end time in ISO 8601 format."""
    try:
        start_dt = date_parser.parse(start_time_iso)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        return end_dt.isoformat()
    except Exception:
        return start_time_iso


def create_calendar_event(appointment: dict[str, Any]) -> Optional[str]:
    """Create a Google Calendar event for an appointment.

    Returns the Google Calendar event ID if successful, or None if skipped/failed.
    Never raises an exception into the caller.
    """
    if not _is_configured():
        logger.info(
            "Google Calendar sync skipped: GOOGLE_CALENDAR_API_KEY / credentials not configured"
        )
        return None

    calendar_id = settings.GOOGLE_CALENDAR_ID or "primary"
    doctor_name = appointment.get("doctor_name") or "Doctor"
    patient_name = appointment.get("patient_name") or "Patient"
    clinic_name = appointment.get("clinic_name") or "Prime Care Clinic"
    clinic_address = appointment.get("clinic_address") or "Ground Floor, ABC Plaza, Taxila"
    start_time = appointment.get("appointment_time")
    duration = int(appointment.get("duration_minutes") or 30)
    symptoms = appointment.get("symptoms_reported") or "General Consultation"
    appt_id = appointment.get("appointment_id") or appointment.get("id") or ""

    if not start_time:
        logger.warning("Google Calendar event creation skipped: missing appointment_time")
        return None

    end_time = _compute_end_time(start_time, duration)

    event_payload = {
        "summary": f"MediBook: Dr. {doctor_name} with {patient_name}",
        "location": f"{clinic_name}, {clinic_address}",
        "description": (
            f"MediBook AI Appointment\n"
            f"Appointment ID: {appt_id}\n"
            f"Doctor: Dr. {doctor_name}\n"
            f"Patient: {patient_name}\n"
            f"Symptoms / Reason: {symptoms}\n"
            f"Clinic: {clinic_name}\n"
            f"Address: {clinic_address}"
        ),
        "start": {
            "dateTime": start_time,
            "timeZone": "Asia/Karachi",
        },
        "end": {
            "dateTime": end_time,
            "timeZone": "Asia/Karachi",
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},  # 24 hours before
                {"method": "popup", "minutes": 60},        # 1 hour before
            ],
        },
    }

    url = f"{CALENDAR_BASE_URL}/{calendar_id}/events"
    params: dict[str, Any] = {}
    if settings.GOOGLE_CALENDAR_API_KEY:
        params["key"] = settings.GOOGLE_CALENDAR_API_KEY

    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            res = client.post(
                url,
                json=event_payload,
                params=params,
                headers=_get_headers(),
            )
            if res.status_code in (200, 201):
                event_data = res.json()
                event_id = event_data.get("id")
                logger.info("Successfully created Google Calendar event: %s", event_id)
                return str(event_id) if event_id else None
            logger.warning(
                "Google Calendar API returned status %s: %s",
                res.status_code,
                res.text[:200],
            )
            return None
    except Exception as exc:
        logger.warning("Google Calendar event creation failed: %s", exc)
        return None


def update_calendar_event(
    event_id: str,
    new_appointment_time: str,
    duration_minutes: int = 30,
) -> bool:
    """Update date/time of an existing Google Calendar event.

    Returns True if successfully updated, False otherwise.
    Never raises an exception into the caller.
    """
    if not event_id or not _is_configured():
        logger.info(
            "Google Calendar update skipped (event_id=%s, configured=%s)",
            event_id,
            _is_configured(),
        )
        return False

    calendar_id = settings.GOOGLE_CALENDAR_ID or "primary"
    end_time = _compute_end_time(new_appointment_time, duration_minutes)

    patch_payload = {
        "start": {
            "dateTime": new_appointment_time,
            "timeZone": "Asia/Karachi",
        },
        "end": {
            "dateTime": end_time,
            "timeZone": "Asia/Karachi",
        },
    }

    url = f"{CALENDAR_BASE_URL}/{calendar_id}/events/{event_id}"
    params: dict[str, Any] = {}
    if settings.GOOGLE_CALENDAR_API_KEY:
        params["key"] = settings.GOOGLE_CALENDAR_API_KEY

    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            res = client.patch(
                url,
                json=patch_payload,
                params=params,
                headers=_get_headers(),
            )
            if res.status_code in (200, 201):
                logger.info("Successfully updated Google Calendar event: %s", event_id)
                return True
            logger.warning(
                "Google Calendar update returned status %s: %s",
                res.status_code,
                res.text[:200],
            )
            return False
    except Exception as exc:
        logger.warning("Google Calendar update failed for event %s: %s", event_id, exc)
        return False


def delete_calendar_event(event_id: str) -> bool:
    """Cancel / delete an existing Google Calendar event.

    Returns True if successfully cancelled/deleted, False otherwise.
    Never raises an exception into the caller.
    """
    if not event_id or not _is_configured():
        logger.info(
            "Google Calendar cancellation skipped (event_id=%s, configured=%s)",
            event_id,
            _is_configured(),
        )
        return False

    calendar_id = settings.GOOGLE_CALENDAR_ID or "primary"
    url = f"{CALENDAR_BASE_URL}/{calendar_id}/events/{event_id}"
    params: dict[str, Any] = {}
    if settings.GOOGLE_CALENDAR_API_KEY:
        params["key"] = settings.GOOGLE_CALENDAR_API_KEY

    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            res = client.delete(
                url,
                params=params,
                headers=_get_headers(),
            )
            if res.status_code in (200, 204):
                logger.info("Successfully deleted Google Calendar event: %s", event_id)
                return True
            logger.warning(
                "Google Calendar delete returned status %s: %s",
                res.status_code,
                res.text[:200],
            )
            return False
    except Exception as exc:
        logger.warning("Google Calendar delete failed for event %s: %s", event_id, exc)
        return False
