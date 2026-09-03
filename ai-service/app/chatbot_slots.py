"""Slot and doctor availability helpers shared across workflows."""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app import backend_client

logger = logging.getLogger("medibook.ai.slots")

try:
    KARACHI = ZoneInfo("Asia/Karachi")
except Exception:
    from datetime import timedelta
    KARACHI = timezone(timedelta(hours=5))  # type: ignore[assignment]


def today_karachi() -> str:
    return datetime.now(KARACHI).date().isoformat()


def fetch_doctor_slots(doctors: list[dict[str, Any]], next_days: int = 3) -> list[dict[str, Any]]:
    """For each doctor fetch availability; return enriched list with .slots key."""
    start = today_karachi()
    result = []
    for d in doctors:
        doctor_id = str(d.get("doctor_id") or "")
        if not doctor_id:
            continue
        avail = backend_client.get_availability(doctor_id, start, next_days=next_days)
        free: list[dict[str, Any]] = []
        if avail:
            for day in avail.get("availability") or []:
                date_label = day.get("date", "")
                for slot in day.get("slots") or []:
                    if slot.get("available"):
                        free.append({
                            "date": date_label,
                            "time": slot.get("time", ""),
                            "timestamp": slot.get("timestamp", ""),
                            "label": f"{date_label} at {slot.get('time', '')}",
                        })
                    if len(free) >= 6:
                        break
                if len(free) >= 6:
                    break
        if not free:
            continue  # skip doctors with no availability
        entry = {
            "doctor_id": doctor_id,
            "name": d.get("name") or "Doctor",
            "specialization": d.get("specialization") or "",
            "consultation_fee": d.get("consultation_fee"),
            "rating": d.get("rating") or 0.0,
            "clinic_name": d.get("clinic_name") or "Prime Care Clinic",
            "clinic_address": d.get("clinic_address") or "Ground Floor, ABC Plaza, Taxila",
            "slots": free,
        }
        result.append(entry)
    return result


def doctors_ui_data(enriched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Serialize enriched doctor list for the frontend ui_data.doctors payload."""
    result = []
    for d in enriched:
        doc_id = d.get("doctor_id")
        if not doc_id:
            logger.warning("Skipping malformed doctor entry (missing doctor_id)")
            continue
        result.append({
            "doctor_id": doc_id,
            "name": d.get("name") or "Doctor",
            "specialization": d.get("specialization") or "",
            "rating": d.get("rating") or 0.0,
            "consultation_fee": d.get("consultation_fee") or 0,
            "clinic_name": d.get("clinic_name") or "Prime Care Clinic",
            "clinic_address": d.get("clinic_address") or "",
        })
    return result


def slots_ui_data(doctor: dict[str, Any]) -> list[dict[str, Any]]:
    """Serialize slot list for the frontend ui_data.slots payload."""
    result = []
    for s in doctor.get("slots") or []:
        time_val = s.get("time")
        date_val = s.get("date")
        ts_val = s.get("timestamp")
        if not time_val or not ts_val:
            logger.warning("Skipping malformed slot entry: %s", s)
            continue
        result.append({
            "time": time_val,
            "date": date_val or "",
            "timestamp": ts_val,
            "label": s.get("label") or f"{date_val or ''} at {time_val}",
        })
    return result


def find_doctor_by_id(doctor_id: str, candidates: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    for c in candidates:
        if str(c.get("doctor_id", "")).lower() == doctor_id.lower():
            return c
    return None


def find_slot_by_ts(timestamp: str, doctor: dict[str, Any]) -> Optional[dict[str, Any]]:
    for s in doctor.get("slots") or []:
        if s.get("timestamp") == timestamp:
            return s
    return None


def match_slot_from_text(text: str, doctor: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Try to find a slot by parsing time from free text."""
    time_pats = re.findall(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", text, re.I)
    for raw in time_pats:
        norm = raw.lower().replace(" ", "")
        for s in doctor.get("slots") or []:
            t = (s.get("time") or "").lower().replace(" ", "")
            if norm in t or t in norm:
                return s
    return None


def format_appointment_for_ui(appt: dict[str, Any]) -> dict[str, Any]:
    return {
        "appointment_id": str(appt.get("appointment_id") or appt.get("id") or ""),
        "doctor_name": appt.get("doctor_name") or "Doctor",
        "doctor_specialization": appt.get("doctor_specialization") or appt.get("specialization") or "",
        "appointment_time": appt.get("appointment_time") or "",
        "status": appt.get("status") or "scheduled",
        "clinic_name": appt.get("clinic_name") or "Prime Care Clinic",
        "symptoms_reported": appt.get("symptoms_reported") or "",
    }
