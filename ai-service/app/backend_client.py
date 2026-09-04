"""HTTP client for the MediBook backend. JWT is forwarded in-memory per request."""

from __future__ import annotations

import logging
_status_emitter: Callable[[str], None] | None = None

def set_status_emitter(emitter: Callable[[str], None] | None) -> None:
    """Set the status emitter for the current request."""
    global _status_emitter
    _status_emitter = emitter

def _emit_status(message: str) -> None:
    """Emit a status message if an emitter is configured."""
    if _status_emitter:
        try:
            _status_emitter(message)
        except Exception as e:
            logger.debug("Status emitter raised exception: %s", e)

import httpx

from app.config import settings

logger = logging.getLogger("medibook.ai.backend")

# Global status emitter callable, set per request
_status_emitter: Callable[[str], None] | None = None

def set_status_emitter(emitter: Callable[[str], None] | None) -> None:
    """Set the status emitter for the current request.
    The emitter should accept a single string message describing the current operation.
    """
    global _status_emitter
    _status_emitter = emitter

def _emit_status(message: str) -> None:
    """Emit a status message if an emitter is configured."""
    if _status_emitter:
        try:
            _status_emitter(message)
        except Exception as e:
            logger.debug("Status emitter raised exception: %s", e)


TIMEOUT = 8.0


class BackendError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


def _parse_error(response: httpx.Response) -> BackendError:
    error_code = "INTERNAL_ERROR"
    message = "Backend request failed"
    try:
        body = response.json()
        if isinstance(body, dict):
            error_code = str(body.get("error_code") or error_code)
            message = str(body.get("message") or message)
            detail = body.get("detail")
            if isinstance(detail, dict):
                error_code = str(detail.get("error_code") or error_code)
                message = str(detail.get("message") or message)
    except Exception:
        message = f"Backend returned HTTP {response.status_code}"
    return BackendError(response.status_code, error_code, message)


def _headers(authorization: Optional[str] = None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if authorization:
        headers["Authorization"] = authorization
    return headers


def get_current_user(authorization: str) -> Optional[dict[str, Any]]:
    """Fetch current user profile via GET /api/auth/me."""
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.get(
                f"{settings.backend_base}/auth/me",
                headers=_headers(authorization),
            )
        if res.status_code == 200:
            return res.json()
        return None
    except Exception:
        return None


def get_patient_profile(patient_or_user_id: str, authorization: str) -> Optional[dict[str, Any]]:
    """Resolve a user ID or patient ID to the canonical patient profile."""
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.get(
                f"{settings.backend_base}/patients/{patient_or_user_id}",
                headers=_headers(authorization),
            )
        if res.status_code == 200:
            return res.json()
        logger.warning("Patient profile lookup failed with HTTP %s", res.status_code)
        return None
    except httpx.HTTPError:
        logger.warning("Patient profile lookup could not reach backend")
        return None


def list_doctors(specialization: Optional[str] = None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": 50, "is_available": True}
    if specialization:
        params["specialization"] = specialization
def list_doctors(specialization: Optional[str] = None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": 50, "is_available": True}
    if specialization:
        params["specialization"] = specialization
    try:
        _emit_status("Fetching list of doctors…")
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.get(
                f"{settings.backend_base}/doctors",
                params=params,
                headers=_headers(),
            )
        if res.status_code >= 400:
            logger.warning("Doctor list request failed with HTTP %s", res.status_code)
            return []
        data = res.json()
        return list(data.get("doctors") or [])
    except httpx.HTTPError:
        logger.warning("Doctor list request could not reach backend")
        return []


def get_availability(doctor_id: str, date: str, next_days: int = 3) -> Optional[dict[str, Any]]:
    try:
    _emit_status(f"Checking availability for doctor {doctor_id} on {date}…")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.get(
                f"{settings.backend_base}/doctors/{doctor_id}/availability",
                params={"date": date, "next_days": next_days},
                headers=_headers(),
            )
    except httpx.HTTPError:
        logger.warning("Availability request could not reach backend")
        return None
        if res.status_code >= 400:
            logger.warning("Availability request failed with HTTP %s", res.status_code)
            return None
        return res.json()
    except httpx.HTTPError:
        logger.warning("Availability request could not reach backend")
        return None


def create_appointment(payload: dict[str, Any], authorization: str) -> dict[str, Any]:
    try:
    _emit_status("Creating new appointment…")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.post(
                f"{settings.backend_base}/appointments",
                json=payload,
                headers=_headers(authorization),
            )
    except httpx.HTTPError:
        raise BackendError(503, "INTERNAL_ERROR", "Could not reach the booking service. Please try again.")
    except httpx.HTTPError:
        raise BackendError(503, "INTERNAL_ERROR", "Could not reach the booking service. Please try again.")
    if res.status_code >= 400:
        raise _parse_error(res)
    return res.json()


def reschedule_appointment(appointment_id: str, appointment_time: str, authorization: str) -> dict[str, Any]:
    try:
    _emit_status("Rescheduling appointment…")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.put(
                f"{settings.backend_base}/appointments/{appointment_id}",
                json={"appointment_time": appointment_time},
                headers=_headers(authorization),
            )
    except httpx.HTTPError:
        raise BackendError(503, "INTERNAL_ERROR", "Could not reach the booking service. Please try again.")
    except httpx.HTTPError:
        raise BackendError(503, "INTERNAL_ERROR", "Could not reach the booking service. Please try again.")
    if res.status_code >= 400:
        raise _parse_error(res)
    return res.json()


def fetch_patient_appointments(
    patient_id: str,
    authorization: str,
    status_filter: str = "scheduled",
) -> list[dict[str, Any]]:
    """Fetch a patient's appointments. Returns a list of appointment dicts."""
    params: dict[str, Any] = {"patient_id": patient_id, "limit": 20}
    if status_filter:
        params["status"] = status_filter
    try:
    _emit_status("Fetching patient appointments…")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.get(
                f"{settings.backend_base}/appointments",
                params=params,
                headers=_headers(authorization),
            )
    except httpx.HTTPError:
        logger.warning("Fetch patient appointments could not reach backend")
        return []
        if res.status_code >= 400:
            logger.warning("Fetch patient appointments failed with HTTP %s", res.status_code)
            return []
        data = res.json()
        return list(data.get("appointments") or [])
    except httpx.HTTPError:
        logger.warning("Fetch patient appointments could not reach backend")
        return []


def fetch_doctor_appointments(
    doctor_id: str,
    authorization: str,
    date: Optional[str] = None,
    status_filter: str = "scheduled",
) -> list[dict[str, Any]]:
    """Fetch a doctor's appointments using the shared appointments endpoint."""
    params: dict[str, Any] = {"doctor_id": doctor_id, "limit": 20}
    if status_filter:
        params["status"] = status_filter
    if date:
        params["date"] = date
    try:
    _emit_status("Fetching doctor appointments…")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.get(
                f"{settings.backend_base}/appointments",
                params=params,
                headers=_headers(authorization),
            )
    except httpx.HTTPError:
        logger.warning("Fetch doctor appointments could not reach backend")
        return []
        if res.status_code >= 400:
            logger.warning("Fetch doctor appointments failed with HTTP %s", res.status_code)
            return []
        data = res.json()
        return list(data.get("appointments") or [])
    except httpx.HTTPError:
        logger.warning("Fetch doctor appointments could not reach backend")
        return []


def get_appointment_details(appointment_id: str, authorization: str) -> Optional[dict[str, Any]]:
    """Fetch a single appointment's full details."""
    try:
    _emit_status(f"Getting details for appointment {appointment_id}…")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.get(
                f"{settings.backend_base}/appointments/{appointment_id}",
                headers=_headers(authorization),
            )
    except httpx.HTTPError:
        logger.warning("Get appointment details could not reach backend")
        return None
        if res.status_code >= 400:
            logger.warning("Get appointment details failed with HTTP %s", res.status_code)
            return None
        return res.json()
    except httpx.HTTPError:
        logger.warning("Get appointment details could not reach backend")
        return None


def cancel_appointment(appointment_id: str, authorization: str) -> dict[str, Any]:
    """Cancel an appointment via DELETE /api/appointments/{id}."""
    try:
    _emit_status(f"Cancelling appointment {appointment_id}…")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.delete(
                f"{settings.backend_base}/appointments/{appointment_id}",
                headers=_headers(authorization),
            )
    except httpx.HTTPError:
        raise BackendError(503, "INTERNAL_ERROR", "Could not reach the booking service. Please try again.")
    except httpx.HTTPError:
        raise BackendError(503, "INTERNAL_ERROR", "Could not reach the booking service. Please try again.")
    if res.status_code >= 400:
        raise _parse_error(res)
    return res.json()
