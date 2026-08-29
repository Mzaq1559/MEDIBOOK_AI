"""MediBook AI — Single Agentic RAG System Engine."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from app import groq_client
from app.chatbot_handlers import (
    tool_execute_confirmed_action,
    tool_get_clinic_info,
    tool_get_doctor_availability,
    tool_get_patient_appointments,
    tool_list_doctors,
    tool_propose_book_appointment,
    tool_propose_cancel_appointment,
    tool_propose_reschedule_appointment,
    tool_retrieve_medical_knowledge,
)
from app.chatbot_nlu import is_confirm, is_decline, is_off_topic_or_hostile, extract_option_id, extract_appointment_id
from app.chatbot_state import append_msg, get_session, new_session
from app.chatbot_slots import find_doctor_by_id
from app.rag.metrics import metrics
from app.symptom_triage import EMERGENCY_ALERT, is_emergency

logger = logging.getLogger("medibook.ai.agent")

AGENT_SYSTEM_PROMPT = """You are MediBook AI, an expert clinic virtual receptionist and triage assistant.
You assist patients naturally with:
1. Appointment booking, rescheduling, and cancellation.
2. Answering clinic FAQs (hours, fees, location).
3. Symptom triage and medical knowledge guidance.

Rules:
- ALWAYS use tool calls when you need information or need to perform an action.
- Read-only tools (list_doctors, get_doctor_availability, get_patient_appointments, get_clinic_info, retrieve_medical_knowledge) can be called freely.
- Write actions MUST use the two-step flow: FIRST call propose_book_appointment, propose_reschedule_appointment, or propose_cancel_appointment.
- When a propose_* tool succeeds, restate ALL specific details (doctor name, date, time, clinic name, fee if applicable) to the user in plain language, and ask them to explicitly confirm (e.g. "Reply Yes or Confirm to proceed").
- NEVER claim an appointment is booked, rescheduled, or cancelled until confirmation is given.
- If user input is off-topic or hostile, politely redirect them back to clinic services.
- Never diagnose medical conditions — keep triage guidance informational.
"""

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "list_doctors",
            "description": "List available clinic doctors filtered optionally by specialty.",
            "parameters": {
                "type": "object",
                "properties": {
                    "specialty": {"type": "string", "description": "Optional medical specialty"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_doctor_availability",
            "description": "Get available time slots for a specific doctor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "string", "description": "Doctor UUID or ID"}
                },
                "required": ["doctor_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_appointments",
            "description": "Fetch upcoming appointments for the authenticated patient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status_filter": {"type": "string", "description": "Filter status e.g. scheduled"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_clinic_info",
            "description": "Get clinic operational information, working hours, location, and fees.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_medical_knowledge",
            "description": "Retrieve medical knowledge grounding and symptom triage guidance using RAG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Patient symptom description or medical query"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_book_appointment",
            "description": "Validate booking details and create a pending proposal for user confirmation. Does not write to DB.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "string", "description": "Doctor ID"},
                    "date_time": {"type": "string", "description": "Requested date/time or slot label"},
                    "symptoms": {"type": "string", "description": "Optional patient symptoms"}
                },
                "required": ["doctor_id", "date_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_reschedule_appointment",
            "description": "Validate reschedule details and create a pending proposal. Does not write to DB.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string", "description": "Appointment UUID"},
                    "new_date_time": {"type": "string", "description": "New requested date/time"}
                },
                "required": ["appointment_id", "new_date_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_cancel_appointment",
            "description": "Validate cancellation details and create a pending proposal. Does not write to DB.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string", "description": "Appointment UUID"}
                },
                "required": ["appointment_id"],
            },
        },
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _execute_tool_by_name(
    tool_name: str,
    tool_args: dict[str, Any],
    session: dict[str, Any],
    authorization: Optional[str]
) -> dict[str, Any]:
    """Dispatch execution to the corresponding python tool function."""
    logger.info("Agent Tool Dispatch: tool=%s args=%s", tool_name, tool_args)
    
    if tool_name == "list_doctors":
        return tool_list_doctors(session, specialty=tool_args.get("specialty"))
    elif tool_name == "get_doctor_availability":
        return tool_get_doctor_availability(session, doctor_id=str(tool_args.get("doctor_id")))
    elif tool_name == "get_patient_appointments":
        return tool_get_patient_appointments(session, auth=authorization, status_filter=tool_args.get("status_filter", "scheduled"))
    elif tool_name == "get_clinic_info":
        return tool_get_clinic_info(session)
    elif tool_name == "retrieve_medical_knowledge":
        return tool_retrieve_medical_knowledge(session, query=str(tool_args.get("query", "")))
    elif tool_name == "propose_book_appointment":
        return tool_propose_book_appointment(
            session,
            doctor_id=str(tool_args.get("doctor_id")),
            date_time=str(tool_args.get("date_time")),
            symptoms=tool_args.get("symptoms"),
            auth=authorization,
        )
    elif tool_name == "propose_reschedule_appointment":
        return tool_propose_reschedule_appointment(
            session,
            appointment_id=str(tool_args.get("appointment_id")),
            new_date_time=str(tool_args.get("new_date_time")),
            auth=authorization,
        )
    elif tool_name == "propose_cancel_appointment":
        return tool_propose_cancel_appointment(
            session,
            appointment_id=str(tool_args.get("appointment_id")),
            auth=authorization,
        )
    else:
        return {"status": "error", "message": f"Unknown tool '{tool_name}'"}


def _run_agent_fallback(
    message: str,
    session: dict[str, Any],
    authorization: Optional[str]
) -> tuple[str, str, dict[str, Any]]:
    """Deterministic agent fallback for offline/test environments without Groq API keys."""
    metrics.inc("agent_fallback_total")
    clean = message.lower().strip()
    
    # Check option_id selection (e.g. user clicked a doctor or slot card in UI)
    opt_id = extract_option_id(message)
    appt_id = extract_appointment_id(message)
    
    pending = session.get("pending_action")
    if pending and pending.get("status") == "proposed":
        if is_confirm(message):
            res = tool_execute_confirmed_action(session, authorization)
            if res.get("success"):
                action = "appointment_booked" if pending.get("action_type") == "book" else "waiting_for_input"
                return res["message"], action, res.get("ui_data", {})
            else:
                return f"Could not complete request: {res.get('reason')}", "waiting_for_confirmation", session.get("last_ui_data", {})
        elif is_decline(message) or clean == "change":
            session["pending_action"] = None
            res_docs = tool_list_doctors(session)
            return "No problem. Let's pick a different doctor or time option below:", "waiting_for_doctor_selection", res_docs.get("ui_data", {})

    # Intent routing via tool calls
    if any(p in clean for p in ("book an appointment", "book appointment", "appointment book", "make an appointment", "book a doctor", "schedule an appointment", "schedule appointment", "doctor se milna hai", "appointment chahiye")):
        res = tool_list_doctors(session)
        return "Please select a doctor to book your appointment:", "waiting_for_doctor_selection", res.get("ui_data", {})
        
    if any(p in clean for p in ("cancel appointment", "cancel my appointment", "appointment cancel", "cancel karna")):
        res = tool_get_patient_appointments(session, authorization)
        if res.get("status") == "unauthorized":
            return res["message"], "waiting_for_input", {}
        appts = res.get("appointments") or []
        if not appts:
            return "You have no scheduled appointments to cancel.", "waiting_for_input", {"appointments": []}
        if appt_id:
            prop = tool_propose_cancel_appointment(session, appt_id, authorization)
            if prop.get("valid"):
                return f"{prop['summary']} Please reply 'Yes' to confirm cancellation or 'No' to keep it.", "waiting_for_confirmation", prop.get("ui_data", {})
        return "Which appointment would you like to cancel?", "show_appointments", res.get("ui_data", {})
        
    if any(p in clean for p in ("reschedule", "change time", "change appointment", "waqt tabdeel", "time badal")):
        res = tool_get_patient_appointments(session, authorization)
        if res.get("status") == "unauthorized":
            return res["message"], "waiting_for_input", {}
        appts = res.get("appointments") or []
        if not appts:
            return "You have no appointments to reschedule. Would you like to book a new one?", "waiting_for_input", {}
        return "Which appointment would you like to reschedule?", "show_appointments", res.get("ui_data", {})
        
    if any(p in clean for p in ("my appointment", "show appointment", "check appointment", "view appointment", "what is my appointment", "mera appointment")):
        res = tool_get_patient_appointments(session, authorization)
        if res.get("status") == "unauthorized":
            return res["message"], "waiting_for_input", {}
        appts = res.get("appointments") or []
        if not appts:
            return "You have no upcoming appointments.", "waiting_for_input", {"appointments": []}
        return f"You have {len(appts)} upcoming appointments:", "show_appointments", res.get("ui_data", {})
        
    if any(p in clean for p in ("hour", "timing", "open", "close", "weekend", "fee", "cost", "price", "charge", "fees")):
        info = tool_get_clinic_info(session)
        return (
            f"MediBook Central Clinic Info:\n"
            f"Working Hours: {info['working_hours']}\n"
            f"Consultation Fees: {info['consultation_fees']}\n"
            f"Location: {info['location']}"
        ), "waiting_for_input", {}

    # Option selection handling (doctor or slot clicked)
    if opt_id:
        docs = session.get("candidate_doctors") or []
        if not docs:
            tool_list_doctors(session)
            docs = session.get("candidate_doctors") or []

        doc = find_doctor_by_id(opt_id, docs)
        if doc:
            res_avail = tool_get_doctor_availability(session, opt_id)
            return f"You selected {doc['name']}. Please pick an available time slot:", "waiting_for_slot_selection", res_avail.get("ui_data", {})
            
        sel_doc = session.get("selected_doctor")
        if not sel_doc and docs:
            sel_doc = docs[0]
            session["selected_doctor"] = sel_doc

        if sel_doc:
            prop = tool_propose_book_appointment(session, sel_doc["doctor_id"], opt_id, auth=authorization)
            if prop.get("valid"):
                return f"{prop['summary']} Please reply 'Yes' or 'Confirm' to complete your booking.", "waiting_for_confirmation", prop.get("ui_data", {})
            else:
                return f"Could not select slot: {prop.get('reason')}", "waiting_for_slot_selection", session.get("last_ui_data", {})


    # Default to symptom triage retrieval tool
    if len(clean) > 3 and clean not in ("hi", "hello", "hey"):
        knowledge = tool_retrieve_medical_knowledge(session, message)
        if knowledge.get("needs_emergency_care"):
            return EMERGENCY_ALERT, "emergency_redirect", {}
        bot_text = knowledge.get("bot_recommendation") or f"Recommended specialty: {knowledge.get('recommended_specialty')}."
        return bot_text, "waiting_for_input", knowledge.get("ui_data", {})

    return "Hi! I'm MediBook AI. How can I help you today? You can book an appointment, check clinic hours, or describe symptoms.", "waiting_for_input", {}


def handle_message(
    *,
    conversation_id: Optional[str],
    patient_id: Optional[str],
    message: str,
    language: str,
    authorization: Optional[str],
) -> dict[str, Any]:
    """Primary entrypoint: deterministic safety checks followed by LLM agent loop with tool-calling."""
    conv_id = conversation_id or str(uuid4())
    
    session = get_session(conv_id)
    if not session:
        session = new_session(conv_id, patient_id)
        
    if patient_id:
        session["patient_id"] = patient_id

    now_ts = _utc_now()
    append_msg(session, "user", message, now_ts)

    # -----------------------------------------------------------------------
    # Rule 1: Immediate Emergency Guard (Deterministic, unconditional)
    # -----------------------------------------------------------------------
    if is_emergency(message):
        bot = EMERGENCY_ALERT
        action = "emergency_redirect"
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
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }

    # -----------------------------------------------------------------------
    # Rule 2: Explicit Confirmation Gate for Pending Propose Actions
    # -----------------------------------------------------------------------
    pending = session.get("pending_action")
    if pending and pending.get("status") == "proposed":
        if is_confirm(message):
            exec_res = tool_execute_confirmed_action(session, authorization)
            if exec_res.get("success"):
                bot = exec_res["message"]
                action = "appointment_booked" if pending.get("action_type") == "book" else "waiting_for_input"
                ui_data = exec_res.get("ui_data", {})
            else:
                bot = f"Could not complete action: {exec_res.get('reason')}"
                action = "waiting_for_confirmation"
                ui_data = session.get("last_ui_data", {})
            
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
        elif is_decline(message) or message.lower().strip() == "change":
            session["pending_action"] = None
            res_docs = tool_list_doctors(session)
            bot = "No problem. I have cancelled that proposal. Please select a doctor or time below:"
            action = "waiting_for_doctor_selection"
            ui_data = res_docs.get("ui_data", {})
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

    # -----------------------------------------------------------------------
    # Rule 3: Off-Topic / Hostile Input Guard
    # -----------------------------------------------------------------------
    if is_off_topic_or_hostile(message):
        bot = "I didn't understand that. I am your MediBook AI assistant. I can help you book, reschedule, or cancel appointments, or assist with health symptoms and clinic questions. How can I help you today?"
        action = "waiting_for_input"
        ui_data = session.get("last_ui_data", {})
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

    # -----------------------------------------------------------------------
    # Rule 4: LLM Agent Loop (Groq tool-calling) with Offline Fallback
    # -----------------------------------------------------------------------
    bot = ""
    action = "waiting_for_input"
    ui_data = session.get("last_ui_data", {})

    try:
        # Build prompt message history
        messages_payload = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
        for m in session["messages"]:
            messages_payload.append({"role": m.role, "content": m.message})

        response_message = groq_client.complete_with_tools(
            messages=messages_payload,
            tools=TOOLS_SPEC,
            tool_choice="auto",
            temperature=0.2,
        )

        tool_calls = getattr(response_message, "tool_calls", None)
        if tool_calls:
            messages_payload.append(response_message)
            for tool_call in tool_calls:
                fn_name = tool_call.function.name
                fn_args_raw = tool_call.function.arguments or "{}"
                try:
                    fn_args = json.loads(fn_args_raw)
                except Exception:
                    fn_args = {}

                tool_result = _execute_tool_by_name(fn_name, fn_args, session, authorization)
                if isinstance(tool_result, dict) and "ui_data" in tool_result:
                    ui_data.update(tool_result["ui_data"])

                messages_payload.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result),
                })

            follow_up = groq_client.complete_with_tools(
                messages=messages_payload,
                tools=TOOLS_SPEC,
                tool_choice="auto",
                temperature=0.2,
            )
            bot = getattr(follow_up, "content", "") or "How else can I assist you today?"
        else:
            bot = getattr(response_message, "content", "") or "How can I help you today?"

    except groq_client.LLMError:
        # Fallback to deterministic agent tool dispatch when LLM API key is not present / offline
        bot, action, ui_data = _run_agent_fallback(message, session, authorization)
    except Exception as exc:
        logger.warning("Agent loop error, running fallback: %s", exc)
        bot, action, ui_data = _run_agent_fallback(message, session, authorization)

    # Determine action state for UI
    if session.get("pending_action"):
        action = "waiting_for_confirmation"
    elif "doctors" in ui_data:
        action = "waiting_for_doctor_selection"
    elif "slots" in ui_data:
        action = "waiting_for_slot_selection"
    elif "appointments" in ui_data:
        action = "show_appointments"

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
