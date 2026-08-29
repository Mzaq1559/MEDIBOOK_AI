"""NLU: intent classification, entity extraction, keyword shortcuts."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app import groq_client
from app.chatbot_state import S
from app.schemas import MessageItem

logger = logging.getLogger("medibook.ai.nlu")

MAX_HISTORY = 20

INTENTS = ("appointment", "symptom", "faq", "reschedule", "cancel", "lookup", "other")

NLU_SYSTEM = """You are the NLU for MediBook AI, a clinic virtual receptionist (Pakistan).
Classify the latest user message. Return JSON only:
{
  "intent": "appointment"|"symptom"|"faq"|"reschedule"|"cancel"|"lookup"|"other",
  "doctor_name": string|null,
  "doctor_id": string|null,
  "date": string|null,
  "symptoms": string|null,
  "appointment_id": string|null,
  "confirms": boolean,
  "declines": boolean,
  "faq_topic": "hours"|"fees"|"other"|null,
  "option_id": string|null
}
Rules:
- appointment: user explicitly wants to book an appointment (e.g. "book an appointment", "book appointment", "doctor se milna hai")
- symptom: user describes health symptoms (e.g. "chest pain", "gala kharab hai", "fever")
- faq: clinic hours, fees, location questions
- reschedule: change existing appointment time
- cancel: cancel/delete an appointment
- lookup: check/view appointment details ("what is my appointment", "show my bookings")
- other: user input is off-topic, hostile, unrecognized, or insult (e.g. "u are stupid", "random text")
- confirms true: yes/confirm/haan/ji haan/theek hai/bilkul/kar do
- declines true: no/cancel/nahi/na/mat karo/rehne do
- Extract option_id if user passes a UUID or option reference."""


def _keyword_nlu(text: str, state: S) -> Optional[dict[str, Any]]:
    b = text.lower().strip()
    confirm = bool(re.search(r"\b(yes|yeah|yep|y|confirm|book it|go ahead|please book|haan|ji haan|theek hai|bilkul|kar do)\b", b))
    decline = bool(re.search(r"\b(no|nope|cancel|stop|nahi|na|mat karo|rehne do|chhor do)\b", b))

    # In confirmation states, catch yes/no immediately without LLM
    if state in (S.AWAIT_CONFIRM, S.RESCHEDULE_CONFIRM, S.CANCEL_CONFIRM) and (confirm or decline):
        return {"intent": "appointment", "confirms": confirm, "declines": decline,
                "doctor_name": None, "doctor_id": None, "date": None, "symptoms": None,
                "appointment_id": None, "faq_topic": None, "option_id": None}

    # Appointment intent keyword match
    if any(p in b for p in ("book an appointment", "book appointment", "appointment book", "make an appointment", "book a doctor", "schedule an appointment", "schedule appointment", "doctor se milna hai", "appointment chahiye")):
        return {"intent": "appointment", "confirms": False, "declines": False,
                "doctor_name": None, "doctor_id": None, "date": None, "symptoms": None,
                "appointment_id": None, "faq_topic": None, "option_id": None}

    # Cancel intent
    if any(p in b for p in ("cancel appointment", "cancel my appointment", "appointment cancel", "cancel karna", "appointment cancel karna")):
        return {"intent": "cancel", "confirms": False, "declines": False,
                "doctor_name": None, "doctor_id": None, "date": None, "symptoms": None,
                "appointment_id": None, "faq_topic": None, "option_id": None}

    # Lookup intent
    if any(p in b for p in ("my appointment", "show appointment", "check appointment", "view appointment", "what is my appointment", "mera appointment", "appointments dikhao")):
        return {"intent": "lookup", "confirms": False, "declines": False,
                "doctor_name": None, "doctor_id": None, "date": None, "symptoms": None,
                "appointment_id": None, "faq_topic": None, "option_id": None}

    # Reschedule intent
    if any(p in b for p in ("reschedule", "change time", "change appointment", "waqt tabdeel", "time badal", "tabdeel karna")):
        return {"intent": "reschedule", "confirms": False, "declines": False,
                "doctor_name": None, "doctor_id": None, "date": None, "symptoms": None,
                "appointment_id": None, "faq_topic": None, "option_id": None}

    # FAQ hours
    if state in (S.IDLE, S.FAQ, S.BOOKED) and any(w in b for w in ("hour", "timing", "open", "close", "weekend", "kab khulta")):
        return {"intent": "faq", "faq_topic": "hours", "confirms": False, "declines": False,
                "doctor_name": None, "doctor_id": None, "date": None, "symptoms": None,
                "appointment_id": None, "option_id": None}

    # FAQ fees
    if state in (S.IDLE, S.FAQ, S.BOOKED) and any(w in b for w in ("fee", "cost", "price", "charge", "fees", "kitne paise")):
        return {"intent": "faq", "faq_topic": "fees", "confirms": False, "declines": False,
                "doctor_name": None, "doctor_id": None, "date": None, "symptoms": None,
                "appointment_id": None, "option_id": None}

    # Hostile or off-topic phrases
    if any(w in b for w in ("stupid", "idiot", "dumb", "shut up", "useless", "whatever", "u are stupid", "you are stupid")):
        return {"intent": "other", "confirms": False, "declines": False,
                "doctor_name": None, "doctor_id": None, "date": None, "symptoms": None,
                "appointment_id": None, "faq_topic": None, "option_id": None}

    return None


def classify(text: str, history: list[MessageItem], state: S) -> dict[str, Any]:
    fast = _keyword_nlu(text, state)
    if fast:
        return fast
    history_blob = "\n".join(f"{m.role}: {m.message}" for m in history[-8:])
    try:
        parsed = groq_client.complete_json([
            {"role": "system", "content": NLU_SYSTEM},
            {"role": "user", "content": f"conversation:\n{history_blob}\nlatest: {text}"},
        ])
    except Exception as exc:
        logger.warning("NLU LLM failed: %s", exc)
        b = text.lower()
        default_intent = "appointment" if "appointment" in b or "book" in b else "symptom"
        parsed = {"intent": default_intent}

    intent = str(parsed.get("intent") or "symptom").lower().strip()
    if intent not in INTENTS:
        intent = "other" if any(w in text.lower() for w in ("stupid", "idiot", "dumb", "shut up")) else "symptom"
    return {
        "intent": intent,
        "doctor_name": parsed.get("doctor_name"),
        "doctor_id": parsed.get("doctor_id"),
        "date": parsed.get("date"),
        "symptoms": parsed.get("symptoms"),
        "appointment_id": parsed.get("appointment_id"),
        "confirms": bool(parsed.get("confirms")),
        "declines": bool(parsed.get("declines")),
        "faq_topic": parsed.get("faq_topic"),
        "option_id": parsed.get("option_id"),
    }
    return {
        "intent": intent,
        "doctor_name": parsed.get("doctor_name"),
        "doctor_id": parsed.get("doctor_id"),
        "date": parsed.get("date"),
        "symptoms": parsed.get("symptoms"),
        "appointment_id": parsed.get("appointment_id"),
        "confirms": bool(parsed.get("confirms")),
        "declines": bool(parsed.get("declines")),
        "faq_topic": parsed.get("faq_topic"),
        "option_id": parsed.get("option_id"),
    }


def is_confirm(text: str, nlu: dict) -> bool:
    if nlu.get("confirms"):
        return True
    return bool(re.search(r"\b(yes|yeah|confirm|book it|go ahead|haan|theek hai|bilkul|kar do)\b", text, re.I))


def is_decline(text: str, nlu: dict) -> bool:
    if nlu.get("declines"):
        return True
    return bool(re.search(r"\b(no|nope|cancel|stop|nahi|na|mat karo|chhor do)\b", text, re.I))


def extract_appointment_id(text: str, nlu: dict) -> Optional[str]:
    if nlu.get("appointment_id"):
        return str(nlu["appointment_id"]).strip()
    m = re.search(r"\b(?:APT-[\w-]+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b", text, re.I)
    return m.group(0) if m else None


def extract_option_id(text: str, nlu: dict) -> Optional[str]:
    """Extract a UUID or ISO-timestamp option_id from the message or NLU result."""
    if nlu.get("option_id"):
        return str(nlu["option_id"]).strip()
    # Allow clients to send bare UUIDs as doctor/slot selection
    m = re.search(r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b", text, re.I)
    if m:
        return m.group(1)
    # Also match ISO 8601 timestamps sent by the TimeSlotGrid (e.g. 2026-08-28T09:00:00+05:00)
    iso = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)?)", text)
    if iso:
        return iso.group(1)
    return None
