"""State enum and session management for the MediBook AI chatbot."""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Optional

from app.schemas import MessageItem

SESSION_TTL = 2 * 60 * 60  # 2 hours
_sessions: dict[str, dict[str, Any]] = {}


class S(str, Enum):
    IDLE = "idle"
    ASKING_SYMPTOMS = "asking_symptoms"
    ASKING_FOLLOWUP = "asking_followup"
    SHOWING_DOCTORS = "showing_doctors"
    SHOWING_SLOTS = "showing_slots"
    AWAIT_CONFIRM = "await_confirm"
    BOOKED = "booked"
    RESCHEDULE_FETCH = "reschedule_fetch"
    RESCHEDULE_PICK = "reschedule_pick"
    RESCHEDULE_SLOTS = "reschedule_slots"
    RESCHEDULE_CONFIRM = "reschedule_confirm"
    CANCEL_FETCH = "cancel_fetch"
    CANCEL_PICK = "cancel_pick"
    CANCEL_CONFIRM = "cancel_confirm"
    LOOKUP = "lookup"
    EMERGENCY = "emergency"
    FAQ = "faq"


def _now_ts() -> float:
    return time.time()


def _cleanup() -> None:
    now = _now_ts()
    expired = [k for k, v in _sessions.items() if now - float(v.get("last_accessed", 0)) > SESSION_TTL]
    for k in expired:
        _sessions.pop(k, None)


def new_session(conv_id: str, patient_id: Optional[str]) -> dict[str, Any]:
    s: dict[str, Any] = {
        "conversation_id": conv_id,
        "patient_id": patient_id,
        "messages": [],
        "last_accessed": _now_ts(),
        "status": "ongoing",
        "state": S.IDLE,
        # booking
        "symptoms_text": "",
        "follow_up_index": 0,
        "follow_ups": [],
        "specialty": None,
        "urgency_level": "normal",
        "candidate_doctors": [],
        "selected_doctor": None,
        "selected_slot": None,
        "selected_slot_label": None,
        "selected_timestamp": None,
        # reschedule/cancel
        "picked_appointment_id": None,
        "previous_slot_label": None,
        "patient_appointments": [],
        # integrations
        "google_calendar_event_id": None,
        "appointment_booked": None,
        "last_intent": None,
    }
    _sessions[conv_id] = s
    return s


def get_session(conv_id: str) -> Optional[dict[str, Any]]:
    _cleanup()
    s = _sessions.get(conv_id)
    if s:
        s["last_accessed"] = _now_ts()
    return s


def append_msg(session: dict[str, Any], role: str, text: str, ts: str) -> None:
    from app.chatbot_nlu import MAX_HISTORY
    session["messages"].append(MessageItem(role=role, message=text, timestamp=ts))
    if len(session["messages"]) > MAX_HISTORY:
        session["messages"] = session["messages"][-MAX_HISTORY:]
    session["last_accessed"] = _now_ts()
