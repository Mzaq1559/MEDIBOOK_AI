"""Doctor-only chat flow for appointment management and lookup."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from app import backend_client
from app.chatbot_handlers import _appointment_selection_message, _appointment_time_label, _select_appointment_from_text, build_patient_summary
from app.chatbot_nlu import classify
from app.chatbot_slots import fetch_doctor_slots, find_slot_by_ts, format_appointment_for_ui, match_slot_from_text, slots_ui_data
from app.chatbot_state import S

logger = logging.getLogger("medibook.ai.chatbot_doctor")


def _doctor_name_from_context(doctor_context: dict[str, Any]) -> str:
    name = doctor_context.get("name") or doctor_context.get("doctor_name") or "Doctor"
    return str(name)


def _extract_date_filter(message: str) -> Optional[str]:
    lower = message.lower()
    if "today" in lower:
        return "today"
    if "tomorrow" in lower:
        return "tomorrow"
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", message)
    if match:
        return match.group(1)
    return None


def _match_appointment_by_patient(
    appointments: list[dict[str, Any]],
    text: str,
    nlu_patient_name: Optional[str] = None,
) -> list[dict[str, Any]]:
    # Use \w+ (Unicode word chars) to support both Latin and Urdu script names
    tokens = {token.lower() for token in re.findall(r"\w+", text) if len(token) > 2}
    
    # Add NLU-classified patient name tokens (supports Urdu script, Roman Urdu, etc.)
    if nlu_patient_name:
        nlu_tokens = {token.lower() for token in re.findall(r"\w+", nlu_patient_name) if len(token) > 2}
        tokens.update(nlu_tokens)
    
    matches: list[dict[str, Any]] = []
    for appointment in appointments:
        patient_name = str(appointment.get("patient_name") or appointment.get("patient") or "")
        patient_tokens = {token.lower() for token in re.findall(r"\w+", patient_name) if len(token) > 2}
        if patient_tokens and (patient_tokens & tokens):
            matches.append(appointment)
    return matches


def _extract_appointment_time(message: str) -> Optional[str]:
    match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)?)", message)
    if match:
        return match.group(1)
    return None


def _extract_selected_appointment_id(message: str) -> Optional[str]:
    match = re.search(r"\b([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b", message)
    if match:
        return match.group(1)
    return None


def _match_reschedule_slot(message: str, doctor: dict[str, Any]) -> Optional[dict[str, Any]]:
    lowered = message.lower()
    number_match = re.fullmatch(r"\s*(?:slot\s*)?([1-9]\d*)\s*", lowered)
    if number_match:
        index = int(number_match.group(1)) - 1
        slots = doctor.get("slots") or []
        if 0 <= index < len(slots):
            return slots[index]

    timestamp = _extract_appointment_time(message)
    if timestamp:
        return find_slot_by_ts(timestamp, doctor)
    matched = match_slot_from_text(message, doctor)
    if matched:
        return matched

    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", lowered)
    if not time_match:
        return None
    requested = (
        int(time_match.group(1)),
        int(time_match.group(2) or "00"),
        time_match.group(3),
    )
    for slot in doctor.get("slots") or []:
        slot_time = str(slot.get("time") or slot.get("label") or "").lower()
        slot_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", slot_time)
        if slot_match and requested == (
            int(slot_match.group(1)),
            int(slot_match.group(2) or "00"),
            slot_match.group(3),
        ):
            return slot
    return None


def _reschedule_slots_message(patient_name: str, slots: list[dict[str, Any]]) -> str:
    lines = [f"{index}. {slot.get('label') or slot.get('time') or 'Available slot'}" for index, slot in enumerate(slots, start=1)]
    return (
        f"When would you like to reschedule {patient_name}'s appointment? "
        "Please choose an available slot or tell me the time.\n" + "\n".join(lines)
    )


def _reschedule_error_message(error: backend_client.BackendError) -> str:
    if error.error_code == "SLOT_UNAVAILABLE":
        return "That time slot is not available. Please choose another available slot."
    if error.error_code == "INVALID_TIME":
        return "That appointment time is not valid. Please choose another available slot."
    if error.status_code == 409:
        return error.message or "That time cannot be used. Please choose another available slot."
    return error.message or "I could not reschedule that appointment. Please try again."


def _doctor_show_appointments(doctor_id: str, authorization: str, message: str, session: dict[str, Any]) -> dict[str, Any]:
    appointments = backend_client.fetch_doctor_appointments(doctor_id, authorization)
    session["doctor_appointments"] = appointments
    session["last_doctor_action"] = "lookup"
    if not appointments:
        return {"bot_message": "You have no appointments.", "next_action": "doctor_appointments", "ui_data": {"appointments": []}}
    formatted = [format_appointment_for_ui(a) for a in appointments]
    return {
        "bot_message": "Here are your appointments:\n" + "\n".join(
            f"{idx}. {a.get('patient_name') or 'Patient'} — {a.get('appointment_time') or ''} — {a.get('symptoms_reported') or 'No symptoms provided'}"
            for idx, a in enumerate(appointments[:10], start=1)
        ),
        "next_action": "doctor_appointments",
        "ui_data": {"appointments": formatted},
    }


def _doctor_patient_details(
    doctor_id: str,
    authorization: str,
    message: str,
    session: dict[str, Any],
    nlu: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    appointments = session.get("doctor_appointments") or backend_client.fetch_doctor_appointments(doctor_id, authorization)
    if not appointments:
        return {"bot_message": "You have no appointments to review.", "next_action": "doctor_appointment_details", "ui_data": {"appointments": []}}
    
    # Use NLU-classified patient name (or doctor_name as fallback) for matching
    nlu_patient_name = None
    if nlu:
        nlu_patient_name = nlu.get("patient_name") or nlu.get("doctor_name")
    
    matches = _match_appointment_by_patient(appointments, message, nlu_patient_name=nlu_patient_name)
    if len(matches) == 1:
        appointment = matches[0]
        detail = backend_client.get_appointment_details(str(appointment.get("appointment_id") or appointment.get("id") or ""), authorization) or appointment
        # Build the base detail message
        bot_lines = [
            f"Appointment for {detail.get('patient_name') or 'Patient'} on {detail.get('appointment_time') or 'the scheduled time'}:",
            f"Symptoms: {detail.get('symptoms_reported') or 'Not provided'}",
            f"Urgency: {detail.get('urgency_level') or 'normal'}",
        ]
        # Append patient medical history summary if present (doctor-only)
        raw_history = detail.get("patient_history")
        if raw_history:
            try:
                history = json.loads(raw_history) if isinstance(raw_history, str) else raw_history
                summary = build_patient_summary(
                    detail.get("symptoms_reported") or "",
                    detail.get("urgency_level") or "normal",
                    history,
                )
                bot_lines.append("")
                bot_lines.append("\U0001f4cb Patient Medical Summary:")
                bot_lines.append(summary)
            except (json.JSONDecodeError, TypeError):
                pass
        bot_lines.append(f"Notes: {detail.get('notes') or 'No notes'}")
        return {
            "bot_message": "\n".join(bot_lines),
            "next_action": "doctor_appointment_details",
            "ui_data": {"appointment": detail},
        }
    if len(matches) > 1:
        return {
            "bot_message": "I found multiple matches. Please pick one:\n" + "\n".join(
                f"{idx + 1}. {a.get('patient_name') or 'Patient'} — {a.get('appointment_time') or ''}"
                for idx, a in enumerate(matches[:5])
            ),
            "next_action": "doctor_appointment_details",
            "ui_data": {"appointments": [format_appointment_for_ui(a) for a in matches]},
        }
    return {
        "bot_message": "I couldn't match that patient in your appointment list. Please tell me the patient name or choose from your appointments.",
        "next_action": "doctor_appointment_details",
        "ui_data": {"appointments": [format_appointment_for_ui(a) for a in appointments]},
    }


def _resolve_doctor_selection(session: dict[str, Any], appointments: list[dict[str, Any]], message: str, nlu: Optional[dict[str, Any]] = None) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    selected_id = _extract_selected_appointment_id(message) or session.get("doctor_selected_appointment_id")
    if selected_id:
        selected = next(
            (a for a in appointments if str(a.get("appointment_id") or a.get("id") or "") == str(selected_id)),
            None,
        )
        if selected:
            session["doctor_selected_appointment_id"] = str(selected.get("appointment_id") or selected.get("id") or "")
            return selected, []

    lowered = message.lower()
    if not selected_id and len(appointments) == 1 and "selected appointment" in lowered:
        selected = appointments[0]
        session["doctor_selected_appointment_id"] = str(selected.get("appointment_id") or selected.get("id") or "")
        return selected, []

    selected, ambiguous = _select_appointment_from_text(message, appointments, nlu or {})
    if selected:
        session["doctor_selected_appointment_id"] = str(selected.get("appointment_id") or selected.get("id") or "")
    elif session.get("doctor_selected_appointment_id"):
        session["doctor_selected_appointment_id"] = str(session.get("doctor_selected_appointment_id"))
    return selected, ambiguous


def _doctor_reschedule(doctor_id: str, authorization: str, message: str, session: dict[str, Any], doctor_name: str) -> dict[str, Any]:
    appointments = session.get("doctor_appointments") or backend_client.fetch_doctor_appointments(doctor_id, authorization)
    if not appointments:
        return {"bot_message": "You have no appointments to reschedule.", "next_action": "doctor_reschedule", "ui_data": {"appointments": []}}

    selected, ambiguous = _resolve_doctor_selection(session, appointments, message)
    if ambiguous:
        return {
            "bot_message": f"I found multiple appointments for {doctor_name}. Which one should I reschedule? " + ", ".join(_appointment_time_label(a) for a in ambiguous),
            "next_action": "doctor_reschedule",
            "ui_data": {"appointments": [format_appointment_for_ui(a) for a in ambiguous]},
        }
    if not selected:
        return {
            "bot_message": _appointment_selection_message(appointments, "reschedule"),
            "next_action": "doctor_reschedule",
            "ui_data": {"appointments": [format_appointment_for_ui(a) for a in appointments]},
        }
    selected_doctor = None
    appointment_doctor_id = str(selected.get("doctor_id") or "")
    doctors = backend_client.list_doctors()
    if appointment_doctor_id:
        selected_doctor = next(
            (doctor for doctor in doctors if str(doctor.get("doctor_id") or "") == appointment_doctor_id),
            None,
        )
    if selected_doctor:
        available_doctors = fetch_doctor_slots([selected_doctor])
        if available_doctors:
            selected_doctor = available_doctors[0]
            session["doctor_reschedule_slots"] = selected_doctor.get("slots") or []
            new_slot = _match_reschedule_slot(message, selected_doctor)
            if new_slot:
                new_time = str(new_slot.get("timestamp") or "")
            else:
                new_time = None
            if not new_time:
                slots = selected_doctor.get("slots") or []
                return {
                    "bot_message": _reschedule_slots_message(selected.get("patient_name") or "this patient", slots),
                    "next_action": "doctor_reschedule",
                    "ui_data": {"appointment": selected, "slots": slots_ui_data(selected_doctor)},
                }
        else:
            new_time = None
    else:
        new_time = _extract_appointment_time(message)

    if not new_time:
        return {
            "bot_message": f"I couldn't load available slots for {selected.get('patient_name') or 'this patient'}'s appointment. Please try again later.",
            "next_action": "doctor_reschedule",
            "ui_data": {"appointment": selected},
        }
    try:
        result = backend_client.reschedule_appointment(str(selected.get("appointment_id") or selected.get("id") or ""), new_time, authorization)
    except backend_client.BackendError as error:
        return {
            "bot_message": _reschedule_error_message(error),
            "next_action": "doctor_reschedule",
            "ui_data": {"appointment": selected},
        }
    session["doctor_selected_appointment_id"] = None
    session["last_doctor_action"] = "reschedule"
    return {
        "bot_message": f"✅ Rescheduled {selected.get('patient_name') or 'Patient'}'s appointment to {new_time}.",
        "next_action": "doctor_reschedule",
        "ui_data": {"appointment": result},
    }


def _doctor_cancel(doctor_id: str, authorization: str, message: str, session: dict[str, Any], doctor_name: str) -> dict[str, Any]:
    appointments = session.get("doctor_appointments") or backend_client.fetch_doctor_appointments(doctor_id, authorization)
    if not appointments:
        return {"bot_message": "You have no appointments to cancel.", "next_action": "doctor_cancel", "ui_data": {"appointments": []}}

    selected, ambiguous = _resolve_doctor_selection(session, appointments, message)
    if ambiguous:
        return {
            "bot_message": f"I found more than one appointment for {doctor_name}. Which one should I cancel? " + ", ".join(_appointment_time_label(a) for a in ambiguous),
            "next_action": "doctor_cancel",
            "ui_data": {"appointments": [format_appointment_for_ui(a) for a in ambiguous]},
        }
    if not selected:
        return {
            "bot_message": _appointment_selection_message(appointments, "cancel"),
            "next_action": "doctor_cancel",
            "ui_data": {"appointments": [format_appointment_for_ui(a) for a in appointments]},
        }
    result = backend_client.cancel_appointment(str(selected.get("appointment_id") or selected.get("id") or ""), authorization)
    session["doctor_selected_appointment_id"] = None
    session["last_doctor_action"] = "cancel"
    return {
        "bot_message": f"✅ Cancelled {selected.get('patient_name') or 'Patient'}'s appointment.",
        "next_action": "doctor_cancel",
        "ui_data": {"appointment": result},
    }


def handle_doctor_message(
    *,
    session: dict[str, Any],
    message: str,
    authorization: Optional[str],
    doctor_context: dict[str, Any],
) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return {"bot_message": "Unable to load your doctor profile — please contact support", "next_action": "doctor_profile_error", "ui_data": {}}

    doctor_id = str(doctor_context.get("doctor_id") or "")
    if not doctor_id:
        return {"bot_message": "Unable to load your doctor profile — please contact support", "next_action": "doctor_profile_error", "ui_data": {}}

    doctor_name = _doctor_name_from_context(doctor_context)
    lower = message.lower()

    # NLU classification for intent detection (supports English, Roman Urdu, Urdu script)
    nlu = classify(message, session.get("messages") or [], session.get("state") or S.IDLE)
    intent = nlu.get("intent") or ""

    # Pending selection handling — fires for ANY appointment selection,
    # not only after cancel/reschedule.  When the doctor clicks an
    # appointment card from the "Show my appointments" list (without a
    # preceding cancel/reschedule), last_action is None; we route to
    # patient details as a sensible default.
    last_action = session.get("last_doctor_action")
    selected_id = _extract_selected_appointment_id(message)
    has_pending_doctor_selection = bool(
        selected_id or session.get("doctor_selected_appointment_id") or "selected appointment" in lower or _extract_appointment_time(message)
    )
    logger.warning(
        "DOCTOR_STATE_DEBUG last_action=%s selected_id=%s pending_selected=%s has_pending=%s lower=%r session_keys=%s",
        last_action,
        selected_id,
        session.get("doctor_selected_appointment_id"),
        has_pending_doctor_selection,
        lower,
        sorted(session.keys()),
    )
    if has_pending_doctor_selection:
        if last_action == "cancel":
            return _doctor_cancel(doctor_id, authorization, message, session, doctor_name)
        if last_action == "reschedule":
            return _doctor_reschedule(doctor_id, authorization, message, session, doctor_name)
        # No pending action context — show the appointment details
        return _doctor_patient_details(doctor_id, authorization, message, session, nlu=nlu)

    # Route based on NLU intent
    if intent == "reschedule":
        session["last_doctor_action"] = "reschedule"
        return _doctor_reschedule(doctor_id, authorization, message, session, doctor_name)

    if intent == "cancel":
        session["last_doctor_action"] = "cancel"
        return _doctor_cancel(doctor_id, authorization, message, session, doctor_name)

    if intent == "patient_details":
        return _doctor_patient_details(doctor_id, authorization, message, session, nlu=nlu)

    if intent == "lookup":
        return _doctor_show_appointments(doctor_id, authorization, message, session)

    if intent == "appointment":
        return {"bot_message": "This assistant is for doctor schedule management. Booking a new patient appointment is not supported here. Please use your dashboard to manage scheduling.", "next_action": "doctor_unsupported", "ui_data": {}}

    return {"bot_message": "This assistant is for doctor schedule management. Please ask to show your appointments, view a patient detail, reschedule, or cancel an appointment.", "next_action": "doctor_unsupported", "ui_data": {}}
