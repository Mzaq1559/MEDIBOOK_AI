"""n8n Webhook Integration for MediBook AI.

Dispatches appointment lifecycle events (created, rescheduled, cancelled)
and reminder triggers to n8n workflows asynchronously and non-blockingly.
Failures are logged and never interrupt chat conversations.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger("medibook.ai.n8n")

TIMEOUT_SECONDS = 5.0

# Event type constants
EVENT_APPOINTMENT_CREATED = "appointment_created"
EVENT_APPOINTMENT_RESCHEDULED = "appointment_rescheduled"
EVENT_APPOINTMENT_CANCELLED = "appointment_cancelled"
EVENT_REMINDER_TRIGGERED = "reminder_triggered"


def _send_sync(url: str, payload: dict[str, Any]) -> bool:
    """Synchronous HTTP POST to the webhook endpoint with safe error handling."""
    if not url:
        logger.info("n8n webhook skipped: N8N_WEBHOOK_URL is not configured")
        return False

    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            res = client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            if res.status_code in (200, 201, 202, 204):
                logger.info(
                    "n8n webhook delivered successfully (event=%s, status=%s)",
                    payload.get("event"),
                    res.status_code,
                )
                return True
            logger.warning(
                "n8n webhook returned unexpected status %s for event %s: %s",
                res.status_code,
                payload.get("event"),
                res.text[:200],
            )
            return False
    except Exception as exc:
        logger.warning(
            "n8n webhook delivery failed for event %s: %s",
            payload.get("event"),
            exc,
        )
        return False


def send_n8n_webhook(
    event_type: str,
    data: dict[str, Any],
    *,
    non_blocking: bool = True,
) -> bool:
    """Send an event payload to the n8n webhook URL.

    If non_blocking is True, dispatches the HTTP request on a background thread
    so chat response latencies are not affected.
    """
    url = settings.N8N_WEBHOOK_URL or f"{settings.N8N_URL.rstrip('/')}/webhook"
    payload = {
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": data,
    }

    if non_blocking:
        thread = threading.Thread(
            target=_send_sync,
            args=(url, payload),
            daemon=True,
            name=f"n8n-webhook-{event_type}",
        )
        thread.start()
        return True

    return _send_sync(url, payload)


def dispatch_appointment_created(
    appointment: dict[str, Any],
    *,
    non_blocking: bool = True,
) -> bool:
    """Dispatch appointment_created event to n8n."""
    payload = {
        "appointment_id": str(appointment.get("appointment_id") or appointment.get("id") or ""),
        "patient_id": str(appointment.get("patient_id") or ""),
        "patient_name": appointment.get("patient_name") or "Patient",
        "doctor_id": str(appointment.get("doctor_id") or ""),
        "doctor_name": appointment.get("doctor_name") or "Doctor",
        "appointment_time": appointment.get("appointment_time"),
        "clinic_id": str(appointment.get("clinic_id") or ""),
        "clinic_name": appointment.get("clinic_name") or "Prime Care Clinic",
        "clinic_address": appointment.get("clinic_address") or "Ground Floor, ABC Plaza, Taxila",
        "symptoms_reported": appointment.get("symptoms_reported") or "",
        "urgency_level": appointment.get("urgency_level") or "normal",
        "reminder_time_1": appointment.get("reminder_time_1"),
        "reminder_time_2": appointment.get("reminder_time_2"),
    }
    return send_n8n_webhook(
        EVENT_APPOINTMENT_CREATED,
        payload,
        non_blocking=non_blocking,
    )


def dispatch_appointment_rescheduled(
    appointment: dict[str, Any],
    *,
    non_blocking: bool = True,
) -> bool:
    """Dispatch appointment_rescheduled event to n8n."""
    payload = {
        "appointment_id": str(appointment.get("appointment_id") or appointment.get("id") or ""),
        "patient_id": str(appointment.get("patient_id") or ""),
        "doctor_id": str(appointment.get("doctor_id") or ""),
        "new_appointment_time": appointment.get("appointment_time") or appointment.get("new_appointment_time"),
        "previous_appointment_time": appointment.get("previous_appointment_time"),
        "new_reminder_time_1": appointment.get("new_reminder_time_1") or appointment.get("reminder_time_1"),
        "new_reminder_time_2": appointment.get("new_reminder_time_2") or appointment.get("reminder_time_2"),
    }
    return send_n8n_webhook(
        EVENT_APPOINTMENT_RESCHEDULED,
        payload,
        non_blocking=non_blocking,
    )


def dispatch_appointment_cancelled(
    appointment: dict[str, Any],
    *,
    non_blocking: bool = True,
) -> bool:
    """Dispatch appointment_cancelled event to n8n."""
    payload = {
        "appointment_id": str(appointment.get("appointment_id") or appointment.get("id") or ""),
        "patient_id": str(appointment.get("patient_id") or ""),
        "doctor_id": str(appointment.get("doctor_id") or ""),
        "reason": appointment.get("reason") or "Patient request",
    }
    return send_n8n_webhook(
        EVENT_APPOINTMENT_CANCELLED,
        payload,
        non_blocking=non_blocking,
    )
