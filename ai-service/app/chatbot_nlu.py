"""NLU: intent classification, entity extraction using LLM."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app import groq_client
from app.chatbot_state import S
from app.schemas import MessageItem

logger = logging.getLogger("medibook.ai.nlu")

MAX_HISTORY = 20

INTENTS = ("appointment", "symptom", "faq", "reschedule", "cancel", "lookup", "show_doctors", "patient_details")

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
- lookup: check/view appointment details ("what is my appointment", "show my bookings")
- patient_details: doctor wants to view a specific patient's appointment details (e.g. "علی کی ڈیٹیل دکھاؤ", "show Ali's details", "mujhe patient ki detail chahiye")
- confirms true: yes/confirm/haan/ji haan/theek hai/bilkul/kar do
- declines true: no/cancel/nahi/na/mat karo/rehne do
- Extract doctor_name when user mentions a specific doctor
- Extract specialty when the user clearly names a medical specialty or it is clearly implied by symptoms
- Extract symptoms when user describes health issues
- Extract appointment_id when user references a specific appointment
- If you are not confident about doctor_name or specialty, return null rather than guessing. Never invent a doctor name or specialty that wasn't clearly stated or implied by symptoms.
"""


def classify(text: str, history: list[MessageItem], state: S) -> dict[str, Any]:
    history_blob = "\n".join(f"{m.role}: {m.message}" for m in history[-8:])
    
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
    if state in (S.AWAIT_CONFIRM, S.RESCHEDULE_CONFIRM, S.CANCEL_CONFIRM):
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
    except Exception as exc:
        logger.warning("NLU LLM failed: %s", exc)
        parsed = {"intent": "symptom"}

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
    m = re.search(r"\b(?:APP?T-[\w-]+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b", text, re.I)
    return m.group(0) if m else None


def extract_option_id(text: str, nlu: dict) -> Optional[str]:
    if nlu.get("option_id"):
        return str(nlu["option_id"]).strip()
    m = re.search(r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b", text, re.I)
    if m:
        return m.group(1)
    iso = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)?)", text)
    if iso:
        return iso.group(1)
    return None
