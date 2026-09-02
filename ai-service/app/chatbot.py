"""Conversation manager: intent routing and workflow orchestration."""
from __future__ import annotations

import logging
from typing import Any, Optional
from datetime import datetime, timezone
from uuid import uuid4

from app import backend_client
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
from app.chatbot_doctor import handle_doctor_message

logger = logging.getLogger("medibook.ai.chatbot")


def _reset_patient_workflow(session: dict[str, Any], intent: str) -> None:
    session["picked_appointment_id"] = None
    session["patient_appointments"] = []
    session["previous_slot_label"] = None

    if intent in {"appointment", "cancel", "reschedule"}:
        session["selected_doctor"] = None
        session["selected_slot"] = None
        session["selected_slot_label"] = None
        session["selected_timestamp"] = None

    if intent == "appointment":
        session["candidate_doctors"] = []
        session["symptoms_text"] = ""
        session["follow_up_index"] = 0
        session["follow_ups"] = []
        session["specialty"] = None
        session["urgency_level"] = "normal"

    session["state"] = S.IDLE

def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

def _faq_reply(text: str, nlu: dict) -> str:
    t = (nlu.get("faq_topic") or "").lower()
    if t == "hours":
        return "Our clinic hours are:\nMon-Fri: 9:00 AM to 5:00 PM\nSat-Sun: CLOSED\n\nIs there anything else?"
    if t == "fees":
        return "Consultation fees vary by specialist, typically ranging from Rs. 1,800 to Rs. 2,500. Would you like to see available doctors?"
    return "I can help with clinic hours, fees, booking an appointment, rescheduling, or cancellations. What do you need?"

def _validated_specialty(specialty: Optional[str]) -> Optional[str]:
    if not specialty:
        return None
    requested = str(specialty).strip().casefold()
    for doctor in backend_client.list_doctors():
        value = doctor.get("specialization") or doctor.get("specialty")
        if value and str(value).strip().casefold() == requested:
            return str(value)
    return None

def _show_doctors_response(session: dict[str, Any]) -> tuple[str, str, dict]:
    spec = session.get("specialty")
    if not spec:
        docs = backend_client.list_doctors()
    else:
        docs = backend_client.list_doctors(specialization=spec)
    
    from app.chatbot_slots import fetch_doctor_slots, doctors_ui_data
    enriched = fetch_doctor_slots(docs, next_days=3)
    session["candidate_doctors"] = enriched
    session["state"] = S.SHOWING_DOCTORS
    
    if not enriched:
        return f"No {spec or 'doctor'} slots are available right now. Please try again later.", "waiting_for_doctor_selection", {"doctors": []}
    
    msg = f"Here are the available {'specialists' if spec else 'doctors'}:"
    return msg, "waiting_for_doctor_selection", {"doctors": doctors_ui_data(enriched)}

def handle_message(
    *,
    conversation_id: Optional[str],
    patient_id: Optional[str],
    message: str,
    language: str,
    authorization: Optional[str],
) -> dict[str, Any]:
    conv_id = conversation_id or str(uuid4())
    
    session = get_session(conv_id)
    if not session:
        session = new_session(conv_id, patient_id)

    current_user = None
    if authorization and authorization.lower().startswith("bearer "):
        current_user = backend_client.get_current_user(authorization)
        user_type = str((current_user or {}).get("user_type") or "").lower()

        if user_type == "doctor":
            doctor_candidates = backend_client.list_doctors()
            matching_doctor = next(
                (
                    doctor for doctor in doctor_candidates
                    if str(doctor.get("user_id") or "").lower() == str((current_user or {}).get("user_id") or "").lower()
                ),
                None,
            )
            if matching_doctor:
                now_ts = _utc_now()
                append_msg(session, "user", message, now_ts)
                doctor_result = handle_doctor_message(
                    session=session,
                    message=message,
                    authorization=authorization,
                    doctor_context=matching_doctor,
                )
                append_msg(session, "assistant", doctor_result["bot_message"], _utc_now())
                return {
                    "conversation_id": conv_id,
                    "patient_id": session.get("patient_id"),
                    "timestamp": _utc_now(),
                    "bot_message": doctor_result["bot_message"],
                    "next_action": doctor_result["next_action"],
                    "options": [],
                    "ui_data": doctor_result.get("ui_data", {}),
                    "conversation_history": session["messages"],
                    "status": session.get("status", "ongoing"),
                    "appointment_booked": session.get("appointment_booked"),
                    "created_at": _utc_now(),
                    "updated_at": _utc_now(),
                }

            bot = "Unable to load your doctor profile — please contact support"
            action = "doctor_profile_error"
            ui_data = {}
            now_ts = _utc_now()
            append_msg(session, "user", message, now_ts)
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
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            }

        if user_type and user_type != "patient":
            bot = (
                "This assistant is for patients booking appointments. "
                "Please use your dashboard to manage your schedule."
            )
            action = "redirect_non_patient"
            ui_data = {}
            now_ts = _utc_now()
            append_msg(session, "user", message, now_ts)
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
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            }

    if patient_id:
        if session.get("authenticated_user_id") != patient_id:
            session["authenticated_user_id"] = patient_id
            canonical_profile = None
            if authorization and authorization.lower().startswith("bearer "):
                canonical_profile = backend_client.get_patient_profile(patient_id, authorization)
            session["patient_id"] = str(
                (canonical_profile or {}).get("patient_id") or patient_id
            )

    now_ts = _utc_now()
    append_msg(session, "user", message, now_ts)

    combined = f"{session.get('symptoms_text') or ''} {message}".strip()
    
    if is_emergency(message) or is_emergency(combined):
        session["state"] = S.EMERGENCY
        bot = EMERGENCY_ALERT
        action = "emergency_redirect"
        ui_data = {}
    else:
        nlu = classify(message, session["messages"], session["state"])
        intent = nlu["intent"]
        if nlu.get("specialty"):
            validated_specialty = _validated_specialty(nlu["specialty"])
            if validated_specialty:
                session["specialty"] = validated_specialty
        session["last_intent"] = intent
        
        state = session["state"]
        lower_message = message.lower().strip()
        is_selection_message = lower_message.startswith("selected appointment")
        
        is_symptom = intent == "symptom"
        is_lookup = intent == "lookup"
        
        if is_symptom and not is_lookup:
            if state in (S.LOOKUP, S.CANCEL_PICK, S.CANCEL_CONFIRM, S.RESCHEDULE_PICK, S.RESCHEDULE_SLOTS):
                session["state"] = S.IDLE
                session.pop("candidate_doctors", None)
                session.pop("selected_doctor", None)
                session.pop("selected_slot", None)
                session.pop("patient_appointments", None)
                session.pop("picked_appointment_id", None)
                session.pop("previous_slot_label", None)
                intent = "symptom"
                state = S.IDLE
        
        if nlu.get("wants_doctor_list") or intent == "show_doctors":
            bot, action, ui_data = _show_doctors_response(session)
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
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            }
        
        is_top_level_command = (
            intent in ("appointment", "cancel", "reschedule")
            or (intent == "lookup" and is_lookup)
        )
        if is_top_level_command and not is_selection_message and state not in (S.AWAIT_CONFIRM, S.CANCEL_CONFIRM, S.RESCHEDULE_CONFIRM):
            _reset_patient_workflow(session, intent)
            state = session["state"]
        
        if state == S.EMERGENCY:
            bot = EMERGENCY_ALERT
            action = "emergency_redirect"
            ui_data = {}
            
        elif intent == "faq" and not state in (S.AWAIT_CONFIRM, S.RESCHEDULE_CONFIRM, S.CANCEL_CONFIRM):
            bot = _faq_reply(message, nlu)
            action = "waiting_for_input"
            ui_data = {}
            if state in (S.IDLE, S.BOOKED, S.FAQ):
                session["state"] = S.FAQ
                
        elif intent == "cancel" or state.startswith("cancel"):
            bot, action, _, ui_data = handle_cancel(session, message, nlu, authorization)
            
        elif intent == "reschedule" or state.startswith("reschedule"):
            bot, action, _, ui_data = handle_reschedule(session, message, nlu, authorization)

        elif intent == "lookup" or state == S.LOOKUP:
            if is_symptom and not is_lookup:
                session["state"] = S.IDLE
                bot, action, _, ui_data = handle_new_booking(session, message, nlu, authorization)
            else:
                bot, action, _, ui_data = handle_lookup(session, message, nlu, authorization)
            
        else:
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
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }
