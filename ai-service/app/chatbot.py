"""Conversation manager: intent, entities, booking/reschedule/FAQ/triage flows."""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser

from app import backend_client, groq_client
from app.config import settings
from app.schemas import MessageItem, OptionItem
from app.symptom_triage import (
    EMERGENCY_ALERT,
    follow_ups_for,
    is_emergency,
    triage,
)
from integrations import google_calendar, n8n_webhook, reminders

logger = logging.getLogger("medibook.ai.chatbot")

try:
    KARACHI = ZoneInfo("Asia/Karachi")
except Exception:
    KARACHI = timezone(timedelta(hours=5))

INTENTS = ("appointment", "symptom", "faq", "reschedule")

SESSION_TTL_SECONDS = 2 * 60 * 60  # 2 hours
_sessions: dict[str, dict[str, Any]] = {}

LOGIN_REQUIRED_BOOK = (
    "To confirm this appointment you need to be logged in. "
    "Please sign in, then send \"yes\" again to complete the booking."
)
LOGIN_REQUIRED_RESCHEDULE = (
    "To reschedule this appointment you need to be logged in. "
    "Please sign in, then confirm the new time again."
)
MISSING_PATIENT_ID = (
    "I can hold this booking, but I still need your patient profile. "
    "Please send the message again after logging in as a patient so I can attach the appointment to your account."
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_karachi() -> str:
    return datetime.now(KARACHI).date().isoformat()


def _cleanup_expired_sessions() -> None:
    """Evict sessions that have not been updated within SESSION_TTL_SECONDS."""
    now = time.time()
    expired = [
        conv_id
        for conv_id, s in _sessions.items()
        if now - float(s.get("last_accessed", 0)) > SESSION_TTL_SECONDS
    ]
    for conv_id in expired:
        _sessions.pop(conv_id, None)


def get_session(conversation_id: str) -> Optional[dict[str, Any]]:
    _cleanup_expired_sessions()
    session = _sessions.get(conversation_id)
    if session:
        session["last_accessed"] = time.time()
    return session


def _trim_history(messages: list[MessageItem]) -> list[MessageItem]:
    limit = max(2, int(settings.CONVERSATION_MAX_HISTORY))
    if len(messages) <= limit:
        return messages
    return messages[-limit:]


def _new_session(conversation_id: str, patient_id: Optional[str]) -> dict[str, Any]:
    now = utc_now_iso()
    session = {
        "conversation_id": conversation_id,
        "patient_id": patient_id,
        "messages": [],
        "created_at": now,
        "updated_at": now,
        "last_accessed": time.time(),
        "status": "ongoing",
        "appointment_booked": None,
        "state": "idle",
        "symptoms_text": "",
        "follow_up_index": 0,
        "follow_ups": [],
        "specialty": None,
        "urgency_level": "normal",
        "candidate_doctors": [],
        "selected_doctor": None,
        "selected_slot_label": None,
        "selected_timestamp": None,
        "reschedule_appointment_id": None,
        "last_intent": None,
    }
    _sessions[conversation_id] = session
    return session


def _append(session: dict[str, Any], role: str, text: str) -> None:
    session["messages"].append(
        MessageItem(role=role, message=text, timestamp=utc_now_iso())
    )
    session["messages"] = _trim_history(session["messages"])
    session["updated_at"] = utc_now_iso()
    session["last_accessed"] = time.time()



NLU_SYSTEM = """You are NLU for MediBook AI, a clinic virtual receptionist in Pakistan.
Classify the latest user message in English or Roman Urdu / Urdu.

Return JSON only:
{
  "intent": "appointment" | "symptom" | "faq" | "reschedule",
  "doctor_name": string or null,
  "date": string or null,
  "symptoms": string or null,
  "appointment_id": string or null,
  "confirms": boolean,
  "declines": boolean,
  "faq_topic": "hours" | "fees" | "other" | null
}

Rules:
- intent appointment: user wants to book or continue booking (e.g. "I want an appointment", "doctor se milna hai", "appointment leni hai", "booking karni hai").
- intent symptom: user describes health symptoms/concerns (e.g. "chest pain", "seene mein dard hai", "gala kharab hai", "kharish ho rahi hai").
- intent faq: hours, fees, location, general clinic questions (e.g. "clinic hours", "timings kya hain", "fees kitni hai").
- intent reschedule: change an existing appointment (e.g. "reschedule appointment", "waqt tabdeel karna hai", "time change karna hai").
- confirms true for yes/confirm/go ahead/book it/haan/ji haan/theek hai/bilkul/kar do.
- declines true for no/cancel/stop/nahi/na/mat karo/rehne do.
- Extract doctor_name, date, symptoms, appointment_id when present.
- Do not diagnose. Do not give medical advice.
"""


def _keyword_nlu(user_message: str, session: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Cheap routing for obvious utterances so we do not call Groq unnecessarily."""
    blob = user_message.lower().strip()
    state = session.get("state")
    confirm = bool(
        re.search(
            r"\b(yes|yeah|yep|y|confirm|book it|go ahead|please book|haan|ji haan|theek hai|sahi hai|bilkul|kar do|kar dein)\b",
            blob,
        )
    )
    decline = bool(
        re.search(
            r"\b(no|nope|cancel|stop|never mind|dont|don't|nahi|na|mat karo|rehne do|chhor do)\b",
            blob,
        )
    )
    if state in ("await_confirm", "reschedule_await_confirm") and (confirm or decline):
        return {
            "intent": "appointment" if state == "await_confirm" else "reschedule",
            "doctor_name": None,
            "date": None,
            "symptoms": None,
            "appointment_id": None,
            "confirms": confirm,
            "declines": decline,
            "faq_topic": None,
        }

    # Reschedule intent keywords (English + Roman Urdu)
    if any(
        phrase in blob
        for phrase in (
            "reschedule",
            "change time",
            "change appointment",
            "change date",
            "waqt tabdeel",
            "time badal",
            "tareekh badal",
            "tabdeel karna",
        )
    ):
        return {
            "intent": "reschedule",
            "doctor_name": None,
            "date": None,
            "symptoms": None,
            "appointment_id": None,
            "confirms": False,
            "declines": False,
            "faq_topic": None,
        }

    # FAQ hours (English + Roman Urdu)
    if state in ("idle", "faq", "booked") and any(
        w in blob
        for w in (
            "hour",
            "timing",
            "open",
            "close",
            "weekend",
            "auqaat",
            "kab khulta",
            "khula hai",
            "band hota",
        )
    ):
        return {
            "intent": "faq",
            "doctor_name": None,
            "date": None,
            "symptoms": None,
            "appointment_id": None,
            "confirms": False,
            "declines": False,
            "faq_topic": "hours",
        }

    # FAQ fees (English + Roman Urdu)
    if state in ("idle", "faq", "booked") and any(
        w in blob
        for w in (
            "fee",
            "cost",
            "price",
            "charge",
            "consult",
            "fees",
            "kitne paise",
            "kitna kharcha",
            "charges",
        )
    ):
        return {
            "intent": "faq",
            "doctor_name": None,
            "date": None,
            "symptoms": None,
            "appointment_id": None,
            "confirms": False,
            "declines": False,
            "faq_topic": "fees",
        }

    # Booking intent keywords (English + Roman Urdu)
    if state in ("idle", "faq", "booked") and any(
        phrase in blob
        for phrase in (
            "doctor se milna",
            "doctor ko dikhana",
            "appointment leni",
            "booking karni",
            "checkup karwana",
            "book appointment",
            "want appointment",
        )
    ):
        return {
            "intent": "appointment",
            "doctor_name": None,
            "date": None,
            "symptoms": None,
            "appointment_id": None,
            "confirms": False,
            "declines": False,
            "faq_topic": None,
        }

    return None


def _nlu_or_groq(user_message: str, session: dict[str, Any], language: str) -> dict[str, Any]:
    local = _keyword_nlu(user_message, session)
    if local:
        return local
    return detect_intent_and_entities(user_message, session["messages"], language)


def detect_intent_and_entities(
    user_message: str,
    history: list[MessageItem],
    language: str,
) -> dict[str, Any]:
    history_blob = "\n".join(
        f"{m.role}: {m.message}" for m in history[-8:]
    )
    try:
        parsed = groq_client.complete_json(
            [
                {"role": "system", "content": NLU_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"language={language}\n"
                        f"conversation:\n{history_blob}\n"
                        f"latest_user_message: {user_message}"
                    ),
                },
            ]
        )
    except Exception as exc:
        logger.warning("NLU LLM call failed, falling back safely: %s", exc)
        parsed = {"intent": "appointment"}

    intent = str(parsed.get("intent") or "appointment").lower().strip()
    if intent not in INTENTS:
        intent = "appointment"
    return {
        "intent": intent,
        "doctor_name": parsed.get("doctor_name"),
        "date": parsed.get("date"),
        "symptoms": parsed.get("symptoms"),
        "appointment_id": parsed.get("appointment_id"),
        "confirms": bool(parsed.get("confirms")),
        "declines": bool(parsed.get("declines")),
        "faq_topic": parsed.get("faq_topic"),
    }


def _looks_like_confirm(text: str, nlu: dict[str, Any]) -> bool:
    if nlu.get("confirms"):
        return True
    return bool(
        re.search(
            r"\b(yes|yeah|yep|confirm|book it|go ahead|please book|haan|ji haan|theek hai|sahi hai|bilkul|kar do|kar dein)\b",
            text,
            re.I,
        )
    )


def _looks_like_decline(text: str, nlu: dict[str, Any]) -> bool:
    if nlu.get("declines"):
        return True
    return bool(
        re.search(
            r"\b(no|nope|cancel|stop|never mind|dont|don't|nahi|na|mat karo|rehne do|chhor do)\b",
            text,
            re.I,
        )
    )


def _extract_appointment_id(text: str, nlu: dict[str, Any]) -> Optional[str]:
    if nlu.get("appointment_id"):
        return str(nlu["appointment_id"]).strip()
    match = re.search(
        r"\b(?:APT-[\w-]+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
        text,
        re.I,
    )
    return match.group(0) if match else None


def _faq_reply(user_message: str, nlu: dict[str, Any]) -> str:
    topic = (nlu.get("faq_topic") or "").lower()
    blob = user_message.lower()
    if topic == "hours" or any(w in blob for w in ("hour", "timing", "open", "close", "weekend")):
        return (
            "Our clinic hours are:\n"
            "Monday - Friday: 9:00 AM to 5:00 PM\n"
            "Saturday-Sunday: CLOSED\n"
            "\n"
            "Our timezone is Asia/Karachi (PKT, UTC+5).\n"
            "\n"
            "Is there anything else you'd like to know?"
        )
    if topic == "fees" or any(w in blob for w in ("fee", "cost", "price", "charge", "consult")):
        doctors = backend_client.list_doctors()
        if doctors:
            lines = ["Consultation fees vary by doctor:"]
            for d in doctors:
                name = d.get("name") or "Doctor"
                spec = d.get("specialization") or ""
                fee = d.get("consultation_fee")
                fee_txt = f"Rs. {int(fee):,}" if isinstance(fee, (int, float)) else "see clinic"
                lines.append(f"- {name} ({spec}): {fee_txt}")
            lines.append("\nWould you like to book an appointment with any of them?")
            return "\n".join(lines)
        return (
            "Consultation fees vary by doctor. Typical specialist fees at our clinic "
            "range from about Rs. 1,800 to Rs. 2,500. Would you like to book an appointment?"
        )
    return (
        "I can help with clinic hours, consultation fees, symptom routing to a specialist, "
        "booking an appointment, or rescheduling. What would you like to know?"
    )


def _format_slots(doctors: list[dict[str, Any]]) -> tuple[str, list[OptionItem], list[dict[str, Any]]]:
    options: list[OptionItem] = []
    candidates: list[dict[str, Any]] = []
    blocks: list[str] = []
    start = today_karachi()

    for d in doctors:
        doctor_id = str(d.get("doctor_id") or "")
        name = d.get("name") or "Doctor"
        spec = d.get("specialization") or ""
        fee = d.get("consultation_fee")
        clinic = d.get("clinic_name") or "Prime Care Clinic"
        avail = backend_client.get_availability(doctor_id, start, next_days=3) if doctor_id else None
        free: list[dict[str, str]] = []
        if avail:
            for day in avail.get("availability") or []:
                date_label = day.get("date")
                for slot in day.get("slots") or []:
                    if slot.get("available"):
                        free.append(
                            {
                                "date": date_label,
                                "time": slot.get("time"),
                                "timestamp": slot.get("timestamp"),
                            }
                        )
                    if len(free) >= 4:
                        break
                if len(free) >= 4:
                    break
        if not free:
            continue
        slot_txt = ", ".join(
            f"{s['date']} at {s['time']}" for s in free[:4] if s.get("date") and s.get("time")
        )
        blocks.append(f"{name} ({spec}) — {clinic} — {slot_txt}")
        options.append(
            OptionItem(
                option_id=f"doc-{doctor_id}",
                text=f"{name} ({spec})",
                doctor_id=uuid.UUID(doctor_id) if doctor_id else None,
            )
        )
        candidates.append(
            {
                "doctor_id": doctor_id,
                "name": name,
                "specialization": spec,
                "consultation_fee": fee,
                "clinic_name": clinic,
                "clinic_address": d.get("clinic_address") or "Ground Floor, ABC Plaza, Taxila",
                "slots": free,
            }
        )
    if not blocks:
        return (
            "I could not find open slots for that specialty right now. "
            "Would you like me to check a different day, or book with another available doctor?",
            [],
            [],
        )
    body = (
        "Based on what you described, here are available doctors and times:\n\n"
        + "\n".join(f"{i}. {line}" for i, line in enumerate(blocks, 1))
        + "\n\nPlease tell me the doctor and time you prefer (for example: Dr. Ahmed at 2:00 PM)."
    )
    return body, options, candidates


def _match_doctor_and_slot(
    text: str,
    nlu: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    if not candidates:
        return None
    blob = text.lower().strip()
    doctor_hint = (nlu.get("doctor_name") or "").lower()
    doctor_id_hint = str(nlu.get("doctor_id") or nlu.get("option_id") or "").lower().strip()

    chosen = None

    # 1. Doctor ID / Option ID matching as FIRST check
    if doctor_id_hint:
        for c in candidates:
            cid = str(c.get("doctor_id") or "").lower()
            if cid and (doctor_id_hint == cid or doctor_id_hint == f"doc-{cid}" or cid in doctor_id_hint):
                chosen = c
                break

    if chosen is None:
        for i, c in enumerate(candidates, 1):
            cid = str(c.get("doctor_id") or "").lower()
            if cid and (cid in blob or f"doc-{cid}" in blob):
                chosen = c
                break
            if f"doc-{i}" in blob:
                chosen = c
                break

    # 2. Fall back to name-parsing only if no ID matched
    if chosen is None and doctor_hint:
        for c in candidates:
            if doctor_hint in (c.get("name") or "").lower():
                chosen = c
                break

    if chosen is None:
        clean_blob = blob.replace("dr.", "").strip()
        for c in candidates:
            name = (c.get("name") or "").lower()
            clean_name = name.replace("dr.", "").strip()
            if name in blob or (clean_blob and clean_blob in clean_name):
                chosen = c
                break
            name_parts = [p for p in clean_name.split() if len(p) >= 3]
            if any(p in blob for p in name_parts):
                chosen = c
                break

    if chosen is None and len(candidates) == 1:
        chosen = candidates[0]


    if chosen is None:
        return None

    slot_match = None
    time_patterns = re.findall(
        r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b",
        text,
        flags=re.I,
    )
    for raw in time_patterns:
        normalized = raw.lower().replace(" ", "")
        for slot in chosen.get("slots") or []:
            t = (slot.get("time") or "").lower().replace(" ", "")
            ts = (slot.get("timestamp") or "").lower()
            if normalized in t or raw.lower() in (slot.get("time") or "").lower():
                slot_match = slot
                break
            # 2pm vs 14:00
            try:
                parsed = date_parser.parse(raw)
                if slot.get("time") and parsed.strftime("%H:%M") == slot["time"]:
                    slot_match = slot
                    break
                if slot.get("timestamp") and parsed.strftime("%H:%M") in ts:
                    slot_match = slot
                    break
            except Exception:
                pass
        if slot_match:
            break

    if slot_match is None and chosen.get("slots"):
        # If they named a doctor and only one slot was offered, accept it only when they also said a time-ish word
        if re.search(r"\b(\d{1,2}|first|that time)\b", blob):
            slot_match = chosen["slots"][0]

    if slot_match is None:
        return {"doctor": chosen, "slot": None}

    return {"doctor": chosen, "slot": slot_match}


def _confirmation_summary(session: dict[str, Any]) -> str:
    doctor = session.get("selected_doctor") or {}
    fee = doctor.get("consultation_fee")
    fee_txt = f"Rs. {int(fee):,}" if isinstance(fee, (int, float)) else "as listed by the clinic"
    return (
        "Perfect! Let me confirm your appointment:\n\n"
        f"Doctor: {doctor.get('name')} ({doctor.get('specialization')})\n"
        f"Date/Time: {session.get('selected_slot_label')}\n"
        f"Clinic: {doctor.get('clinic_name')}\n"
        f"Address: {doctor.get('clinic_address')}\n"
        f"Consultation Fee: {fee_txt}\n\n"
        "This looks correct. Shall I go ahead and book this appointment?"
    )


def _success_message(created: dict[str, Any], session: dict[str, Any]) -> str:
    doctor = session.get("selected_doctor") or {}
    appt_id = created.get("appointment_id") or created.get("id")
    when = created.get("appointment_time") or session.get("selected_slot_label")
    return (
        "Great! Your appointment is confirmed!\n\n"
        "🎯 Appointment Details:\n"
        f"Appointment ID: {appt_id}\n"
        f"Doctor: {created.get('doctor_name') or doctor.get('name')}\n"
        f"Date/Time: {when}\n"
        f"Location: {doctor.get('clinic_name') or 'Prime Care Clinic Taxila'}\n\n"
        "📱 You'll receive:\n"
        "• WhatsApp reminder 24 hours before\n"
        "• WhatsApp reminder 1 hour before\n"
        "• Calendar invite (check your email)\n\n"
        "Important: Please arrive 10 minutes early. Bring your ID and any medical records.\n\n"
        "Is there anything else I can help you with?"
    )


def _booking_error_message(exc: backend_client.BackendError) -> str:
    code = exc.error_code
    if code == "INVALID_TIME":
        return "That appointment time is not valid (it may be in the past). Please pick another available slot."
    if code == "SLOT_UNAVAILABLE":
        return "That time slot is not available. Please pick another time from the list."
    if code == "DOUBLE_BOOKING":
        return "You already have an appointment at that time. Would you like a different slot?"
    if code == "NOT_FOUND":
        return "I could not find that doctor or patient record. Please log in as a patient and try again."
    if exc.status_code in (401, 403):
        return LOGIN_REQUIRED_BOOK
    return exc.message or "I could not complete the booking. Please try another slot or contact the clinic."


def _handle_booking(
    session: dict[str, Any],
    user_message: str,
    nlu: dict[str, Any],
    authorization: Optional[str],
) -> tuple[str, str, list[OptionItem]]:
    state = session["state"]

    if state in ("idle", "faq"):
        session["state"] = "await_symptoms"
        return (
            "Hi! I'm MediBook AI, your virtual receptionist. I'd be happy to help you book an appointment.\n\n"
            "What brings you in today? Please describe your symptoms or health concern.",
            "waiting_for_symptoms",
            [],
        )

    if session["state"] == "await_symptoms":
        if nlu.get("symptoms"):
            session["symptoms_text"] = str(nlu["symptoms"])
        else:
            session["symptoms_text"] = user_message
        if is_emergency(session["symptoms_text"]):
            session["state"] = "emergency"
            return EMERGENCY_ALERT, "emergency_redirect", []
        result = triage(session["symptoms_text"])
        session["specialty"] = result.specialty
        session["urgency_level"] = result.urgency_level
        session["follow_ups"] = follow_ups_for(result.specialty)
        session["follow_up_index"] = 0
        session["state"] = "await_followup"
        question = session["follow_ups"][0]
        return (
            "Thank you. I will route you to the right specialist — I will not diagnose the condition.\n\n"
            f"Let me ask a few quick questions:\n{question}",
            "waiting_for_followup",
            [],
        )

    if session["state"] == "await_followup":
        session["symptoms_text"] = (session.get("symptoms_text") or "") + " " + user_message
        if is_emergency(session["symptoms_text"]):
            session["state"] = "emergency"
            return EMERGENCY_ALERT, "emergency_redirect", []
        session["follow_up_index"] = int(session.get("follow_up_index") or 0) + 1
        result = triage(session["symptoms_text"])
        session["specialty"] = result.specialty or session.get("specialty")
        session["urgency_level"] = result.urgency_level
        follow_ups = session.get("follow_ups") or follow_ups_for(session.get("specialty"))
        session["follow_ups"] = follow_ups
        if session["follow_up_index"] < min(3, len(follow_ups)):
            nxt = follow_ups[session["follow_up_index"]]
            return f"Thanks. {nxt}", "waiting_for_followup", []

        specialty = session.get("specialty")
        doctors = backend_client.list_doctors(specialization=specialty)
        if not doctors:
            doctors = backend_client.list_doctors()
        body, options, candidates = _format_slots(doctors)
        session["candidate_doctors"] = candidates
        session["state"] = "await_slot"
        rec = (
            f"Based on your symptoms, I recommend seeing a {specialty}."
            if specialty
            else "Based on your symptoms, I recommend seeing one of our available clinic doctors."
        )
        rec += " This is a routing suggestion only, not a diagnosis.\n\n"
        return rec + body, "waiting_for_doctor_selection", options

    if session["state"] in ("await_slot", "await_confirm"):
        if session["state"] == "await_confirm" and _looks_like_decline(user_message, nlu):
            session["state"] = "await_slot"
            return (
                "No problem. Please pick another doctor and time from the list.",
                "waiting_for_doctor_selection",
                [],
            )
        if session["state"] == "await_confirm" and _looks_like_confirm(user_message, nlu):
            return _confirm_booking(session, authorization)

        matched = _match_doctor_and_slot(user_message, nlu, session.get("candidate_doctors") or [])
        if not matched or not matched.get("doctor"):
            return (
                "I didn't catch the doctor and time. Please reply with a doctor name and a listed slot, "
                "for example: Dr. Ahmed at 14:00.",
                "waiting_for_doctor_selection",
                [],
            )
        if not matched.get("slot"):
            session["selected_doctor"] = matched["doctor"]
            names = ", ".join(
                f"{s.get('date')} {s.get('time')}" for s in (matched["doctor"].get("slots") or [])[:4]
            )
            return (
                f"I found {matched['doctor'].get('name')}. Which of these times works: {names}?",
                "waiting_for_doctor_selection",
                [],
            )
        doctor = matched["doctor"]
        slot = matched["slot"]
        session["selected_doctor"] = doctor
        session["selected_timestamp"] = slot.get("timestamp")
        session["selected_slot_label"] = f"{slot.get('date')} at {slot.get('time')}"
        session["state"] = "await_confirm"
        return _confirmation_summary(session), "waiting_for_confirmation", []

    session["state"] = "await_symptoms"
    return (
        "Let's start over. Please describe your symptoms or health concern.",
        "waiting_for_symptoms",
        [],
    )


def _confirm_booking(
    session: dict[str, Any],
    authorization: Optional[str],
) -> tuple[str, str, list[OptionItem]]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return LOGIN_REQUIRED_BOOK, "waiting_for_login", []
    patient_id = session.get("patient_id")
    if not patient_id:
        return MISSING_PATIENT_ID, "waiting_for_login", []
    doctor = session.get("selected_doctor") or {}
    timestamp = session.get("selected_timestamp")
    if not doctor.get("doctor_id") or not timestamp:
        session["state"] = "await_slot"
        return (
            "I lost the selected slot. Please pick a doctor and time again.",
            "waiting_for_doctor_selection",
            [],
        )
    payload = {
        "patient_id": patient_id,
        "doctor_id": doctor["doctor_id"],
        "appointment_time": timestamp,
        "symptoms_reported": (session.get("symptoms_text") or "General consultation")[:500],
        "urgency_level": session.get("urgency_level") or "normal",
        "appointment_type": "in_person",
    }
    try:
        created = backend_client.create_appointment(payload, authorization)
    except backend_client.BackendError as exc:
        return _booking_error_message(exc), "waiting_for_confirmation", []

    appt_id = created.get("appointment_id") or created.get("id")
    session["appointment_booked"] = str(appt_id) if appt_id else None
    session["status"] = "completed"
    session["state"] = "booked"

    # Fail-safe Google Calendar event creation
    cal_event_id = None
    try:
        cal_payload = {
            "appointment_id": str(appt_id or ""),
            "doctor_name": created.get("doctor_name") or doctor.get("name"),
            "patient_name": created.get("patient_name") or "Patient",
            "clinic_name": doctor.get("clinic_name") or "Prime Care Clinic",
            "clinic_address": doctor.get("clinic_address") or "Ground Floor, ABC Plaza, Taxila",
            "appointment_time": created.get("appointment_time") or timestamp,
            "duration_minutes": 30,
            "symptoms_reported": session.get("symptoms_text") or "",
        }
        cal_event_id = google_calendar.create_calendar_event(cal_payload)
        if cal_event_id:
            session["google_calendar_event_id"] = cal_event_id
    except Exception as exc:
        logger.warning("Google Calendar event creation failed (non-blocking): %s", exc)

    # Fail-safe n8n webhook event & automated reminders dispatch
    try:
        n8n_payload = {
            "appointment_id": str(appt_id or ""),
            "patient_id": str(patient_id or ""),
            "patient_name": created.get("patient_name") or "Patient",
            "doctor_id": str(doctor.get("doctor_id") or ""),
            "doctor_name": created.get("doctor_name") or doctor.get("name"),
            "appointment_time": created.get("appointment_time") or timestamp,
            "clinic_id": str(created.get("clinic_id") or ""),
            "clinic_name": doctor.get("clinic_name") or "Prime Care Clinic",
            "clinic_address": doctor.get("clinic_address") or "Ground Floor, ABC Plaza, Taxila",
            "symptoms_reported": session.get("symptoms_text") or "",
            "urgency_level": session.get("urgency_level") or "normal",
            "reminder_time_1": created.get("reminder_time_1"),
            "reminder_time_2": created.get("reminder_time_2"),
            "google_calendar_event_id": cal_event_id,
        }
        n8n_webhook.dispatch_appointment_created(n8n_payload)
        reminders.trigger_reminder(n8n_payload, reminder_type="24h")
        reminders.trigger_reminder(n8n_payload, reminder_type="1h")
    except Exception as exc:
        logger.warning("n8n webhook / reminder dispatch failed (non-blocking): %s", exc)

    return _success_message(created, session), "appointment_booked", []


def _handle_reschedule(
    session: dict[str, Any],
    user_message: str,
    nlu: dict[str, Any],
    authorization: Optional[str],
) -> tuple[str, str, list[OptionItem]]:
    state = session["state"]
    appt_id = _extract_appointment_id(user_message, nlu) or session.get("reschedule_appointment_id")

    if state not in ("reschedule_await_id", "reschedule_await_slot", "reschedule_await_confirm"):
        session["state"] = "reschedule_await_id"
        if not appt_id:
            return (
                "I can help you reschedule!\n\n"
                "Do you know your appointment ID? Please paste it (for example APT-2026-08-22-001 or the UUID).",
                "waiting_for_appointment_id",
                [],
            )

    if appt_id:
        session["reschedule_appointment_id"] = appt_id

    if session["state"] == "reschedule_await_id":
        if not session.get("reschedule_appointment_id"):
            return (
                "Please share the appointment ID so I can look up your booking.",
                "waiting_for_appointment_id",
                [],
            )
        doctors = backend_client.list_doctors()
        body, options, candidates = _format_slots(doctors[:3] if doctors else [])
        session["candidate_doctors"] = candidates
        session["state"] = "reschedule_await_slot"
        return (
            f"Found appointment {session['reschedule_appointment_id']}. "
            "When would you like to reschedule this to?\n\n" + body,
            "waiting_for_new_time",
            options,
        )

    if session["state"] in ("reschedule_await_slot", "reschedule_await_confirm"):
        if session["state"] == "reschedule_await_confirm" and _looks_like_confirm(user_message, nlu):
            if not authorization or not authorization.lower().startswith("bearer "):
                return LOGIN_REQUIRED_RESCHEDULE, "waiting_for_login", []
            try:
                updated = backend_client.reschedule_appointment(
                    session["reschedule_appointment_id"],
                    session["selected_timestamp"],
                    authorization,
                )
            except backend_client.BackendError as exc:
                if exc.status_code in (401, 403):
                    return LOGIN_REQUIRED_RESCHEDULE, "waiting_for_login", []
                return _booking_error_message(exc), "waiting_for_new_time", []

            session["state"] = "idle"
            new_time = updated.get("appointment_time") or session.get("selected_slot_label")
            new_timestamp = session.get("selected_timestamp") or updated.get("appointment_time")

            # Fail-safe Google Calendar event update
            cal_event_id = session.get("google_calendar_event_id") or updated.get("google_calendar_event_id")
            if cal_event_id and new_timestamp:
                try:
                    google_calendar.update_calendar_event(cal_event_id, new_timestamp)
                except Exception as exc:
                    logger.warning("Google Calendar update failed (non-blocking): %s", exc)

            # Fail-safe n8n webhook reschedule dispatch & reminder recalculations
            try:
                reminder_meta = reminders.calculate_reminder_times(new_timestamp) if new_timestamp else {}
                doc = session.get("selected_doctor") or {}
                reschedule_payload = {
                    "appointment_id": str(session.get("reschedule_appointment_id") or ""),
                    "patient_id": str(session.get("patient_id") or ""),
                    "doctor_id": str(doc.get("doctor_id") or ""),
                    "new_appointment_time": new_timestamp,
                    "previous_appointment_time": session.get("previous_appointment_time"),
                    "new_reminder_time_1": reminder_meta.get("reminder_time_1"),
                    "new_reminder_time_2": reminder_meta.get("reminder_time_2"),
                }
                n8n_webhook.dispatch_appointment_rescheduled(reschedule_payload)
            except Exception as exc:
                logger.warning("n8n reschedule dispatch failed (non-blocking): %s", exc)

            return (
                "Perfect! Your appointment has been rescheduled:\n\n"
                f"New time: {new_time}\n\n"
                "📱 You'll receive:\n"
                "• WhatsApp reminder 24 hours before\n"
                "• WhatsApp reminder 1 hour before\n"
                "• Updated calendar invite (check your email)\n\n"
                "Confirmed!",
                "reschedule_complete",
                [],
            )
        matched = _match_doctor_and_slot(user_message, nlu, session.get("candidate_doctors") or [])
        if matched and matched.get("slot"):
            session["selected_doctor"] = matched["doctor"]
            session["selected_timestamp"] = matched["slot"].get("timestamp")
            session["selected_slot_label"] = f"{matched['slot'].get('date')} at {matched['slot'].get('time')}"
            session["state"] = "reschedule_await_confirm"
            return (
                f"Reschedule to {session['selected_slot_label']} with {matched['doctor'].get('name')}? "
                "Reply yes to confirm.",
                "waiting_for_confirmation",
                [],
            )
        return (
            "Please pick a listed date and time for the new appointment.",
            "waiting_for_new_time",
            [],
        )

    return (
        "Please share your appointment ID to reschedule.",
        "waiting_for_appointment_id",
        [],
    )


def handle_message(
    *,
    conversation_id: Optional[str],
    patient_id: Optional[str],
    message: str,
    language: str,
    authorization: Optional[str],
) -> dict[str, Any]:
    _cleanup_expired_sessions()
    conv_id = conversation_id or f"conv-{uuid.uuid4().hex[:12]}"
    session = _sessions.get(conv_id) or _new_session(conv_id, patient_id)
    session["last_accessed"] = time.time()
    if patient_id:
        session["patient_id"] = patient_id

    _append(session, "user", message)

    combined = f"{session.get('symptoms_text') or ''} {message}".strip()
    if is_emergency(message) or is_emergency(combined):
        session["state"] = "emergency"
        bot = EMERGENCY_ALERT
        next_action = "emergency_redirect"
        options: list[OptionItem] = []
    else:
        nlu = _nlu_or_groq(message, session, language)
        intent = nlu["intent"]
        session["last_intent"] = intent
        in_booking = session["state"] in (
            "await_symptoms",
            "await_followup",
            "await_slot",
            "await_confirm",
        )
        in_reschedule = session["state"].startswith("reschedule")

        if in_booking and intent == "faq" and not _looks_like_confirm(message, nlu):
            bot, next_action, options = _faq_reply(message, nlu), "waiting_for_input", []
            # stay in booking after FAQ
        elif (intent == "reschedule" or in_reschedule) and not (
            in_booking and intent == "symptom"
        ):
            bot, next_action, options = _handle_reschedule(session, message, nlu, authorization)
        elif intent == "faq" and session["state"] in ("idle", "faq", "booked"):
            session["state"] = "faq"
            bot, next_action, options = _faq_reply(message, nlu), "waiting_for_input", []
        elif intent == "symptom" and session["state"] == "idle":
            session["state"] = "await_symptoms"
            bot, next_action, options = _handle_booking(session, message, nlu, authorization)
        else:
            if session["state"] == "idle" and intent in ("appointment", "symptom"):
                session["state"] = "idle" if intent == "appointment" else "await_symptoms"
            bot, next_action, options = _handle_booking(session, message, nlu, authorization)

    _append(session, "assistant", bot)
    return {
        "conversation_id": conv_id,
        "patient_id": session.get("patient_id"),
        "timestamp": utc_now_iso(),
        "bot_message": bot,
        "next_action": next_action,
        "options": options,
        "conversation_history": session["messages"],
        "status": session.get("status") or "ongoing",
        "appointment_booked": session.get("appointment_booked"),
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
    }
