"""Session management for the MediBook AI agentic chatbot."""
from __future__ import annotations

import time
from typing import Any, Optional

from app.schemas import MessageItem

SESSION_TTL = 2 * 60 * 60  # 2 hours
_sessions: dict[str, dict[str, Any]] = {}

MAX_HISTORY = 20


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
        "pending_action": None,  # Holds proposed action details and proposal_id
        "last_ui_data": {},
        "candidate_doctors": [],
        "selected_doctor": None,
        "patient_appointments": [],
        "appointment_booked": None,
        "google_calendar_event_id": None,
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
    session["messages"].append(MessageItem(role=role, message=text, timestamp=ts))
    if len(session["messages"]) > MAX_HISTORY:
        session["messages"] = session["messages"][-MAX_HISTORY:]
    session["last_accessed"] = _now_ts()
