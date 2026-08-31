"""Load patient name, history, and language for receptionist-style prompts."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import Any, Optional

from app import backend_client

logger = logging.getLogger("medibook.ai.patient_context")


def first_name(full_name: Optional[str]) -> str:
    """Return a natural first name from 'Ali Khan' or 'Khan, Ali'."""
    raw = (full_name or "").strip()
    if not raw:
        return ""
    if "," in raw:
        after = raw.split(",", 1)[1].strip()
        if after:
            return after.split()[0]
        return raw.split(",", 1)[0].strip().split()[0]
    return raw.split()[0]


def _parse_when(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _ordinal_day(day: int) -> str:
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def format_visit_when(value: Any) -> str:
    """Conversational date/time, e.g. August 27th at 10 AM."""
    dt = _parse_when(value)
    if not dt:
        return str(value or "").strip()
    hour = dt.strftime("%I").lstrip("0") or "0"
    minute = dt.minute
    ampm = dt.strftime("%p").lstrip("0") or dt.strftime("%p")
    time_part = f"{hour}:{dt.strftime('%M')} {ampm}" if minute else f"{hour} {ampm}"
    month = dt.strftime("%B")
    return f"{month} {_ordinal_day(dt.day)} at {time_part}"


def _appt_sort_key(appt: dict[str, Any]) -> datetime:
    return _parse_when(appt.get("appointment_time")) or datetime.min.replace(tzinfo=None)


def _doctor_name(appt: dict[str, Any]) -> str:
    return str(appt.get("doctor_name") or appt.get("doctor") or "your doctor")


def _symptoms(appt: dict[str, Any]) -> str:
    return str(
        appt.get("symptoms_reported")
        or appt.get("symptoms")
        or appt.get("reason")
        or ""
    ).strip()


def _clinic(appt: dict[str, Any]) -> str:
    return str(appt.get("clinic_name") or "").strip()


def summarize_appointments(appts: list[dict[str, Any]], limit: int = 3) -> list[dict[str, str]]:
    ordered = sorted(appts, key=_appt_sort_key, reverse=True)
    out: list[dict[str, str]] = []
    for appt in ordered[:limit]:
        out.append(
            {
                "date": format_visit_when(appt.get("appointment_time")),
                "doctor": _doctor_name(appt),
                "symptoms": _symptoms(appt) or "not recorded",
                "clinic": _clinic(appt),
                "status": str(appt.get("status") or ""),
            }
        )
    return out


def preferred_from_history(appts: list[dict[str, Any]]) -> tuple[str, str]:
    doctors = [_doctor_name(a) for a in appts if _doctor_name(a)]
    clinics = [_clinic(a) for a in appts if _clinic(a)]
    doctor = Counter(doctors).most_common(1)[0][0] if doctors else ""
    clinic = Counter(clinics).most_common(1)[0][0] if clinics else ""
    return doctor, clinic


def _list_text(values: Any) -> str:
    if not values:
        return "none noted"
    if isinstance(values, str):
        return values.strip() or "none noted"
    items = [str(v).strip() for v in values if str(v).strip()]
    return ", ".join(items) if items else "none noted"


def format_conversation_history(messages: list[Any], limit: int = 8) -> str:
    recent = list(messages or [])[-limit:]
    if not recent:
        return "(new conversation)"
    lines: list[str] = []
    for item in recent:
        role = getattr(item, "role", None) or (item.get("role") if isinstance(item, dict) else "user")
        text = getattr(item, "message", None)
        if text is None and isinstance(item, dict):
            text = item.get("message") or item.get("content") or ""
        snippet = " ".join(str(text or "").split())
        if len(snippet) > 180:
            snippet = snippet[:177] + "..."
        lines.append(f"- {role}: {snippet}")
    return "\n".join(lines)


def build_patient_context_block(
    *,
    full_name: str,
    given_name: str,
    last_visits: list[dict[str, str]],
    chronic_conditions: Any,
    allergies: Any,
    preferred_doctor: str,
    preferred_clinic: str,
    language: str,
    conversation_history: str,
    special_notes: str = "",
) -> str:
    last = last_visits[0] if last_visits else None
    history_lines = []
    if last:
        history_lines.append(
            f"- Last visit: {last['date']} with {last['doctor']}"
        )
        history_lines.append(f"- Symptoms: {last.get('symptoms') or 'not recorded'}")
    else:
        history_lines.append("- Last visit: none on file")
        history_lines.append("- Symptoms: none on file")
    if len(last_visits) > 1:
        extras = "; ".join(
            f"{v['date']} with {v['doctor']} ({v.get('symptoms') or 'n/a'})"
            for v in last_visits[1:]
        )
        history_lines.append(f"- Earlier visits: {extras}")
    history_lines.append(f"- Chronic conditions: {_list_text(chronic_conditions)}")
    history_lines.append(f"- Allergies / special notes: {_list_text(allergies)}")
    if special_notes:
        history_lines.append(f"- Notes: {special_notes}")

    display_name = given_name or full_name or "the patient"
    lines = [
        f"Patient: {full_name or display_name}",
        f"First name: {display_name}",
        f"Language preference: {language or 'english'}",
        f"Preferred doctor: {preferred_doctor or 'none noted'}",
        f"Preferred clinic: {preferred_clinic or 'none noted'}",
        "Medical History:",
        *history_lines,
        "",
        "Current conversation:",
        conversation_history or "(new conversation)",
    ]
    return "\n".join(lines)


def load_patient_context(
    session: dict[str, Any],
    authorization: Optional[str],
    language: str,
) -> str:
    """Fetch profile + recent visits and return a system-prompt context block."""
    patient_id = session.get("patient_id")
    if not patient_id:
        return ""
    if not authorization or not str(authorization).lower().startswith("bearer "):
        return ""

    facts = session.get("patient_context_facts")
    if isinstance(facts, dict) and facts:
        return build_patient_context_block(
            full_name=str(facts.get("full_name") or ""),
            given_name=str(facts.get("given_name") or ""),
            last_visits=list(facts.get("last_visits") or []),
            chronic_conditions=facts.get("chronic_conditions") or [],
            allergies=facts.get("allergies") or [],
            preferred_doctor=str(facts.get("preferred_doctor") or ""),
            preferred_clinic=str(facts.get("preferred_clinic") or ""),
            language=language,
            conversation_history=format_conversation_history(session.get("messages") or []),
            special_notes=str(facts.get("special_notes") or ""),
        )

    info: dict[str, Any] = {}
    try:
        info = backend_client.get_patient_info(str(patient_id), authorization) or {}
    except Exception as exc:
        logger.warning("Patient profile fetch failed: %s", exc)
        info = {}

    appts: list[dict[str, Any]] = []
    try:
        appts = backend_client.fetch_patient_appointments(
            str(patient_id), authorization, status_filter=""
        )
    except Exception as exc:
        logger.warning("Patient appointment history fetch failed: %s", exc)
        appts = []

    full_name = str(info.get("name") or "").strip()
    given = first_name(full_name)
    last_visits = summarize_appointments(appts, limit=3)
    pref_doc, pref_clinic = preferred_from_history(appts)
    conditions = info.get("medical_conditions") or info.get("medical_history") or []
    allergies = info.get("allergies") or []
    notes = str(info.get("notes") or info.get("special_notes") or "").strip()

    facts = {
        "full_name": full_name,
        "given_name": given,
        "last_visits": last_visits,
        "chronic_conditions": conditions,
        "allergies": allergies,
        "preferred_doctor": pref_doc,
        "preferred_clinic": pref_clinic,
        "special_notes": notes,
    }
    if info or appts:
        session["patient_context_facts"] = facts
        session["patient_first_name"] = given
    return build_patient_context_block(
        full_name=full_name,
        given_name=given,
        last_visits=last_visits,
        chronic_conditions=conditions,
        allergies=allergies,
        preferred_doctor=pref_doc,
        preferred_clinic=pref_clinic,
        language=language,
        conversation_history=format_conversation_history(session.get("messages") or []),
        special_notes=notes,
    )
