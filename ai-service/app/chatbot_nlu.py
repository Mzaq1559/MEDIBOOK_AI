"""NLU & Entity Extraction Helpers (Fast-path optimization and Doctor Agent classification)."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app import groq_client

logger = logging.getLogger("medibook.ai.nlu")

MAX_HISTORY = 20
_NLU_HISTORY_TURNS = 4

# Regex overrides for Urdu/Roman Urdu cancel/reschedule/lookup
CANCEL_RE = re.compile(r"(کینسل|منسوخ|cancel|hatao|hata do)", re.I)
RESCHEDULE_RE = re.compile(r"(دوبارہ\s*بک|تبدیل|reschedule|badal|waqt\s*badal|time\s*change)", re.I)
LOOKUP_RE = re.compile(
    r"(dikhao|dikha do|meri.*appointment|appointment.*(dekh|show)|میری.*اپوائنٹمنٹ.*دکھاؤ|اپوائنٹمنٹ دیکھنی|show\s+(my|me)\s+(appointment|booking)|what\s+are\s+my\s+appointment|view\s+my\s+appointment|check\s+my\s+appointment|my\s+upcoming\s+appointment)",
    re.I,
)

INTENTS = ("appointment", "symptom", "faq", "reschedule", "cancel", "lookup", "show_doctors", "patient_details")

_DOCTOR_NAME_RE = re.compile(
    r"\b(?:dr\.?|doctor)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", re.I,
)
_DATE_KEYWORDS = {
    "today": "today",
    "tomorrow": "tomorrow",
    "aaj": "today",
    "kal": "tomorrow",
}
_DATE_ISO_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_DATE_NATURAL_RE = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b", re.I,
)


def _fallback_specialty(text: str) -> Optional[str]:
    from app.symptom_triage import recommend_specialty
    return recommend_specialty(text)


def _fallback_doctor_name(text: str) -> Optional[str]:
    m = _DOCTOR_NAME_RE.search(text)
    if m:
        return m.group(0).strip()
    return None


def _fallback_date(text: str) -> Optional[str]:
    lower = text.lower()
    for keyword, value in _DATE_KEYWORDS.items():
        if keyword in lower:
            return value
    m = _DATE_ISO_RE.search(text)
    if m:
        return m.group(1)
    m = _DATE_NATURAL_RE.search(text)
    if m:
        return m.group(0)
    return None


NLU_SYSTEM = """You are the NLU for MediBook AI, a clinic virtual receptionist (Pakistan).
Classify the latest user message. Return JSON only:
{
  "intent": "appointment"|"symptom"|"faq"|"reschedule"|"cancel"|"lookup"|"show_doctors"|"patient_details",
  "doctor_name": string|null,
  "doctor_id": string|null,
  "specialty": string|null,
  "wants_doctor_list": boolean,
  "date": string|null,
  "symptoms": string|null,
  "appointment_id": string|null,
  "confirms": boolean,
  "declines": boolean,
  "faq_topic": "hours"|"fees"|"other"|null,
  "option_id": string|null
}
Rules:
- show_doctors and wants_doctor_list: user asks to see available doctors in English, Roman Urdu, or Urdu script
- appointment: user wants to book an appointment (e.g. "book appointment", "doctor se milna hai", "book with Dr Fatima")
- symptom: user describes health symptoms (e.g. "chest pain", "gala kharab hai", "mujhe bukhar hai")
- faq: clinic hours, fees, location questions
- reschedule: change existing appointment time
- cancel: cancel/delete an appointment
- lookup: check/view appointment details ("what is my appointment", "show my bookings", "meri appointment dikhao")
- patient_details: doctor wants to view a specific patient's appointment details (e.g. "علی کی ڈیٹیل دکھاؤ", "show Ali's details", "mujhe patient ki detail chahiye")
- confirms true: yes/confirm/haan/ji haan/theek hai/bilkul/kar do
- declines true: no/cancel/nahi/na/mat karo/rehne do
"""


def classify(text: str, history: Optional[list[Any]] = None, state: Any = "idle") -> dict[str, Any]:
    history_items = history or []
    lines = []
    for m in history_items[-_NLU_HISTORY_TURNS:]:
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else "user")
        msg = getattr(m, "message", None) or (m.get("message") if isinstance(m, dict) else "")
        lines.append(f"{role}: {msg}")
    history_blob = "\n".join(lines)

    # Check for emergency first (always need fast response)
    emergency_keywords = ["chest pain", "heart attack", "stroke", "bleeding", "unconscious", "breathing difficulty", "seenay mein dard"]
    if any(k in text.lower() for k in emergency_keywords):
        return {
            "intent": "emergency",
            "doctor_name": None,
            "doctor_id": None,
            "specialty": None,
            "wants_doctor_list": False,
            "date": None,
            "symptoms": text,
            "appointment_id": None,
            "confirms": False,
            "declines": False,
            "faq_topic": None,
            "option_id": None,
        }

    # Check for simple confirm/decline in confirmation states (fast path)
    state_str = str(getattr(state, "value", state)).lower()
    if state_str in ("await_confirm", "reschedule_confirm", "cancel_confirm"):
        confirm = bool(re.search(r"\b(yes|yeah|yep|confirm|haan|ji haan|theek hai|bilkul|kar do)\b", text.lower()))
        decline = bool(re.search(r"\b(no|nope|cancel|stop|nahi|na|mat karo|rehne do)\b", text.lower()))
        if confirm or decline:
            return {
                "intent": "appointment",
                "doctor_name": None,
                "doctor_id": None,
                "specialty": None,
                "wants_doctor_list": False,
                "date": None,
                "symptoms": None,
                "appointment_id": None,
                "confirms": confirm,
                "declines": decline,
                "faq_topic": None,
                "option_id": None,
            }

    try:
        parsed = groq_client.complete_json([
            {"role": "system", "content": NLU_SYSTEM},
            {"role": "user", "content": f"conversation:\n{history_blob}\nlatest: {text}"},
        ])
        logger.info("NLU classified intent=%s (state=%s)", parsed.get('intent'), state)
    except Exception as exc:
        logger.warning("NLU LLM failed: %s", exc)
        parsed = {"intent": "symptom"}
        parsed["specialty"] = _fallback_specialty(text)
        parsed["doctor_name"] = _fallback_doctor_name(text)
        parsed["date"] = _fallback_date(text)

    # Regex overrides for Urdu/Roman Urdu cancel/reschedule/lookup
    if CANCEL_RE.search(text):
        parsed["intent"] = "cancel"
    elif RESCHEDULE_RE.search(text):
        parsed["intent"] = "reschedule"
    elif LOOKUP_RE.search(text):
        parsed["intent"] = "lookup"

    intent = str(parsed.get("intent") or "symptom").lower().strip()
    if intent not in INTENTS:
        intent = "symptom"

    return {
        "intent": intent,
        "doctor_name": parsed.get("doctor_name"),
        "doctor_id": parsed.get("doctor_id"),
        "specialty": parsed.get("specialty"),
        "wants_doctor_list": bool(parsed.get("wants_doctor_list")),
        "date": parsed.get("date"),
        "symptoms": parsed.get("symptoms") or text if intent == "symptom" else parsed.get("symptoms"),
        "appointment_id": parsed.get("appointment_id"),
        "confirms": bool(parsed.get("confirms")),
        "declines": bool(parsed.get("declines")),
        "faq_topic": parsed.get("faq_topic"),
        "option_id": parsed.get("option_id"),
    }


def is_confirm(text: str) -> bool:
    """Check if the text represents explicit confirmation."""
    return bool(re.search(r"\b(yes|yeah|yep|y|confirm|book it|go ahead|please book|haan|ji haan|theek hai|bilkul|kar do|sure|ok|okay)\b", text, re.I))


def is_decline(text: str) -> bool:
    """Check if the text represents explicit decline/cancellation of intent."""
    return bool(re.search(r"\b(no|nope|cancel|stop|nahi|na|mat karo|rehne do|chhor do|nevermind|don't)\b", text, re.I))


def is_off_topic_or_hostile(text: str) -> bool:
    """Check if message is hostile or off-topic gibberish."""
    b = text.lower().strip()
    return any(w in b for w in ("stupid", "idiot", "dumb", "shut up", "useless", "whatever", "u are stupid", "you are stupid", "fool", "nonsense"))


def extract_appointment_id(text: str) -> Optional[str]:
    """Extract an appointment UUID or ID string from text."""
    m = re.search(r"\b(?:APT-[\w-]+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b", text, re.I)
    return m.group(0) if m else None


def extract_option_id(text: str) -> Optional[str]:
    """Extract a UUID or ISO-timestamp option_id from text."""
    m = re.search(r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b", text, re.I)
    if m:
        return m.group(1)
    iso = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)?)", text)
    if iso:
        return iso.group(1)
    return None
