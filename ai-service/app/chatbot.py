"""Conversation manager: intent routing and workflow orchestration."""
from __future__ import annotations

import logging
from typing import Any, Optional
from datetime import datetime, timezone

from app.schemas import MessageItem, OptionItem
from app.chatbot_state import get_session, new_session, append_msg, S
from app.chatbot_nlu import classify
from app.symptom_triage import is_emergency, EMERGENCY_ALERT
from app.chatbot_handlers import (
    handle_new_booking,
    handle_reschedule,
    handle_cancel,
    handle_lookup
)

logger = logging.getLogger("medibook.ai.chatbot")

def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

def _faq_reply(text: str, nlu: dict) -> str:
    t = (nlu.get("faq_topic") or "").lower()
    b = text.lower()
    if t == "hours" or any(w in b for w in ("hour", "timing", "open", "close", "weekend")):
        return "Our clinic hours are:\nMon-Fri: 9:00 AM to 5:00 PM\nSat-Sun: CLOSED\n\nIs there anything else?"
    if t == "fees" or any(w in b for w in ("fee", "cost", "price", "charge")):
        return "Consultation fees vary by specialist, typically ranging from Rs. 1,800 to Rs. 2,500. Would you like to see available doctors?"
    return "I can help with clinic hours, fees, booking an appointment, rescheduling, or cancellations. What do you need?"

def handle_message(
    *,
    conversation_id: Optional[str],
    patient_id: Optional[str],
    message: str,
    language: str,
    authorization: Optional[str],
) -> dict[str, Any]:
    conv_id = conversation_id or f"conv-{uuid.uuid4().hex[:12]}"
    import uuid # lazy import inside or global
    
    session = get_session(conv_id)
    if not session:
        import uuid
        if not conversation_id:
            conv_id = f"conv-{uuid.uuid4().hex[:12]}"
        session = new_session(conv_id, patient_id)
        
    if patient_id:
        session["patient_id"] = patient_id

    now_ts = _utc_now()
    append_msg(session, "user", message, now_ts)

    combined = f"{session.get('symptoms_text') or ''} {message}".strip()
    
    # 1. Immediate Emergency Override
    if is_emergency(message) or is_emergency(combined):
        session["state"] = S.EMERGENCY
        bot = EMERGENCY_ALERT
        action = "emergency_redirect"
        ui_data = {}
    else:
        # 2. Classify intent
        nlu = classify(message, session["messages"], session["state"])
        intent = nlu["intent"]
        session["last_intent"] = intent
        
        state = session["state"]
        
        # 3. Route to handlers
        if state == S.EMERGENCY:
            bot = EMERGENCY_ALERT
            action = "emergency_redirect"
            ui_data = {}
            
        elif intent == "faq" and not state in (S.AWAIT_CONFIRM, S.RESCHEDULE_CONFIRM, S.CANCEL_CONFIRM):
            bot = _faq_reply(message, nlu)
            action = "waiting_for_input"
            ui_data = {}
            # Do not change state if we are just asking FAQ mid-booking
            if state in (S.IDLE, S.BOOKED, S.FAQ):
                session["state"] = S.FAQ
                
        elif intent == "lookup" or state == S.LOOKUP:
            bot, action, _, ui_data = handle_lookup(session, message, nlu, authorization)
            
        elif intent == "cancel" or state.startswith("cancel"):
            bot, action, _, ui_data = handle_cancel(session, message, nlu, authorization)
            
        elif intent == "reschedule" or state.startswith("reschedule"):
            bot, action, _, ui_data = handle_reschedule(session, message, nlu, authorization)
            
        else:
            # intent == "appointment" or "symptom", or state is a booking state
            if state in (S.IDLE, S.FAQ, S.BOOKED) and intent in ("appointment", "symptom"):
                session["state"] = S.IDLE
            bot, action, _, ui_data = handle_new_booking(session, message, nlu, authorization)

    append_msg(session, "assistant", bot, _utc_now())

    return {
        "conversation_id": conv_id,
        "patient_id": session.get("patient_id"),
        "timestamp": _utc_now(),
        "bot_message": bot,
        "next_action": action,
        "options": [],
        "ui_data": ui_data,
        "conversation_history": session["messages"],
        "status": session.get("status", "ongoing"),
        "appointment_booked": session.get("appointment_booked"),
        "created_at": _utc_now(), # We drop created_at/updated_at tracking in session for simplicity, just return now
        "updated_at": _utc_now(),
    }
