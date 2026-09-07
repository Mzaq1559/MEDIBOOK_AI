"""MediBook AI — agentic chat engine (LLM + function calling)."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Iterator, Optional
from uuid import uuid4

from app import backend_client, groq_client
from app.chatbot_doctor import handle_doctor_message
from app.patient_context import load_patient_context
from app.response_format import lists_appointment_details, strip_markdown
from app.schemas import MessageItem
from app.symptom_triage import EMERGENCY_ALERT, is_emergency
from app.tools import TOOL_DEFINITIONS, build_system_prompt, execute_tool

logger = logging.getLogger("medibook.ai.agent")

SESSION_TTL = 2 * 60 * 60
MAX_HISTORY = 10
MAX_TOOL_ROUNDS = 8

TOOL_FRIENDLY_LABELS: dict[str, str] = {
    "list_doctors": "Looking up available doctors...",
    "get_doctors_by_specialty": "Looking up available doctors...",
    "get_doctor_availability": "Checking availability...",
    "get_availability": "Checking availability...",
    "get_patient_appointments": "Checking your appointments...",
    "search_patient_appointments": "Checking your appointments...",
    "get_clinic_info": "Getting clinic information...",
    "get_patient_info": "Getting clinic information...",
    "retrieve_medical_knowledge": "Looking into that for you...",
    "propose_book_appointment": "Preparing your booking...",
    "propose_reschedule_appointment": "Preparing your reschedule...",
    "propose_cancel_appointment": "Preparing your cancellation...",
    "execute_confirmed_action": "Confirming your appointment...",
}

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
    if ui_data.get("booking") and not (ui_data.get("booking") or {}).get("isConfirmed"):
        return "waiting_for_confirmation"
    if ui_data.get("slots"):
        return "waiting_for_slot_selection"
    if ui_data.get("doctors"):
        return "waiting_for_doctor_selection"
    if ui_data.get("appointments"):
        return "show_appointments"
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


def _format_doctor_entry(doc: dict[str, Any]) -> str:
    doctor_id = doc.get("doctor_id") or doc.get("id") or ""
    name = doc.get("name") or "Doctor"
    specialty = doc.get("specialization") or doc.get("specialty") or "General"
    return f"{{id: {doctor_id}, name: '{name}', specialty: '{specialty}'}}"


def _doctor_matches_text(doc: dict[str, Any], text: str) -> bool:
    if not text or not doc:
        return False
    text_lower = text.lower()
    full_name = str(doc.get("name") or "").strip().lower()
    if not full_name:
        return False
    if full_name in text_lower:
        return True
    clean_name = re.sub(r"^(dr\.?|doctor)\s+", "", full_name).strip()
    if clean_name and clean_name in text_lower:
        return True
    for part in clean_name.split():
        if len(part) >= 4 and re.search(r"\b" + re.escape(part) + r"\b", text_lower):
            return True
    return False


def _resolve_selected_doctor(session: dict[str, Any], latest_user_msg: str = "") -> Optional[dict[str, Any]]:
    candidates = session.get("candidate_doctors") or []
    selected = session.get("selected_doctor")

    if selected:
        if latest_user_msg:
            for c in candidates:
                c_id = str(c.get("doctor_id") or c.get("id") or "")
                s_id = str(selected.get("doctor_id") or selected.get("id") or "")
                if c_id and s_id and c_id != s_id and _doctor_matches_text(c, latest_user_msg):
                    session["selected_doctor"] = c
                    return c
        return selected

    if len(candidates) == 1:
        session["selected_doctor"] = candidates[0]
        return candidates[0]

    if len(candidates) > 1:
        if latest_user_msg:
            for c in candidates:
                if _doctor_matches_text(c, latest_user_msg):
                    session["selected_doctor"] = c
                    return c
        messages = session.get("messages") or []
        for m in reversed(messages):
            role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else "")
            if role == "assistant":
                text = getattr(m, "message", None) or (m.get("message") if isinstance(m, dict) else "") or ""
                matched = [c for c in candidates if _doctor_matches_text(c, text)]
                if len(matched) == 1:
                    session["selected_doctor"] = matched[0]
                    return matched[0]
                break

    return session.get("selected_doctor")


def _build_doctor_context_message(session: dict[str, Any]) -> Optional[dict[str, Any]]:
    selected = session.get("selected_doctor")
    if selected:
        doc_id = selected.get("doctor_id") or selected.get("id") or ""
        content = (
            f"Active doctor selected for booking: {_format_doctor_entry(selected)}. "
            f"Use doctor_id '{doc_id}' for availability and booking."
        )
        return {"role": "system", "content": content}

    candidates = session.get("candidate_doctors") or []
    if candidates:
        entries = ", ".join(_format_doctor_entry(d) for d in candidates)
        content = f"Candidate doctors available: [{entries}]. Use their IDs for booking."
        return {"role": "system", "content": content}

    return None


def _update_session_doctor_state(
    session: dict[str, Any],
    fn_name: str,
    fn_args: Any,
    result: Any,
) -> None:
    if isinstance(fn_args, str):
        try:
            parsed_args = json.loads(fn_args)
        except Exception:
            parsed_args = {}
    elif isinstance(fn_args, dict):
        parsed_args = fn_args
    else:
        parsed_args = {}

    if fn_name in ("get_doctors_by_specialty", "list_doctors"):
        docs = []
        if isinstance(result, dict) and isinstance(result.get("doctors"), list):
            docs = result["doctors"]
        elif isinstance(session.get("candidate_doctors"), list):
            docs = session["candidate_doctors"]

        if len(docs) == 1:
            candidates = session.get("candidate_doctors") or []
            doc_id = docs[0].get("doctor_id") or docs[0].get("id")
            matched = next((c for c in candidates if (c.get("doctor_id") or c.get("id")) == doc_id), docs[0])
            session["selected_doctor"] = matched
        elif len(docs) > 1:
            session["selected_doctor"] = None

    if fn_name in ("get_availability", "get_doctor_availability", "propose_book_appointment"):
        doctor_id = str(parsed_args.get("doctor_id") or (result.get("doctor_id") if isinstance(result, dict) else "") or "")
        if doctor_id:
            candidates = session.get("candidate_doctors") or []
            matched = next((c for c in candidates if str(c.get("doctor_id") or c.get("id")) == doctor_id), None)
            if matched:
                session["selected_doctor"] = matched
            elif not session.get("selected_doctor") or str(session["selected_doctor"].get("doctor_id") or session["selected_doctor"].get("id")) != doctor_id:
                session["selected_doctor"] = {"doctor_id": doctor_id, "name": parsed_args.get("doctor_name") or "Doctor"}

    if isinstance(result, dict) and result.get("ui_data"):
        booking = result["ui_data"].get("booking")
        if isinstance(booking, dict) and booking.get("doctor"):
            session["selected_doctor"] = booking["doctor"]


def run_agent_loop_stream(
    session: dict[str, Any],
    authorization: Optional[str],
    language: str = "english",
) -> Iterator[dict[str, Any]]:
    """Send history + tools to Groq, execute tool calls, and yield status events as each tool starts."""
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
                    "Rules:\n"
                    "- Use tools for live clinic data. Do not invent doctors, slots, or appointment IDs.\n"
                    "- For booking, reschedule, and cancel: call propose_X first, state the summary, wait for "
                    "explicit affirmative text, then call execute_confirmed_action.\n"
                    "- If the patient is not logged in, ask them to sign in instead of guessing IDs.\n"
                    "- You only help with this clinic's appointments and information.\n"
                    "- Do NOT use markdown symbols (**) in responses.\n"
                    "- Appointment tool selection: when the patient references a specific doctor, date, or "
                    "status (e.g. 'my appointment with Dr. Khan', 'my Tuesday appointment', 'my cancelled "
                    "ones'), use search_patient_appointments with the relevant filters so only matching "
                    "appointments are shown. Use get_patient_appointments only for genuinely broad requests "
                    "like 'what appointments do I have?' with no qualifying details.\n"
                ),
            }
        )

    latest_user_msg = ""
    for m in reversed(session.get("messages") or []):
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else "")
        if role == "user":
            latest_user_msg = getattr(m, "message", None) or (m.get("message") if isinstance(m, dict) else "") or ""
            break

    _resolve_selected_doctor(session, latest_user_msg)
    doc_msg = _build_doctor_context_message(session)
    if doc_msg:
        messages.append(doc_msg)

    for m in session["messages"]:
        messages.append({"role": m.role, "content": m.message})

    ui_data: dict[str, Any] = {}
    this_turn_ui_keys: set[str] = set()
    bot = ""

    turn_groq_calls = 0
    turn_groq_total_ms = 0.0

    for _round in range(MAX_TOOL_ROUNDS):
        t_groq_start = time.perf_counter()
        response_message = groq_client.complete_with_tools(
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            temperature=0.4,
        )
        groq_round_ms = (time.perf_counter() - t_groq_start) * 1000
        turn_groq_calls += 1
        turn_groq_total_ms += groq_round_ms
        logger.info("[PERF TURN ROUND] round=%d Groq API call took %.2f ms", turn_groq_calls, groq_round_ms)

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

            # Emit intermediate status event before tool execution resolves
            label = TOOL_FRIENDLY_LABELS.get(fn_name, "Looking into that for you...")
            yield {"event": "status", "data": {"label": label}}

            result = execute_tool(fn_name, fn_args, session, authorization)
            _update_session_doctor_state(session, fn_name, fn_args, result)
            if isinstance(result, dict) and result.get("ui_data"):
                fresh = result["ui_data"]
                this_turn_ui_keys.update(fresh.keys())
                ui_data.update(fresh)
            tool_payload = result
            if isinstance(result, dict) and "ui_data" in result:
                tool_payload = {k: v for k, v in result.items() if k != "ui_data"}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": getattr(tool_call, "id", "") or "",
                    "content": json.dumps(tool_payload, default=str),
                }
            )
        else:
            continue
    else:
        bot = strip_markdown(content or "I've got what I need — what would you like to do next?")

    # Ensure slot selection clears stale doctor list cards from earlier turns
    if "slots" in this_turn_ui_keys:
        if "doctors" not in this_turn_ui_keys:
            ui_data.pop("doctors", None)
            last = session.get("last_ui_data")
            if isinstance(last, dict):
                last.pop("doctors", None)

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

    yield {"event": "result", "bot": bot, "ui_data": ui_data}


def run_agent_loop(
    session: dict[str, Any],
    authorization: Optional[str],
    language: str = "english",
) -> tuple[str, dict[str, Any]]:
    """Send history + tools to Groq, execute tool calls, repeat until a final reply."""
    bot = ""
    ui_data = {}
    for ev in run_agent_loop_stream(session, authorization, language=language):
        if ev.get("event") == "result":
            bot = ev.get("bot", "")
            ui_data = ev.get("ui_data", {})
    return bot, ui_data


def _match_doctor_context(authorization: Optional[str]) -> tuple[bool, Optional[dict[str, Any]]]:
    """Check if the user is a doctor and return (is_doctor, doctor_context)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return False, None
    current_user = backend_client.get_current_user(authorization)
    user_type = str((current_user or {}).get("user_type") or "").lower()
    if user_type != "doctor":
        return False, None

    doctor_candidates = backend_client.list_doctors()
    current_uid = str((current_user or {}).get("user_id") or "").lower()
    current_did = str((current_user or {}).get("doctor_id") or "").lower()

    matching_doctor = next(
        (
            d for d in doctor_candidates
            if (current_uid and str(d.get("user_id") or "").lower() == current_uid)
            or (current_did and str(d.get("doctor_id") or "").lower() == current_did)
        ),
        None,
    )
    if not matching_doctor and current_did:
        matching_doctor = {
            "doctor_id": (current_user or {}).get("doctor_id"),
            "user_id": (current_user or {}).get("user_id"),
            "name": (current_user or {}).get("name") or "Doctor",
        }
    return True, matching_doctor


def handle_message(
    *,
    conversation_id: Optional[str],
    patient_id: Optional[str],
    message: str,
    language: str,
    authorization: Optional[str],
) -> dict[str, Any]:
    t_req_start = time.perf_counter()
    conv_id = conversation_id or str(uuid4())
    session = get_session(conv_id)
    if not session:
        session = new_session(conv_id, patient_id)
    if patient_id:
        session["patient_id"] = patient_id

    append_msg(session, "user", message, _utc_now())

    # Doctor routing: bypass patient triage & agent loop for authenticated doctors
    is_doctor, matching_doctor = _match_doctor_context(authorization)
    if is_doctor:
        if matching_doctor:
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
                "created_at": session.get("created_at") or _utc_now(),
                "updated_at": session.get("updated_at") or _utc_now(),
            }

        bot = "Unable to load your doctor profile - please contact support"
        action = "doctor_profile_error"
        ui_data = {}
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

    t_em_start = time.perf_counter()
    em_check = is_emergency(message)
    em_ms = (time.perf_counter() - t_em_start) * 1000
    logger.info("[PERF EMERGENCY GUARD] check took %.2f ms (is_emergency=%s)", em_ms, em_check)

    if em_check:
        bot = EMERGENCY_ALERT
        action = "emergency_redirect"
        ui_data: dict[str, Any] = {}
        append_msg(session, "assistant", bot, _utc_now())
        total_turn_ms = (time.perf_counter() - t_req_start) * 1000
        logger.info("[PERF TURN SUMMARY] emergency turn completed in %.2f ms", total_turn_ms)
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

    total_turn_ms = (time.perf_counter() - t_req_start) * 1000
    logger.info("[PERF TURN SUMMARY] message='%s' total_turn_ms=%.2f ms", message[:40], total_turn_ms)

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


def handle_message_stream(
    *,
    conversation_id: Optional[str],
    patient_id: Optional[str],
    message: str,
    language: str,
    authorization: Optional[str],
) -> Iterator[str]:
    """Execute agent loop with streaming status updates via SSE."""
    conv_id = conversation_id or str(uuid4())
    session = get_session(conv_id)
    if not session:
        session = new_session(conv_id, patient_id)
    if patient_id:
        session["patient_id"] = patient_id

    append_msg(session, "user", message, _utc_now())

    is_doctor, matching_doctor = _match_doctor_context(authorization)
    if is_doctor:
        yield f"event: status\ndata: {json.dumps({'label': 'Checking doctor schedule...'})}\n\n"
        if matching_doctor:
            doctor_result = handle_doctor_message(
                session=session,
                message=message,
                authorization=authorization,
                doctor_context=matching_doctor,
            )
            append_msg(session, "assistant", doctor_result["bot_message"], _utc_now())
            final_payload = {
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
                "created_at": session.get("created_at") or _utc_now(),
                "updated_at": session.get("updated_at") or _utc_now(),
            }
            yield f"event: final\ndata: {json.dumps(final_payload, default=str)}\n\n"
            return

        bot = "Unable to load your doctor profile - please contact support"
        action = "doctor_profile_error"
        ui_data = {}
        append_msg(session, "assistant", bot, _utc_now())
        final_payload = {
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
        yield f"event: final\ndata: {json.dumps(final_payload, default=str)}\n\n"
        return

    if is_emergency(message):
        bot = EMERGENCY_ALERT
        action = "emergency_redirect"
        ui_data: dict[str, Any] = {}
        append_msg(session, "assistant", bot, _utc_now())
        final_payload = {
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
        yield f"event: final\ndata: {json.dumps(final_payload, default=str)}\n\n"
        return

    bot = ""
    ui_data = {}
    try:
        for ev in run_agent_loop_stream(session, authorization, language=language):
            if ev.get("event") == "status":
                yield f"event: status\ndata: {json.dumps(ev['data'])}\n\n"
            elif ev.get("event") == "result":
                bot = ev.get("bot", "")
                ui_data = ev.get("ui_data", {})
    except groq_client.LLMError:
        bot = groq_client.LLM_FALLBACK
        ui_data = dict(session.get("last_ui_data") or {})
    except Exception as exc:
        logger.error("Agent loop error in stream: %s", exc, exc_info=True)
        yield f"event: error\ndata: {json.dumps({'message': 'Our AI assistant encountered an issue. Please try again in a moment.'})}\n\n"
        return

    bot = strip_markdown(bot)
    ui_data = _strip_listed_appointment_cards(bot, ui_data, session)
    action = _next_action_from_ui(session, ui_data, bot)
    append_msg(session, "assistant", bot, _utc_now())

    final_payload = {
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
    yield f"event: final\ndata: {json.dumps(final_payload, default=str)}\n\n"

