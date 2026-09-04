"""HTTP client for the MediBook backend. JWT is forwarded in-memory per request."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger("medibook.ai.backend")

TIMEOUT = 8.0

# Persistent HTTP client reused across requests (connection pooling)
_http_client = httpx.Client(timeout=TIMEOUT)

# Cache for list_doctors with TTL handling
_doctors_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

# Metric tracking variables
last_http_call_ms = 0.0
last_http_calls_total_ms = 0.0
last_http_call_count = 0

def reset_turn_http_metrics() -> None:
    global last_http_calls_total_ms, last_http_call_count
    # Reset the metrics counters for a new turn
    last_http_calls_total_ms = 0.0
    last_http_call_count = 0

def _record_http(duration_ms: float, label: str) -> None:
    global last_http_call_ms, last_http_calls_total_ms, last_http_call_count
    last_http_call_ms = duration_ms
    last_http_calls_total_ms += duration_ms
    last_http_call_count += 1
    logger.info("[PERF BACKEND HTTP] %s took %.2f ms", label, duration_ms)



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


def list_doctors(specialization: Optional[str] = None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": 50, "is_available": True}
    if specialization:
        params["specialization"] = specialization
    # TTL cache check (60 seconds)
    cache_key = f"list_doctors:{specialization or ''}"
    cached = _doctors_cache.get(cache_key)
    if cached:
        ts, data_cached = cached
        if time.time() - ts < 60:
            return list(data_cached)
    try:
        t0 = time.perf_counter()
        # Use persistent client for connection reuse
        res = _http_client.get(
            f"{settings.backend_base}/doctors",
            params=params,
            headers=_headers(),
        )
        _record_http((time.perf_counter() - t0) * 1000, "GET /doctors")
        if res.status_code >= 400:
            logger.warning("Doctor list request failed with HTTP %s", res.status_code)
            return []
        data = res.json()
        # Store in cache with timestamp
        _doctors_cache[cache_key] = (time.time(), data.get("doctors") or [])
        return list(_doctors_cache[cache_key][1])
    except httpx.HTTPError:
        logger.warning("Doctor list request could not reach backend")
        return []


def get_availability(doctor_id: str, date: str, next_days: int = 3) -> Optional[dict[str, Any]]:
    try:
        t0 = time.perf_counter()
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.get(
                f"{settings.backend_base}/doctors/{doctor_id}/availability",
                params={"date": date, "next_days": next_days},
                headers=_headers(),
            )
        _record_http((time.perf_counter() - t0) * 1000, f"GET /doctors/{doctor_id}/availability")
        if res.status_code >= 400:
            logger.warning("Availability request failed with HTTP %s", res.status_code)
            return None
        return res.json()
    except httpx.HTTPError:
        logger.warning("Availability request could not reach backend")
        return None


def create_appointment(payload: dict[str, Any], authorization: str) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.post(
                f"{settings.backend_base}/appointments",
                json=payload,
                headers=_headers(authorization),
            )
    except httpx.HTTPError:
        raise BackendError(503, "INTERNAL_ERROR", "Could not reach the booking service. Please try again.")
    if res.status_code >= 400:
        raise _parse_error(res)
    return res.json()


def reschedule_appointment(appointment_id: str, appointment_time: str, authorization: str) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.put(
                f"{settings.backend_base}/appointments/{appointment_id}",
                json={"appointment_time": appointment_time},
                headers=_headers(authorization),
            )
    except httpx.HTTPError:
        raise BackendError(503, "INTERNAL_ERROR", "Could not reach the booking service. Please try again.")
    if res.status_code >= 400:
        raise _parse_error(res)
    return res.json()


def fetch_patient_appointments(
    patient_id: str,
    authorization: str,
    status_filter: Optional[str] = "scheduled",
) -> list[dict[str, Any]]:
    """Fetch a patient's appointments. Returns a list of appointment dicts."""
    params: dict[str, Any] = {"patient_id": patient_id, "limit": 20}
    if status_filter:
        params["status"] = status_filter
    try:
        t0 = time.perf_counter()
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.get(
                f"{settings.backend_base}/appointments",
                params=params,
                headers=_headers(authorization),
            )
        _record_http((time.perf_counter() - t0) * 1000, "GET /appointments")
        if res.status_code >= 400:
            logger.warning("Fetch patient appointments failed with HTTP %s", res.status_code)
            return []
        data = res.json()
        return list(data.get("appointments") or [])
    except httpx.HTTPError:
        logger.warning("Fetch patient appointments could not reach backend")
        return []


def search_patient_appointments(
    authorization: str,
    doctor_name: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Search the authenticated patient's appointments with optional filters.

    Calls GET /api/appointments/search.  Patient scoping is enforced by the
    backend via the Authorization JWT — no patient_id is sent as a query param.
    """
    params: dict[str, Any] = {}
    if doctor_name:
        params["doctor_name"] = doctor_name
    if status:
        params["status"] = status
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    try:
        t0 = time.perf_counter()
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.get(
                f"{settings.backend_base}/appointments/search",
                params=params,
                headers=_headers(authorization),
            )
        _record_http((time.perf_counter() - t0) * 1000, "GET /appointments/search")
        if res.status_code >= 400:
            logger.warning("Search patient appointments failed with HTTP %s", res.status_code)
            return []
        data = res.json()
        return list(data.get("appointments") or [])
    except httpx.HTTPError:
        logger.warning("Search patient appointments could not reach backend")
        return []


def cancel_appointment(appointment_id: str, authorization: str) -> dict[str, Any]:
    """Cancel an appointment via DELETE /api/appointments/{id}."""
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.delete(
                f"{settings.backend_base}/appointments/{appointment_id}",
                headers=_headers(authorization),
            )
    except httpx.HTTPError:
        raise BackendError(503, "INTERNAL_ERROR", "Could not reach the booking service. Please try again.")
    if res.status_code >= 400:
        raise _parse_error(res)
    return res.json()


def get_patient_info(patient_id: str, authorization: str) -> Optional[dict[str, Any]]:
    """Fetch a patient profile via GET /api/patients/{id}."""
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            res = client.get(
                f"{settings.backend_base}/patients/{patient_id}",
                headers=_headers(authorization),
            )
        if res.status_code >= 400:
            logger.warning("Get patient info failed with HTTP %s", res.status_code)
            return None
        data = res.json()
        return data if isinstance(data, dict) else None
    except httpx.HTTPError:
        logger.warning("Get patient info could not reach backend")
        return None
