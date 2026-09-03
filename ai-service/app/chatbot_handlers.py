"""Workflow handlers for NEW_BOOKING, RESCHEDULE, CANCEL, LOOKUP."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from app import backend_client
from app.chatbot_nlu import (
    extract_appointment_id, extract_option_id, is_confirm, is_decline,
    RESCHEDULE_RE, LOOKUP_RE, CANCEL_RE,
)
from app.chatbot_slots import (
    doctors_ui_data,
    fetch_doctor_slots,
    find_doctor_by_id,
    find_slot_by_ts,
    format_appointment_for_ui,
    match_slot_from_text,
    slots_ui_data,
)
from app.chatbot_state import S
from app.schemas import OptionItem
from app.symptom_triage import emergency_alert_with, emergency_explanation, follow_ups_for, is_emergency, triage
from integrations import google_calendar, n8n_webhook, reminders

logger = logging.getLogger("medibook.ai.handlers")

LOGIN_REQ_BOOK = "To confirm this appointment you need to be logged in. Please sign in, then send 'yes' again."
LOGIN_REQ_RESCHEDULE = "To reschedule you need to be logged in. Please sign in, then confirm."
LOGIN_REQ_CANCEL = "Please log in to cancel appointments."
LOGIN_REQ_LOOKUP = "Please log in to view your appointments."

# ── Patient medical history collection ──────────────────────────────────
HISTORY_CONSENT = (
    "\U0001f512 This information will only be shared with your assigned doctor for this appointment."
)
HISTORY_PROMPT = (
    "Would you like to share any relevant medical history for the doctor? "
    "(e.g. existing conditions, allergies, or past similar issues)\n\n"
    "You can skip this by typing \"skip\"."
)

_SKIP_WORDS = frozenset({
    "skip", "no", "nah", "no thanks", "no thank you", "not really",
    "n/a", "none", "pass", "nope", "not needed", "nothing",
    "nahi", "nahi chahiye", "skip karo", "kuch nahi",
})

_CONDITION_TERMS = [
    "diabetes", "diabetic", "blood pressure", "hypertension", "high blood pressure",
    "asthma", "heart disease", "heart condition", "thyroid", "cholesterol",
    "kidney disease", "liver disease", "epilepsy", "arthritis", "cancer",
    "copd", "hepatitis", "hiv", "tuberculosis", "tb",
]
# Captures the full allergy list (including commas) until a sentence
# terminator (period, newline, or end-of-string).  Individual items are
# then split on commas and "and" in post-processing.
_ALLERGY_MARKERS = re.compile(
    r"(?:allergi(?:c|es|y)\s+(?:to\s+)?|allergy\s*:?\s*|intolerant\s+(?:to\s+)?)"
    r"([\w\s,]+?)(?:\.|\n|$)",
    re.IGNORECASE,
)
# Splitter for breaking a captured allergy string into individual items.
# Priority: comma (optionally followed by spaces/and) > standalone "and".
_ALLERGY_SPLIT_RE = re.compile(r",\s*(?:and\s+)?|\s+and\s+", re.IGNORECASE)
_PAST_ISSUE_MARKERS = re.compile(
    r"(?:(?:ha[ds]|previous(?:ly)?|past|history\s+of|prior|last\s+(?:year|month|week)|suffered\s+from|was\s+diagnosed\s+with)\s+)"
    r"([\w\s,]+?)(?:\.|,|\band\b|$)",
    re.IGNORECASE,
)


def _is_history_skip(text: str) -> bool:
    stripped = text.strip().lower()
    return stripped in _SKIP_WORDS or stripped.startswith("skip") or stripped.startswith("no ")


def extract_medical_history(text: str) -> dict[str, Any]:
    """Parse free-text patient input into structured medical history."""
    blob = text.lower()
    conditions: list[str] = [t for t in _CONDITION_TERMS if t in blob]
    # Allergy extraction: capture full list, then split on commas and "and"
    raw_allergy_matches = [
        m.group(1).strip() for m in _ALLERGY_MARKERS.finditer(text) if m.group(1).strip()
    ]
    allergies: list[str] = []
    for raw in raw_allergy_matches:
        parts = _ALLERGY_SPLIT_RE.split(raw)
        allergies.extend(p.strip() for p in parts if p.strip())
    past_issues: list[str] = [m.group(1).strip() for m in _PAST_ISSUE_MARKERS.finditer(text) if m.group(1).strip()]
    # Deduplicate while preserving order
    seen: set[str] = set()
    conditions = [c for c in conditions if not (c in seen or seen.add(c))]
    allergies = [a for a in allergies if not (a.lower() in seen or seen.add(a.lower()))]
    past_issues = [p for p in past_issues if not (p.lower() in seen or seen.add(p.lower()))]
    return {
        "conditions": conditions,
        "allergies": allergies,
        "past_issues": past_issues,
        "raw": text.strip()[:500],
    }


def build_patient_summary(symptoms: str, urgency: str, history: Optional[dict[str, Any]]) -> str:
    """3–5 bullet summary combining symptoms, urgency, and shared history."""
    bullets: list[str] = []
    if symptoms:
        bullets.append(f"\u2022 Current symptoms: {symptoms}")
    bullets.append(f"\u2022 Urgency level: {urgency or 'normal'}")
    if history:
        conds = history.get("conditions") or []
        if conds:
            bullets.append(f"\u2022 Existing conditions: {', '.join(conds)}")
        allerg = history.get("allergies") or []
        if allerg:
            bullets.append(f"\u2022 Known allergies: {', '.join(allerg)}")
        past = history.get("past_issues") or []
        if past:
            bullets.append(f"\u2022 Relevant history: {', '.join(past)}")
    return "\n".join(bullets[:5])


def _history_prompt_message() -> str:
    return f"{HISTORY_CONSENT}\n\n{HISTORY_PROMPT}"


def _proceed_to_show_doctors(session: dict[str, Any]) -> tuple[str, str, list, dict]:
    """Transition from ASKING_HISTORY to SHOWING_DOCTORS, loading doctor slots."""
    try:
        spec = session.get("specialty")
        if not spec:
            docs = backend_client.list_doctors()
            enriched = fetch_doctor_slots(docs, next_days=3)
            session["candidate_doctors"] = enriched
            session["state"] = S.SHOWING_DOCTORS
            if not enriched:
                return "No doctors are available right now. Please try again later.", "waiting_for_doctor_selection", [], {"doctors": []}
            return (
                "Here are the available doctors. Please select one:",
                "waiting_for_doctor_selection",
                [],
                {"doctors": doctors_ui_data(enriched)},
            )
        docs = backend_client.list_doctors(specialization=spec)
        enriched = fetch_doctor_slots(docs, next_days=3)
        session["candidate_doctors"] = enriched
        session["state"] = S.SHOWING_DOCTORS
        if not enriched:
            session["awaiting_specialty_fallback"] = True
            return (
                f"No {spec or 'recommended'} slots are available right now. "
                "Would you like me to check General Medicine instead?",
                "waiting_for_doctor_selection",
                [],
                {"doctors": []},
            )
        msg = f"Based on your symptoms, I recommend seeing a {spec or 'doctor'}. Please select a doctor:"
        return msg, "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(enriched)}
    except Exception as exc:
        logger.error("Failed to load doctors: %s", exc, exc_info=True)
        session["state"] = S.IDLE
        return (
            "I'm sorry, I couldn't load the doctor list right now. Please try again in a moment.",
            "waiting_for_input",
            [],
            {},
        )


def _appointment_time_label(appointment: dict[str, Any]) -> str:
    value = str(appointment.get("appointment_time") or "")
    match = re.search(r"T(\d{2}:\d{2})", value)
    return match.group(1) if match else value


def _select_appointment_from_text(
    text: str,
    appointments: list[dict[str, Any]],
    nlu: dict,
) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    lowered = text.lower()
    ordinal_map = {
        "first": 0, "1st": 0, "second": 1, "2nd": 1,
        "third": 2, "3rd": 2, "fourth": 3, "4th": 3,
    }
    number_match = re.search(r"\b([1-9]\d*)\b", lowered)
    ordinal_match = next((index for word, index in ordinal_map.items() if re.search(rf"\b{re.escape(word)}\b", lowered)), None)
    selected_index = int(number_match.group(1)) - 1 if number_match else ordinal_match
    if selected_index is not None:
        if 0 <= selected_index < len(appointments):
            return appointments[selected_index], []
        return None, []

    doctor_name = str(nlu.get("doctor_name") or "").strip().casefold().removeprefix("dr.").strip()
    doctor_matches = [
        appointment for appointment in appointments
        if doctor_name
        and (
            str(appointment.get("doctor_name") or "Doctor").strip().casefold().removeprefix("dr.").strip() == doctor_name
            or str(appointment.get("patient_name") or "").strip().casefold().removeprefix("dr.").strip() == doctor_name
        )
    ]
    if not doctor_matches:
        if len(appointments) == 1 and "selected appointment" in lowered:
            return appointments[0], []
        return None, []

    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lowered)
    if time_match and len(doctor_matches) > 1:
        hour = int(time_match.group(1))
        minute = time_match.group(2) or "00"
        meridiem = (time_match.group(3) or "").lower()
        if meridiem:
            hour = hour % 12 + (12 if meridiem == "pm" else 0)
        rough_time = f"{hour:02d}:{minute}"
        doctor_matches = [
            appointment for appointment in doctor_matches
            if _appointment_time_label(appointment).endswith(rough_time)
        ]

    if len(doctor_matches) == 1:
        return doctor_matches[0], []
    return None, doctor_matches


def _appointment_selection_message(appointments: list[dict[str, Any]], action: str) -> str:
    lines = [
        f"{index}. {appointment.get('doctor_name') or 'Doctor'} - {_appointment_time_label(appointment)}"
        for index, appointment in enumerate(appointments, start=1)
    ]
    return f"Which appointment would you like to {action}?\n" + "\n".join(lines)


def _booking_error(exc: backend_client.BackendError, is_reschedule: bool = False) -> str:
    c = exc.error_code
    if c == "INVALID_TIME":
        return "That appointment time is not valid. Please pick another available slot."
    if c == "SLOT_UNAVAILABLE":
        return "That time slot is not available. Please pick another time."
    if c == "DOUBLE_BOOKING":
        return "You already have an appointment at that time. Would you like a different slot?"
    if exc.status_code in (401, 403):
        return LOGIN_REQ_RESCHEDULE if is_reschedule else LOGIN_REQ_BOOK
    return exc.message or "I could not complete the request. Please try again."

def _validated_doctor_name(name: Optional[str], doctors: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not name:
        return None
    requested = str(name).strip().casefold().removeprefix("dr.").strip()
    return next(
        (
            doctor for doctor in doctors
            if str(doctor.get("name") or "").strip().casefold().removeprefix("dr.").strip() == requested
        ),
        None,
    )


def _validated_specialty(specialty: Optional[str], doctors: list[dict[str, Any]]) -> Optional[str]:
    if not specialty:
        return None
    requested = str(specialty).strip().casefold()
    for doctor in doctors:
        value = doctor.get("specialization") or doctor.get("specialty")
        if value and str(value).strip().casefold() == requested:
            return str(value)
    return None


def _handle_named_selection(
    session: dict[str, Any],
    nlu: dict,
) -> Optional[tuple[str, str, list, dict]]:
    doctor_name = nlu.get("doctor_name")
    specialty_name = nlu.get("specialty")
    if not doctor_name and not specialty_name:
        return None

    doctors = backend_client.list_doctors()
    if doctor_name:
        doctor = _validated_doctor_name(doctor_name, doctors)
        if not doctor:
            enriched = fetch_doctor_slots(doctors, next_days=3)
            session["candidate_doctors"] = enriched
            session["state"] = S.SHOWING_DOCTORS
            return (
                f"I couldn't find a doctor named '{doctor_name}'. Please select a doctor by clicking one of the cards.",
                "waiting_for_doctor_selection",
                [],
                {"doctors": doctors_ui_data(enriched)},
            )
        enriched = fetch_doctor_slots([doctor], next_days=3)
        if not enriched:
            session["candidate_doctors"] = []
            session["state"] = S.SHOWING_DOCTORS
            return (
                f"No available slots were found for {doctor.get('name') or doctor_name}. Please select a doctor from the cards.",
                "waiting_for_doctor_selection",
                [],
                {"doctors": []},
            )
        selected_doctor = enriched[0]
        session["candidate_doctors"] = enriched
        session["selected_doctor"] = selected_doctor
        session["state"] = S.SHOWING_SLOTS
        return (
            f"You selected {selected_doctor['name']}. Please pick an available time slot:",
            "waiting_for_slot_selection",
            [],
            {"slots": slots_ui_data(selected_doctor)},
        )

    specialty = _validated_specialty(specialty_name, doctors)
    if not specialty:
        enriched = fetch_doctor_slots(doctors, next_days=3)
        session["candidate_doctors"] = enriched
        session["state"] = S.SHOWING_DOCTORS
        return (
            "I couldn't find that specialty. Please select a doctor by clicking one of the cards.",
            "waiting_for_doctor_selection",
            [],
            {"doctors": doctors_ui_data(enriched)},
        )
    specialty_doctors = backend_client.list_doctors(specialization=specialty)
    enriched = fetch_doctor_slots(specialty_doctors, next_days=3)
    session["candidate_doctors"] = enriched
    session["state"] = S.SHOWING_DOCTORS
    if not enriched:
        return (
            f"No {specialty} slots are available right now. Please select a doctor from the cards.",
            "waiting_for_doctor_selection",
            [],
            {"doctors": []},
        )
    return (
        f"Here are the available {specialty} specialists:",
        "waiting_for_doctor_selection",
        [],
        {"doctors": doctors_ui_data(enriched)},
    )

def handle_new_booking(session: dict[str, Any], text: str, nlu: dict, auth: Optional[str]) -> tuple[str, str, list, dict]:
    state = session["state"]

    # Direct "show doctors" request from a non-active state — skip symptom flow
    if state in (S.IDLE, S.FAQ, S.LOOKUP) and (
        nlu.get("wants_doctor_list") or nlu.get("intent") == "show_doctors"
    ):
        spec = session.get("specialty")
        if not spec:
            docs = backend_client.list_doctors()
        else:
            docs = backend_client.list_doctors(specialization=spec)
        enriched = fetch_doctor_slots(docs, next_days=3)
        session["candidate_doctors"] = enriched
        session["state"] = S.SHOWING_DOCTORS
        if not enriched:
            return f"No {spec or 'doctor'} slots are available right now. Please try again later.", "waiting_for_doctor_selection", [], {"doctors": []}
        msg = f"Here are the available {'specialists' if spec else 'doctors'}:"
        return msg, "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(enriched)}

    if state in (S.IDLE, S.FAQ, S.LOOKUP):
        named_selection = _handle_named_selection(session, nlu)
        if named_selection:
            return named_selection
        session["state"] = S.ASKING_SYMPTOMS
        return (
            "Hi! I'm MediBook AI. What brings you in today? Please describe your symptoms.",
            "waiting_for_symptoms",
            [],
            {},
        )

    if state == S.ASKING_SYMPTOMS:
        session["symptoms_text"] = str(nlu.get("symptoms") or text)
        if is_emergency(session["symptoms_text"]):
            session["state"] = S.EMERGENCY
            session["emergency_explanation"] = emergency_explanation(session["symptoms_text"])
            return emergency_alert_with(session["emergency_explanation"]), "emergency_redirect", [], {}
        result = triage(session["symptoms_text"])
        doctors = backend_client.list_doctors()
        requested_specialty = _validated_specialty(nlu.get("specialty"), doctors)
        session["specialty"] = requested_specialty or _validated_specialty(result.specialty, doctors)
        session["urgency_level"] = result.urgency_level
        session["urgency_reason"] = result.reason
        session["follow_ups"] = follow_ups_for(result.specialty)
        session["follow_up_index"] = 0
        session["state"] = S.ASKING_FOLLOWUP
        return f"Thank you. Let me ask a few quick questions:\n{session['follow_ups'][0]}", "waiting_for_input", [], {}

    if state == S.ASKING_FOLLOWUP:
        # ── Intent-switch escape hatch ──────────────────────────────────
        # If the user sends a clearly unrelated request (lookup, reschedule,
        # cancel) while we're collecting follow-up answers, detect and route
        # instead of blindly consuming the message as a symptom answer.
        _intent = nlu.get("intent")
        _is_switch = _intent in ("reschedule", "cancel", "lookup")
        if not _is_switch:
            lower = text.lower()
            if (
                "?" in text
                and any(
                    kw in lower
                    for kw in (
                        "my appointment", "what are my", "show my",
                        "view my", "check my", "cancel my", "reschedule my",
                        "start over", "help",
                    )
                )
            ):
                _is_switch = True
        if _is_switch:
            logger.info(
                "Intent switch '%s' detected during ASKING_FOLLOWUP — "
                "breaking out to route as '%s'",
                text[:80], _intent,
            )
            from app.chatbot import _reset_patient_workflow
            # Infer the correct target intent when NLU says "symptom"/"appointment"
            # but the text clearly indicates a different request
            _target = _intent
            if _target not in ("reschedule", "cancel", "lookup"):
                lower2 = text.lower()
                if any(kw in lower2 for kw in ("my appointment", "show my", "view my", "check my", "what are my")):
                    _target = "lookup"
                elif any(kw in lower2 for kw in ("cancel my", "cancel this")):
                    _target = "cancel"
                elif any(kw in lower2 for kw in ("reschedule my", "change my", "time change")):
                    _target = "reschedule"
                else:
                    _target = "appointment"
            _reset_patient_workflow(session, _target)
            if _target == "lookup":
                return handle_lookup(session, text, nlu, auth)
            if _target == "reschedule":
                return handle_reschedule(session, text, nlu, auth)
            if _target == "cancel":
                return handle_cancel(session, text, nlu, auth)
            session["state"] = S.IDLE
            return handle_new_booking(session, text, nlu, auth)

        session["symptoms_text"] = f"{session.get('symptoms_text', '')} {text}".strip()
        if is_emergency(session["symptoms_text"]):
            session["state"] = S.EMERGENCY
            session["emergency_explanation"] = emergency_explanation(session["symptoms_text"])
            return emergency_alert_with(session["emergency_explanation"]), "emergency_redirect", [], {}
        
        if nlu.get("wants_doctor_list") or nlu.get("intent") == "show_doctors":
            session["state"] = S.ASKING_HISTORY
            return _history_prompt_message(), "waiting_for_input", [], {}

        named_selection = _handle_named_selection(session, nlu)
        if named_selection:
            return named_selection
        
        idx = int(session.get("follow_up_index") or 0) + 1
        session["follow_up_index"] = idx
        fu = session.get("follow_ups") or []
        if idx < min(3, len(fu)):
            return f"Thanks. {fu[idx]}", "waiting_for_input", [], {}
        
        # Transition to optional medical history collection before showing doctors
        session["state"] = S.ASKING_HISTORY
        return _history_prompt_message(), "waiting_for_input", [], {}

    if state == S.ASKING_HISTORY:
        # ── Intent-switch escape hatch (same logic as ASKING_FOLLOWUP) ──
        _intent_h = nlu.get("intent")
        _is_switch_h = _intent_h in ("reschedule", "cancel", "lookup")
        if not _is_switch_h:
            lower_h = text.lower()
            if (
                "?" in text
                and any(
                    kw in lower_h
                    for kw in (
                        "my appointment", "what are my", "show my",
                        "view my", "check my", "cancel my", "reschedule my",
                        "start over", "help",
                    )
                )
            ):
                _is_switch_h = True
        if _is_switch_h:
            logger.info(
                "Intent switch '%s' detected during ASKING_HISTORY — "
                "breaking out to route as '%s'",
                text[:80], _intent_h,
            )
            from app.chatbot import _reset_patient_workflow
            _target_h = _intent_h
            if _target_h not in ("reschedule", "cancel", "lookup"):
                lower_h2 = text.lower()
                if any(kw in lower_h2 for kw in ("my appointment", "show my", "view my", "check my", "what are my")):
                    _target_h = "lookup"
                elif any(kw in lower_h2 for kw in ("cancel my", "cancel this")):
                    _target_h = "cancel"
                elif any(kw in lower_h2 for kw in ("reschedule my", "change my", "time change")):
                    _target_h = "reschedule"
                else:
                    _target_h = "appointment"
            _reset_patient_workflow(session, _target_h)
            if _target_h == "lookup":
                return handle_lookup(session, text, nlu, auth)
            if _target_h == "reschedule":
                return handle_reschedule(session, text, nlu, auth)
            if _target_h == "cancel":
                return handle_cancel(session, text, nlu, auth)
            session["state"] = S.IDLE
            return handle_new_booking(session, text, nlu, auth)

        if _is_history_skip(text):
            session["medical_history"] = None
        else:
            history = extract_medical_history(text)
            session["medical_history"] = history
        return _proceed_to_show_doctors(session)

    if state == S.SHOWING_DOCTORS:
        if session.pop("awaiting_general_fallback", False):
            if is_confirm(text, nlu):
                docs = backend_client.list_doctors()
                enriched = fetch_doctor_slots(docs, next_days=3)
                session["candidate_doctors"] = enriched
                return (
                    "Here are the available doctors. Please select one:",
                    "waiting_for_doctor_selection",
                    [],
                    {"doctors": doctors_ui_data(enriched)},
                )
            session["state"] = S.ASKING_SYMPTOMS
            return (
                "Please describe your symptoms differently so I can recommend the right specialist.",
                "waiting_for_symptoms",
                [],
                {},
            )
        if session.pop("awaiting_specialty_fallback", False):
            if is_confirm(text, nlu):
                fallback_specialty = "General Medicine"
                docs = backend_client.list_doctors(specialization=fallback_specialty)
                enriched = fetch_doctor_slots(docs, next_days=3)
                session["candidate_doctors"] = enriched
                if not enriched:
                    return (
                        f"No {fallback_specialty} slots are available right now. Please try again later.",
                        "waiting_for_doctor_selection",
                        [],
                        {"doctors": []},
                    )
                return (
                    "I found these General Medicine doctors. Please select one:",
                    "waiting_for_doctor_selection",
                    [],
                    {"doctors": doctors_ui_data(enriched)},
                )
            session["awaiting_specialty_fallback"] = True
            return (
                "I will keep your search limited to the recommended specialty. "
                "Please confirm if you would like me to check General Medicine.",
                "waiting_for_doctor_selection",
                [],
                {"doctors": []},
            )

        doc_id = extract_option_id(text, nlu)
        
        if doc_id:
            doc = find_doctor_by_id(doc_id, session.get("candidate_doctors", []))
            if doc:
                session["selected_doctor"] = doc
                session["state"] = S.SHOWING_SLOTS
                try:
                    slot_data = slots_ui_data(doc)
                except Exception as exc:
                    logger.error("Failed to serialize slots for doctor %s: %s", doc.get("doctor_id"), exc, exc_info=True)
                    session["state"] = S.SHOWING_DOCTORS
                    return "I couldn't load available time slots for this doctor. Please try selecting again.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
                return f"You selected {doc['name']}. Please pick an available time slot:", "waiting_for_slot_selection", [], {"slots": slot_data}
        
        doctors = backend_client.list_doctors()
        doctor_name = nlu.get("doctor_name")
        if doctor_name:
            validated_doctor = _validated_doctor_name(doctor_name, doctors)
            candidate_ids = {str(item.get("doctor_id")) for item in session.get("candidate_doctors", [])}
            doctor = next(
                (
                    item for item in session.get("candidate_doctors", [])
                    if validated_doctor
                    and str(item.get("doctor_id")) == str(validated_doctor.get("doctor_id"))
                ),
                None,
            ) if validated_doctor else None
            if doctor and candidate_ids and str(doctor.get("doctor_id")) not in candidate_ids:
                doctor = None
            if doctor:
                session["selected_doctor"] = doctor
                session["state"] = S.SHOWING_SLOTS
                try:
                    slot_data = slots_ui_data(doctor)
                except Exception as exc:
                    logger.error("Failed to serialize slots for doctor %s: %s", doctor.get("doctor_id"), exc, exc_info=True)
                    session["state"] = S.SHOWING_DOCTORS
                    return "I couldn't load available time slots for this doctor. Please try selecting again.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
                return f"You selected {doctor['name']}. Please pick an available time slot:", "waiting_for_slot_selection", [], {"slots": slot_data}
            else:
                return f"I couldn't find a doctor named '{doctor_name}'. Please select a doctor by clicking one of the cards.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
        
        specialty = _validated_specialty(nlu.get("specialty"), doctors)
        if nlu.get("specialty") and not specialty:
            return "I couldn't find that specialty. Please select a doctor by clicking one of the cards.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
        if specialty:
            docs = backend_client.list_doctors(specialization=specialty)
            enriched = fetch_doctor_slots(docs, next_days=3)
            session["candidate_doctors"] = enriched
            session["state"] = S.SHOWING_DOCTORS
            if not enriched:
                return f"No {specialty} slots are available right now. Please try another specialty or select a doctor from the list.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
            return f"Here are the available {specialty} specialists:", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(enriched)}
        
        if nlu.get("wants_doctor_list"):
            docs = backend_client.list_doctors()
            enriched = fetch_doctor_slots(docs, next_days=3)
            session["candidate_doctors"] = enriched
            session["state"] = S.SHOWING_DOCTORS
            if not enriched:
                return "No doctors are available right now. Please try again later.", "waiting_for_doctor_selection", [], {"doctors": []}
            return "Here are all available doctors:", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(enriched)}
        
        if nlu.get("intent") == "symptom":
            session["state"] = S.ASKING_SYMPTOMS
            return "Please describe your symptoms:", "waiting_for_symptoms", [], {}
        
        return "Please select a doctor by clicking one of the cards.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}

    if state == S.SHOWING_SLOTS:
        doc = session.get("selected_doctor")
        if not doc:
            session["state"] = S.SHOWING_DOCTORS
            return "Session error: missing doctor. Please pick a doctor.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
        
        slot_ts = extract_option_id(text, nlu)
        if not slot_ts:
            iso_m = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)?)", text)
            if iso_m:
                slot_ts = iso_m.group(1)
        slot = find_slot_by_ts(slot_ts, doc) if slot_ts else match_slot_from_text(text, doc)
        if not slot:
            return "Please select a time slot from the list.", "waiting_for_slot_selection", [], {"slots": slots_ui_data(doc)}
        
        session["selected_slot"] = slot
        session["selected_timestamp"] = slot["timestamp"]
        session["selected_slot_label"] = slot["label"]
        session["state"] = S.AWAIT_CONFIRM
        
        ui_booking = {
            "doctor": doc,
            "selectedSlot": slot["label"],
            "isConfirmed": False
        }
        return "Perfect! Please confirm your appointment details.", "waiting_for_confirmation", [], {"booking": ui_booking}

    if state == S.AWAIT_CONFIRM:
        if is_decline(text, nlu) or text.lower().strip() == "change":
            session["state"] = S.SHOWING_DOCTORS
            docs = session.get("candidate_doctors", [])
            ids = [d["doctor_id"] for d in docs]
            all_d = backend_client.list_doctors()
            filtered = [d for d in all_d if d["doctor_id"] in ids] if ids else all_d
            enriched = fetch_doctor_slots(filtered)
            session["candidate_doctors"] = enriched
            return "No problem. Let's pick a different doctor or time.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(enriched)}
        
        if is_confirm(text, nlu):
            if not auth or not auth.lower().startswith("bearer "):
                return LOGIN_REQ_BOOK, "waiting_for_login", [], {}
            pat_id = session.get("patient_id")
            if not pat_id:
                return "I need your patient profile. Please log in first.", "waiting_for_login", [], {}
            
            doc = session.get("selected_doctor")
            ts = session.get("selected_timestamp")
            if not doc or not ts:
                session["state"] = S.SHOWING_DOCTORS
                return "Lost selected slot. Please pick again.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
            
            payload = {
                "patient_id": pat_id,
                "doctor_id": doc["doctor_id"],
                "appointment_time": ts,
                "symptoms_reported": (session.get("symptoms_text") or "General")[:500],
                "urgency_level": session.get("urgency_level") or "normal",
                "urgency_reason": session.get("urgency_reason"),
                "appointment_type": "in_person"
            }
            # Attach structured patient history if the patient shared any
            med_history = session.get("medical_history")
            if med_history:
                summary = build_patient_summary(
                    session.get("symptoms_text") or "",
                    session.get("urgency_level") or "normal",
                    med_history,
                )
                payload["patient_history"] = json.dumps(med_history, ensure_ascii=False)
                session["patient_history_summary"] = summary
            try:
                created = backend_client.create_appointment(payload, auth)
            except backend_client.BackendError as e:
                ui_booking = {"doctor": doc, "selectedSlot": session.get("selected_slot_label"), "isConfirmed": False}
                return _booking_error(e), "waiting_for_confirmation", [], {"booking": ui_booking}

            session["appointment_booked"] = created.get("appointment_id") or created.get("id")
            if created.get("patient_id"):
                session["patient_id"] = str(created["patient_id"])
            session["state"] = S.BOOKED
            session["status"] = "completed"
            
            pat_email = session.get("patient_email") or ""
            pat_name = session.get("patient_name") or "Patient"
            if not pat_email and auth:
                try:
                    user_prof = backend_client.get_current_user(auth)
                    if user_prof:
                        pat_email = user_prof.get("email") or ""
                        pat_name = user_prof.get("name") or pat_name
                        session["patient_email"] = pat_email
                        session["patient_name"] = pat_name
                except Exception:
                    pass

            cal_p = {
                "appointment_id": str(session["appointment_booked"]),
                "doctor_name": doc.get("name") or "Doctor",
                "patient_name": pat_name,
                "patient_email": pat_email,
                "clinic_name": doc.get("clinic_name") or "Prime Care Clinic",
                "clinic_address": doc.get("clinic_address") or "Ground Floor, ABC Plaza, Taxila",
                "appointment_time": ts,
                "duration_minutes": 30,
                "symptoms_reported": session.get("symptoms_text", "")
            }

            try:
                cid = google_calendar.create_calendar_event(cal_p)
                if cid:
                    session["google_calendar_event_id"] = cid
            except Exception as e:
                logger.warning(f"Calendar sync failed: {e}")

            try:
                reminders.send_confirmation_email(cal_p)
            except Exception as e:
                logger.warning(f"Direct confirmation email delivery failed: {e}")
                
            try:
                n8n_p = cal_p.copy()
                n8n_p["patient_id"] = pat_id
                n8n_p["doctor_id"] = doc.get("doctor_id")
                n8n_p["clinic_id"] = created.get("clinic_id")
                n8n_p["urgency_level"] = payload.get("urgency_level", "normal")
                n8n_p["google_calendar_event_id"] = session.get("google_calendar_event_id")
                n8n_webhook.dispatch_appointment_created(n8n_p)
            except Exception as e:
                logger.warning(f"N8N sync failed: {e}")

            ui_booking = {
                "doctor": doc,
                "selectedSlot": session.get("selected_slot_label"),
                "isConfirmed": True
            }
            return "Your appointment is confirmed!", "appointment_booked", [], {"booking": ui_booking}

    session["state"] = S.ASKING_SYMPTOMS
    return "Let's start over. What are your symptoms?", "waiting_for_symptoms", [], {}


def handle_lookup(session: dict[str, Any], text: str, nlu: dict, auth: Optional[str]) -> tuple[str, str, list, dict]:
    if not auth or not auth.lower().startswith("bearer "):
        return LOGIN_REQ_LOOKUP, "waiting_for_login", [], {}
    pat_id = session.get("patient_id")
    if not pat_id:
        return LOGIN_REQ_LOOKUP, "waiting_for_login", [], {}
    
    appts = backend_client.fetch_patient_appointments(pat_id, auth)
    session["state"] = S.LOOKUP
    if not appts:
        return "You have no upcoming appointments.", "show_appointments", [], {"appointments": []}
    
    formatted = [format_appointment_for_ui(a) for a in appts]
    return "Here are your upcoming appointments:", "show_appointments", [], {"appointments": formatted}


def handle_cancel(session: dict[str, Any], text: str, nlu: dict, auth: Optional[str]) -> tuple[str, str, list, dict]:
    if not auth or not auth.lower().startswith("bearer "):
        return LOGIN_REQ_CANCEL, "waiting_for_login", [], {}
    pat_id = session.get("patient_id")
    if not pat_id:
        return LOGIN_REQ_CANCEL, "waiting_for_login", [], {}
    
    state = session["state"]
    
    if state not in (S.CANCEL_FETCH, S.CANCEL_PICK, S.CANCEL_CONFIRM):
        appts = backend_client.fetch_patient_appointments(pat_id, auth)
        if not appts:
            session["state"] = S.IDLE
            return "You have no appointments to cancel.", "show_appointments", [], {"appointments": []}
        
        session["patient_appointments"] = appts
        session["state"] = S.CANCEL_PICK
        formatted = [format_appointment_for_ui(a) for a in appts]
        return _appointment_selection_message(appts, "cancel"), "show_appointments", [], {"appointments": formatted}
    
    if state == S.CANCEL_PICK:
        appt_id = extract_option_id(text, nlu) or extract_appointment_id(text, nlu)
        if not appt_id:
            selected, ambiguous = _select_appointment_from_text(text, session.get("patient_appointments", []), nlu)
            if ambiguous:
                times = ", ".join(_appointment_time_label(appointment) for appointment in ambiguous)
                return (
                    f"You have {len(ambiguous)} appointments with {ambiguous[0].get('doctor_name') or 'this doctor'} - which one, {times}?",
                    "show_appointments",
                    [],
                    {"appointments": [format_appointment_for_ui(a) for a in ambiguous]},
                )
            if selected:
                appt_id = str(selected.get("appointment_id") or selected.get("id") or "")
        if not appt_id:
            formatted = [format_appointment_for_ui(a) for a in session.get("patient_appointments", [])]
            return _appointment_selection_message(session.get("patient_appointments", []), "cancel"), "show_appointments", [], {"appointments": formatted}
        
        appt = next((a for a in session.get("patient_appointments", []) if str(a.get("id", "")) == appt_id or str(a.get("appointment_id", "")) == appt_id), None)
        if not appt:
            formatted = [format_appointment_for_ui(a) for a in session.get("patient_appointments", [])]
            return "Invalid selection. Please choose a numbered appointment or name a doctor.", "show_appointments", [], {"appointments": formatted}
        
        session["picked_appointment_id"] = appt_id
        session["state"] = S.CANCEL_CONFIRM
        doc_name = appt.get("doctor_name", "your doctor")
        time_lbl = appt.get("appointment_time", "this time")
        return f"Are you sure you want to cancel your appointment with {doc_name} on {time_lbl}? (Reply Yes/No)", "waiting_for_confirmation", [], {}
    
    if state == S.CANCEL_CONFIRM:
        if is_decline(text, nlu):
            session["state"] = S.IDLE
            return "Okay, I won't cancel it.", "waiting_for_input", [], {}
        
        if is_confirm(text, nlu):
            appt_id = session.get("picked_appointment_id")
            if not appt_id:
                session["state"] = S.IDLE
                return "Lost appointment context. Please start over.", "waiting_for_input", [], {}
            
            try:
                backend_client.cancel_appointment(appt_id, auth)
            except backend_client.BackendError as e:
                return _booking_error(e), "waiting_for_confirmation", [], {}
            
            session["state"] = S.IDLE
            return "✅ Your appointment has been cancelled.", "waiting_for_input", [], {}
        
        return "Please reply Yes to confirm cancellation, or No to keep it.", "waiting_for_confirmation", [], {}

    session["state"] = S.IDLE
    return "Let's start over.", "waiting_for_input", [], {}


def handle_reschedule(session: dict[str, Any], text: str, nlu: dict, auth: Optional[str]) -> tuple[str, str, list, dict]:
    if not auth or not auth.lower().startswith("bearer "):
        return LOGIN_REQ_RESCHEDULE, "waiting_for_login", [], {}
    pat_id = session.get("patient_id")
    if not pat_id:
        return LOGIN_REQ_RESCHEDULE, "waiting_for_login", [], {}
    
    state = session["state"]
    
    if state not in (S.RESCHEDULE_FETCH, S.RESCHEDULE_PICK, S.RESCHEDULE_SLOTS, S.RESCHEDULE_CONFIRM):
        appt_id = extract_appointment_id(text, nlu)
        if appt_id:
            session["picked_appointment_id"] = appt_id
            session["state"] = S.RESCHEDULE_FETCH
        else:
            appts = backend_client.fetch_patient_appointments(pat_id, auth)
            if not appts:
                session["state"] = S.IDLE
                return "You have no appointments to reschedule. Would you like to book a new one?", "waiting_for_input", [], {}
            session["patient_appointments"] = appts
            session["state"] = S.RESCHEDULE_PICK
            state = S.RESCHEDULE_PICK
            formatted = [format_appointment_for_ui(a) for a in appts]
            return _appointment_selection_message(appts, "reschedule"), "show_appointments", [], {"appointments": formatted}

    if state == S.RESCHEDULE_FETCH or state == S.RESCHEDULE_PICK:
        appt_id = session.get("picked_appointment_id")
        if not appt_id:
            appt_id = extract_option_id(text, nlu) or extract_appointment_id(text, nlu)
        if not appt_id:
            selected, ambiguous = _select_appointment_from_text(text, session.get("patient_appointments", []), nlu)
            if ambiguous:
                times = ", ".join(_appointment_time_label(appointment) for appointment in ambiguous)
                return (
                    f"You have {len(ambiguous)} appointments with {ambiguous[0].get('doctor_name') or 'this doctor'} - which one, {times}?",
                    "show_appointments",
                    [],
                    {"appointments": [format_appointment_for_ui(a) for a in ambiguous]},
                )
            if selected:
                appt_id = str(selected.get("appointment_id") or selected.get("id") or "")
        
        if not appt_id:
            formatted = [format_appointment_for_ui(a) for a in session.get("patient_appointments", [])]
            return _appointment_selection_message(session.get("patient_appointments", []), "reschedule"), "show_appointments", [], {"appointments": formatted}
        
        session["picked_appointment_id"] = appt_id
        
        docs = backend_client.list_doctors()
        enriched = fetch_doctor_slots(docs)
        session["candidate_doctors"] = enriched
        session["state"] = S.RESCHEDULE_SLOTS
        
        appt = next((a for a in session.get("patient_appointments", []) if str(a.get("id", "")) == appt_id or str(a.get("appointment_id", "")) == appt_id), None)
        if appt:
            session["previous_slot_label"] = appt.get("appointment_time")
            doc_id = appt.get("doctor_id")
            if doc_id:
                doc = find_doctor_by_id(doc_id, enriched)
                if doc:
                    session["selected_doctor"] = doc
                    return f"When would you like to reschedule your appointment with {doc['name']} to?", "waiting_for_new_time", [], {"slots": slots_ui_data(doc)}
        
        return "Please select a new doctor and time.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(enriched)}

    if state == S.RESCHEDULE_SLOTS:
        slot_ts = extract_option_id(text, nlu)
        if not slot_ts:
            iso_m = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)?)", text)
            if iso_m:
                slot_ts = iso_m.group(1)
        
        doc_id = None
        if not slot_ts:
            doc_id = extract_option_id(text, nlu)
        if doc_id:
            doc = find_doctor_by_id(doc_id, session.get("candidate_doctors", []))
            if doc:
                session["selected_doctor"] = doc
                return f"Select a new time with {doc['name']}:", "waiting_for_new_time", [], {"slots": slots_ui_data(doc)}
            
        doc = session.get("selected_doctor")
        if doc and slot_ts:
            slot = find_slot_by_ts(slot_ts, doc)
        else:
            slot = None
            
        if not slot and doc:
            slot = match_slot_from_text(text, doc)
            
        if not slot:
            if doc:
                return "Please select a time slot.", "waiting_for_new_time", [], {"slots": slots_ui_data(doc)}
            else:
                return "Please select a doctor.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
        
        session["selected_slot"] = slot
        session["selected_timestamp"] = slot["timestamp"]
        session["selected_slot_label"] = slot["label"]
        session["state"] = S.RESCHEDULE_CONFIRM
        
        ui_reschedule = {
            "doctor": doc,
            "oldSlot": session.get("previous_slot_label") or "Previous time",
            "newSlot": slot["label"]
        }
        return "Please confirm your new appointment time.", "waiting_for_reschedule_confirm", [], {"reschedule": ui_reschedule}
        
    if state == S.RESCHEDULE_CONFIRM:
        if is_decline(text, nlu) or text.lower().strip() == "change":
            session["state"] = S.RESCHEDULE_SLOTS
            doc = session.get("selected_doctor")
            if doc:
                enriched = fetch_doctor_slots([doc])
                if enriched: doc = enriched[0]
                session["selected_doctor"] = doc
                return "Let's pick a different time.", "waiting_for_new_time", [], {"slots": slots_ui_data(doc)}
            return "Let's pick a different doctor.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
            
        if is_confirm(text, nlu):
            appt_id = session.get("picked_appointment_id")
            ts = session.get("selected_timestamp")
            if not appt_id or not ts:
                session["state"] = S.IDLE
                return "Lost state. Please start over.", "waiting_for_input", [], {}
            
            try:
                updated = backend_client.reschedule_appointment(appt_id, ts, auth)
            except backend_client.BackendError as e:
                doc = session.get("selected_doctor")
                ui_reschedule = {"doctor": doc, "oldSlot": session.get("previous_slot_label"), "newSlot": session.get("selected_slot_label")}
                return _booking_error(e, is_reschedule=True), "waiting_for_reschedule_confirm", [], {"reschedule": ui_reschedule}
            
            session["state"] = S.IDLE
            
            cal_id = session.get("google_calendar_event_id") or updated.get("google_calendar_event_id")
            if cal_id:
                try:
                    google_calendar.update_calendar_event(cal_id, ts)
                except Exception:
                    pass
            try:
                rm = reminders.calculate_reminder_times(ts) if ts else {}
                n8n_webhook.dispatch_appointment_rescheduled({
                    "appointment_id": appt_id,
                    "patient_id": pat_id,
                    "doctor_id": str(session.get("selected_doctor", {}).get("doctor_id", "")),
                    "new_appointment_time": ts,
                    "previous_appointment_time": session.get("previous_slot_label"),
                    "new_reminder_time_1": rm.get("reminder_time_1"),
                    "new_reminder_time_2": rm.get("reminder_time_2"),
                })
            except Exception:
                pass
            
            return f" Rescheduled successfully to {session.get('selected_slot_label')}!", "reschedule_complete", [], {}

    session["state"] = S.IDLE
    return "Let's start over.", "waiting_for_input", [], {}
