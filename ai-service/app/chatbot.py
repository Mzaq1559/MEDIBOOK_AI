"""MediBook AI — agentic chat engine (LLM + function calling)."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from app import groq_client
from app.patient_context import load_patient_context
from app.response_format import lists_appointment_details, strip_markdown
from app.schemas import MessageItem
from app.symptom_triage import EMERGENCY_ALERT, is_emergency
from app.tools import TOOL_DEFINITIONS, build_system_prompt, execute_tool

logger = logging.getLogger("medibook.ai.agent")

SESSION_TTL = 2 * 60 * 60
MAX_HISTORY = 20
MAX_TOOL_ROUNDS = 8

_sessions: dict[str, dict[str, Any]] = {}


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
        "last_ui_data": {},
        "candidate_doctors": [],
        "selected_doctor": None,
        "patient_appointments": [],
        "appointment_booked": None,
        "google_calendar_event_id": None,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
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
    session["updated_at"] = ts


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _assistant_message_dict(message: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": getattr(message, "role", None) or "assistant",
        "content": getattr(message, "content", None),
    }
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        serialized = []
        for tc in tool_calls:
            fn = getattr(tc, "function", None)
            serialized.append(
                {
                    "id": getattr(tc, "id", "") or "",
                    "type": getattr(tc, "type", None) or "function",
                    "function": {
                        "name": getattr(fn, "name", "") if fn is not None else "",
                        "arguments": getattr(fn, "arguments", "{}") if fn is not None else "{}",
                    },
                }
            )
        payload["tool_calls"] = serialized
    return payload


def _default_greeting(session: dict[str, Any]) -> str:
    name = str(session.get("patient_first_name") or "").strip()
    if name:
        return f"Hi {name}! How can I help you today?"
    return "How can I help you today?"


def _next_action_from_ui(session: dict[str, Any], ui_data: dict[str, Any], bot: str) -> str:
    if session.get("appointment_booked") and "confirmed" in (bot or "").lower():
        return "appointment_booked"
    if ui_data.get("doctors"):
        return "waiting_for_doctor_selection"
    if ui_data.get("slots"):
        return "waiting_for_slot_selection"
    if ui_data.get("appointments"):
        return "show_appointments"
    if ui_data.get("booking") and not (ui_data.get("booking") or {}).get("isConfirmed"):
        return "waiting_for_confirmation"
    return "waiting_for_input"


def _strip_listed_appointment_cards(
    bot: str, ui_data: dict[str, Any], session: dict[str, Any]
) -> dict[str, Any]:
    """Drop doctor/appointment cards when the reply already lists those details."""
    if not lists_appointment_details(bot) or not ui_data:
        return ui_data
    ui_data = dict(ui_data)
    ui_data.pop("appointments", None)
    ui_data.pop("doctors", None)
    last = session.get("last_ui_data")
    if isinstance(last, dict):
        last.pop("appointments", None)
        last.pop("doctors", None)
    return ui_data


def run_agent_loop(
    session: dict[str, Any],
    authorization: Optional[str],
    language: str = "english",
) -> tuple[str, dict[str, Any]]:
    """Send history + tools to Groq, execute tool calls, repeat until a final reply."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": build_system_prompt()}]
    patient_context = load_patient_context(session, authorization, language)
    if patient_context:
        messages.append({"role": "system", "content": patient_context})
    if session.get("patient_id"):
        messages.append(
            {
                "role": "system",
                "content": (
                    f"Authenticated patient_id is {session['patient_id']}. "
                    "Pass this id to tools that require it. Do not invent other patient IDs."
                ),
            }
        )
    for m in session["messages"]:
        messages.append({"role": m.role, "content": m.message})

    ui_data: dict[str, Any] = dict(session.get("last_ui_data") or {})
    this_turn_ui_keys: set[str] = set()
    bot = ""

    for _round in range(MAX_TOOL_ROUNDS):
        response_message = groq_client.complete_with_tools(
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            temperature=0.4,
        )
        tool_calls = getattr(response_message, "tool_calls", None) or []
        content = (getattr(response_message, "content", None) or "").strip()

        if not tool_calls:
            bot = strip_markdown(content or _default_greeting(session))
            break

        messages.append(_assistant_message_dict(response_message))
        for tool_call in tool_calls:
            fn = getattr(tool_call, "function", None)
            fn_name = getattr(fn, "name", "") if fn is not None else ""
            fn_args = getattr(fn, "arguments", "{}") if fn is not None else "{}"
            result = execute_tool(fn_name, fn_args, session, authorization)
            if isinstance(result, dict) and result.get("ui_data"):
                fresh = result["ui_data"]
                this_turn_ui_keys.update(fresh.keys())
                ui_data.update(fresh)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": getattr(tool_call, "id", "") or "",
                    "content": json.dumps(result, default=str),
                }
            )
        else:
            continue
    else:
        bot = strip_markdown(content or "I've got what I need — what would you like to do next?")

    # Listing appointments should not keep leftover doctor/slot cards from an earlier turn.
    if "appointments" in this_turn_ui_keys:
        if "doctors" not in this_turn_ui_keys:
            ui_data.pop("doctors", None)
        if "slots" not in this_turn_ui_keys:
            ui_data.pop("slots", None)
        last = session.get("last_ui_data")
        if isinstance(last, dict):
            if "doctors" not in this_turn_ui_keys:
                last.pop("doctors", None)
            if "slots" not in this_turn_ui_keys:
                last.pop("slots", None)

    ui_data = _strip_listed_appointment_cards(bot, ui_data, session)

    return bot, ui_data


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
    if patient_id:
        session["patient_id"] = patient_id

    append_msg(session, "user", message, _utc_now())

    if is_emergency(message):
        bot = EMERGENCY_ALERT
        action = "emergency_redirect"
        ui_data: dict[str, Any] = {}
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
            "created_at": session.get("created_at") or _utc_now(),
            "updated_at": session.get("updated_at") or _utc_now(),
        }

    try:
        bot, ui_data = run_agent_loop(session, authorization, language=language)
    except groq_client.LLMError:
        bot = groq_client.LLM_FALLBACK
        ui_data = dict(session.get("last_ui_data") or {})
    except Exception as exc:
        logger.warning("Agent loop error: %s", exc)
        bot = groq_client.LLM_FALLBACK
        ui_data = dict(session.get("last_ui_data") or {})

    bot = strip_markdown(bot)
    ui_data = _strip_listed_appointment_cards(bot, ui_data, session)
    action = _next_action_from_ui(session, ui_data, bot)
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
        "created_at": session.get("created_at") or _utc_now(),
        "updated_at": session.get("updated_at") or _utc_now(),
    }
