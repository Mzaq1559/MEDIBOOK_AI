"""LLM tool schemas and execution engine for MediBook AI agentic chat.

Tools are exposed as Groq/OpenAI function-calling JSON schemas. The model
chooses which tools to call; this module validates arguments and talks to
the clinic backend. Return types are documented on each tool (Groq schemas
do not have a separate return-type field).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

from app import backend_client
from app.chatbot_slots import (
    doctors_ui_data,
    fetch_doctor_slots,
    find_doctor_by_id,
    find_slot_by_ts,
    format_appointment_for_ui,
    match_slot_from_text,
    slots_ui_data,
    today_karachi,
)
from app.rag.metrics import metrics
from integrations import google_calendar, n8n_webhook, reminders

logger = logging.getLogger("medibook.ai.tools")

import time
import uuid

_PROPOSALS = {}

def _create_proposal(session: dict[str, Any], p_type: str, patient_id: str, data: dict[str, Any], summary: str) -> str:
    pid = str(uuid.uuid4())
    _PROPOSALS[pid] = {
        "id": pid,
        "type": p_type,
        "patient_id": patient_id,
        "session_id": session.get("conversation_id"),
        "data": data,
        "summary": summary,
        "created_at": time.time(),
        "used": False
    }
    return pid


LOGIN_REQUIRED = "Please sign in so I can access your patient record and appointments."

# ---------------------------------------------------------------------------
# JSON schemas the LLM can call (Groq function-calling format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_patient_appointments",
            "description": (
                "Fetch upcoming appointments for a patient. "
                "Returns List[Appointment] with id, doctor, time, clinic, and status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "Patient UUID from the authenticated session",
                    }
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_reschedule_appointment",
            "description": (
                "Move an existing appointment to a new date/time. "
                "Confirm with the patient before calling. Returns bool success."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "Appointment UUID to reschedule",
                    },
                    "new_datetime": {
                        "type": "string",
                        "description": "New slot as ISO-8601 timestamp or availability label",
                    },
                },
                "required": ["appointment_id", "new_datetime"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_cancel_appointment",
            "description": (
                "Cancel an existing appointment. Confirm with the patient before calling. "
                "Returns bool success."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "Appointment UUID to cancel",
                    }
                },
                "required": ["appointment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_book_appointment",
            "description": (
                "Create a new appointment. Confirm doctor, time, and symptoms with the "
                "patient before calling. Returns Appointment."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "Patient UUID from the authenticated session",
                    },
                    "doctor_id": {
                        "type": "string",
                        "description": "Doctor UUID to book with",
                    },
                    "datetime": {
                        "type": "string",
                        "description": "Slot as ISO-8601 timestamp or availability label",
                    },
                    "symptoms": {
                        "type": "string",
                        "description": "Brief symptom description for the visit",
                    },
                },
                "required": ["patient_id", "doctor_id", "datetime", "symptoms"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_confirmed_action",
            "description": (
                "Executes a previously proposed action. Call this ONLY after the user explicitly "
                "confirms the proposal summary."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "proposal_id": {
                        "type": "string",
                        "description": "The ID of the proposal to execute",
                    }
                },
                "required": ["proposal_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_doctors_by_specialty",
            "description": (
                "List available doctors for a medical specialty "
                "(e.g. Cardiologist, ENT Specialist, General Physician). "
                "Returns List[Doctor]."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "specialty": {
                        "type": "string",
                        "description": "Specialty name to filter doctors",
                    }
                },
                "required": ["specialty"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_availability",
            "description": (
                "List open time slots for a doctor on a given date. "
                "Returns List[str] of slot labels / ISO timestamps."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": "Doctor UUID",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD (Asia/Karachi). Use today if the user did not specify.",
                    },
                },
                "required": ["doctor_id", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_info",
            "description": (
                "Fetch the authenticated patient's profile (name, contact, allergies). "
                "Returns Patient. Never use this for another person."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "Patient UUID from the authenticated session",
                    }
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_medical_knowledge",
            "description": (
                "Evaluate patient symptoms or answer medical questions. "
                "Retrieves clinical triage guidelines and recommends a specialist. "
                "Returns TriageResult with bot_message, urgency, and specialty."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symptoms": {
                        "type": "string",
                        "description": "The patient's symptom description or medical question",
                    }
                },
                "required": ["symptoms"],
            },
        },
    },
]

REQUIRED_PARAMS: dict[str, list[str]] = {
    "get_patient_appointments": ["patient_id"],
    "propose_reschedule_appointment": ["appointment_id", "new_datetime"],
    "execute_confirmed_action": ["proposal_id"],
    "propose_cancel_appointment": ["appointment_id"],
    "propose_book_appointment": ["patient_id", "doctor_id", "datetime", "symptoms"],
    "get_doctors_by_specialty": ["specialty"],
    "get_availability": ["doctor_id", "date"],
    "get_patient_info": ["patient_id"],
    "retrieve_medical_knowledge": ["symptoms"],
}

WRITE_TOOLS = frozenset({"propose_book_appointment", "propose_reschedule_appointment", "propose_cancel_appointment", "execute_confirmed_action"})


def tools_prompt_listing() -> str:
    """Human-readable tool list for the system prompt."""
    lines: list[str] = []
    for spec in TOOL_DEFINITIONS:
        fn = spec["function"]
        params = fn["parameters"].get("properties") or {}
        param_sig = ", ".join(f"{name}: {meta.get('type', 'string')}" for name, meta in params.items())
        lines.append(f"- {fn['name']}({param_sig}): {fn['description']}")
    return "\n".join(lines)


def build_system_prompt() -> str:
    return (
        "You are an experienced healthcare receptionist for Pakistani clinics. "
        "You sound like a real person at the front desk, not a form or a report.\n"
        "\n"
        "Communication style:\n"
        "- Use the patient's first name naturally (Ali, Fatima, etc.) when you know it.\n"
        "- Keep responses SHORT: 1-2 sentences max per message.\n"
        "- Sound warm and professional, not robotic.\n"
        "- Ask a follow-up question when it helps (how they feel, when they can come in).\n"
        "- Reference their medical history when it is relevant. Do not dump the whole chart.\n"
        "- Mix Urdu and English lightly when the patient does, or when language preference is Urdu.\n"
        "\n"
        "Tone examples:\n"
        "- Greeting: Hi {name}! How can I help you today?\n"
        "- Appointment lookup: You have an appointment with {doctor} on {date}.\n"
        "- Medical reference: I see you had {symptom} last time. How's that now?\n"
        "- Booking: Let me find a cardiologist for you, {name}.\n"
        "- Confirmation: Perfect! I've scheduled you with {doctor} on {date}.\n"
        "- Empathy: Sorry to hear about {symptom}. Let me connect you with {specialist}.\n"
        "- Cancel: Sure, I'll cancel that appointment with {doctor}.\n"
        "\n"
        "Bad vs good:\n"
        "- Bad: I see you have one upcoming appointment with details as follows...\n"
        "- Good: Hi Ali! You have an appointment with Dr. Tariq on Aug 27th at 10 AM.\n"
        "- Bad: Please inform me of your preferred time slot\n"
        "- Good: When works best for you?\n"
        "- Bad: Would you like to reschedule or cancel?\n"
        "- Good: Want to reschedule instead?\n"
        "- Bad: Patient Name: Ali Khan / Last Visit: Dr. Tariq Mahmood / Date: 27 August 2026\n"
        "- Good: Hi Ali! How are you feeling since your last visit with Dr. Tariq?\n"
        "\n"
        "Never write labeled fields like 'Doctor:', 'Date & Time:', 'Clinic:', or 'Patient Name:'. "
        "Do not use markdown symbols such as ** or ##. Plain conversational sentences only.\n"
        "\n"
        "Your role:\n"
        "- Help patients book appointments\n"
        "- Use retrieve_medical_knowledge when a patient describes symptoms or asks a medical question. Use the tool's result to advise them.\n"
        "- Reschedule or cancel appointments\n"
        "- Answer questions about this clinic\n"
        "\n"
        f"Available tools:\n{tools_prompt_listing()}\n"
        "\n"
        "When the user asks something:\n"
        "1. Determine which tools are needed\n"
        "2. Call appropriate tools\n"
        "3. Answer in one or two warm sentences using the tool results\n"
        "\n"
        "Rules:\n"
        "- Use tools for live clinic data. Do not invent doctors, slots, or appointment IDs.\n"
        "- For booking, reschedule, and cancel: call propose_X first, state the summary, wait for "
        "explicit affirmative text, then call execute_confirmed_action.\n"
        "- If the patient is not logged in, ask them to sign in instead of guessing IDs.\n"
        "- You only help with this clinic's appointments and information.\n"
        "- Do NOT use markdown symbols (**) in responses.\n"
    )


def _session_patient_id(session: dict[str, Any], requested: Optional[str]) -> Optional[str]:
    bound = session.get("patient_id")
    if bound:
        return str(bound)
    if requested:
        return str(requested)
    return None


def _require_auth(auth: Optional[str]) -> Optional[str]:
    if not auth or not str(auth).lower().startswith("bearer "):
        return LOGIN_REQUIRED
    return None


def _booking_error(exc: backend_client.BackendError) -> str:
    if exc.error_code == "INVALID_TIME":
        return "That appointment time is not valid. Please pick another available slot."
    if exc.error_code == "SLOT_UNAVAILABLE":
        return "That time slot is not available. Please pick another time."
    if exc.error_code == "DOUBLE_BOOKING":
        return "You already have an appointment at that time. Would you like a different slot?"
    if exc.status_code in (401, 403):
        return LOGIN_REQUIRED
    return exc.message or "I could not complete the request. Please try again."


def _merge_ui(session: dict[str, Any], ui: dict[str, Any]) -> dict[str, Any]:
    session.setdefault("last_ui_data", {}).update(ui)
    return ui


def _resolve_slot(doctor: dict[str, Any], when: str) -> Optional[dict[str, Any]]:
    slot = find_slot_by_ts(when, doctor) if when else None
    if not slot:
        slot = match_slot_from_text(when, doctor)
    if not slot:
        needle = (when or "").lower()
        for s in doctor.get("availability_slots") or doctor.get("slots") or []:
            if needle in (s.get("label") or "").lower() or when in (s.get("timestamp") or ""):
                return s
    return slot


def _load_doctor(session: dict[str, Any], doctor_id: str) -> Optional[dict[str, Any]]:
    candidates = session.get("candidate_doctors") or []
    doc = find_doctor_by_id(doctor_id, candidates)
    if doc:
        return doc
    all_docs = backend_client.list_doctors() or []
    enriched = fetch_doctor_slots(all_docs)
    session["candidate_doctors"] = enriched
    return find_doctor_by_id(doctor_id, enriched)


def _find_owned_appointment(
    session: dict[str, Any],
    appointment_id: str,
    patient_id: str,
    auth: str,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    appts = session.get("patient_appointments") or backend_client.fetch_patient_appointments(
        patient_id, auth
    )
    session["patient_appointments"] = appts
    appt = next(
        (
            a
            for a in appts
            if str(a.get("id") or "") == appointment_id
            or str(a.get("appointment_id") or "") == appointment_id
        ),
        None,
    )
    if not appt:
        return None, "Appointment not found for this patient."
    owner = appt.get("patient_id")
    if owner and str(owner) != str(patient_id):
        return None, "Appointment not found or does not belong to authenticated patient."
    return appt, None


def tool_get_patient_appointments(
    session: dict[str, Any],
    args: dict[str, Any],
    auth: Optional[str],
) -> dict[str, Any]:
    metrics.inc("agent_tool_calls_total")
    auth_err = _require_auth(auth)
    if auth_err:
        return {"ok": False, "error": auth_err, "appointments": []}
    patient_id = _session_patient_id(session, args.get("patient_id"))
    if not patient_id:
        return {"ok": False, "error": LOGIN_REQUIRED, "appointments": []}
    appts = backend_client.fetch_patient_appointments(patient_id, auth or "")
    session["patient_appointments"] = appts
    formatted = [format_appointment_for_ui(a) for a in appts]
    ui = _merge_ui(session, {"appointments": formatted})
    return {
        "ok": True,
        "appointments": formatted,
        "count": len(formatted),
        "ui_data": ui,
    }


def tool_get_doctors_by_specialty(
    session: dict[str, Any],
    args: dict[str, Any],
    auth: Optional[str],
) -> dict[str, Any]:
    metrics.inc("agent_tool_calls_total")
    specialty = str(args.get("specialty") or "").strip()
    docs = backend_client.list_doctors(specialization=specialty or None) or []
    if not docs:
        docs = backend_client.list_doctors() or []
    enriched = fetch_doctor_slots(docs)
    session["candidate_doctors"] = enriched
    ui = _merge_ui(session, {"doctors": doctors_ui_data(enriched)})
    summaries = [
        {
            "doctor_id": d["doctor_id"],
            "name": d["name"],
            "specialization": d["specialization"],
            "clinic_name": d["clinic_name"],
            "consultation_fee": d["consultation_fee"],
            "available_slots": [s.get("label") for s in (d.get("availability_slots") or [])],
        }
        for d in enriched
    ]
    return {"ok": True, "doctors": summaries, "count": len(summaries), "ui_data": ui}


def tool_get_availability(
    session: dict[str, Any],
    args: dict[str, Any],
    auth: Optional[str],
) -> dict[str, Any]:
    metrics.inc("agent_tool_calls_total")
    doctor_id = str(args.get("doctor_id") or "")
    date = str(args.get("date") or today_karachi())
    avail = backend_client.get_availability(doctor_id, date, next_days=3)
    labels: list[str] = []
    timestamps: list[str] = []
    slots_for_ui: list[dict[str, Any]] = []
    if avail:
        for day in avail.get("availability") or []:
            date_label = day.get("date", date)
            for slot in day.get("slots") or []:
                if not slot.get("available"):
                    continue
                ts = slot.get("timestamp") or ""
                label = f"{date_label} at {slot.get('time', '')}"
                labels.append(label)
                if ts:
                    timestamps.append(ts)
                slots_for_ui.append(
                    {
                        "date": date_label,
                        "time": slot.get("time", ""),
                        "timestamp": ts,
                        "label": label,
                    }
                )
    doc = _load_doctor(session, doctor_id)
    if not labels and doc:
        for s in doc.get("availability_slots") or doc.get("slots") or []:
            labels.append(s.get("label") or s.get("timestamp") or "")
            if s.get("timestamp"):
                timestamps.append(s["timestamp"])
            slots_for_ui.append(s)
        doc["slots"] = slots_for_ui or doc.get("slots") or []
        ui = _merge_ui(session, {"slots": slots_ui_data(doc)})
    else:
        if doc:
            doc["availability_slots"] = slots_for_ui
            doc["slots"] = slots_for_ui
            session["selected_doctor"] = doc
        ui = _merge_ui(session, {"slots": slots_for_ui})
    return {
        "ok": True,
        "doctor_id": doctor_id,
        "date": date,
        "slots": labels,
        "timestamps": timestamps,
        "ui_data": ui,
    }


def tool_get_patient_info(
    session: dict[str, Any],
    args: dict[str, Any],
    auth: Optional[str],
) -> dict[str, Any]:
    metrics.inc("agent_tool_calls_total")
    auth_err = _require_auth(auth)
    if auth_err:
        return {"ok": False, "error": auth_err}
    patient_id = _session_patient_id(session, args.get("patient_id"))
    if not patient_id:
        return {"ok": False, "error": LOGIN_REQUIRED}
    info = backend_client.get_patient_info(patient_id, auth or "")
    if not info:
        return {"ok": False, "error": "Could not load patient profile."}
    safe = {
        "patient_id": str(info.get("patient_id") or patient_id),
        "name": info.get("name"),
        "phone": info.get("phone"),
        "age": info.get("age"),
        "gender": info.get("gender"),
        "allergies": info.get("allergies") or [],
        "medical_conditions": info.get("medical_conditions") or [],
    }
    return {"ok": True, "patient": safe}


def tool_propose_book_appointment(
    session: dict[str, Any],
    args: dict[str, Any],
    auth: Optional[str],
) -> dict[str, Any]:
    metrics.inc("agent_tool_calls_total")
    auth_err = _require_auth(auth)
    if auth_err:
        return {"ok": False, "error": auth_err}
    patient_id = _session_patient_id(session, args.get("patient_id"))
    if not patient_id:
        return {"ok": False, "error": LOGIN_REQUIRED}
    doctor_id = str(args.get("doctor_id") or "")
    when = str(args.get("datetime") or "")
    symptoms = str(args.get("symptoms") or "General Consultation")[:500]
    doc = _load_doctor(session, doctor_id)
    if not doc:
        return {"ok": False, "error": f"Doctor '{doctor_id}' not found."}
    slot = _resolve_slot(doc, when)
    if not slot:
        available = [s.get("label") for s in (doc.get("availability_slots") or [])]
        return {
            "ok": False,
            "error": f"Requested slot '{when}' is unavailable for {doc['name']}. Available slots: {available}",
        }
    payload = {
        "patient_id": patient_id,
        "doctor_id": doc["doctor_id"],
        "appointment_time": slot["timestamp"],
        "symptoms_reported": symptoms,
        "urgency_level": session.get("urgency_level") or "normal",
        "appointment_type": "in_person",
    }
    
    summary = f"Book appointment with {doc['name']} on {slot.get('label') or slot.get('timestamp')}."
    pid = _create_proposal(session, "book", patient_id, {"payload": payload, "doc": doc, "slot": slot, "symptoms": symptoms}, summary)
    
    ui = _merge_ui(
        session,
        {"booking": {"doctor": doc, "selectedSlot": slot.get("label"), "isConfirmed": False}},
    )
    return {"ok": True, "proposal_id": pid, "summary": summary, "ui_data": ui}


def tool_propose_reschedule_appointment(
    session: dict[str, Any],
    args: dict[str, Any],
    auth: Optional[str],
) -> dict[str, Any]:
    metrics.inc("agent_tool_calls_total")
    auth_err = _require_auth(auth)
    if auth_err:
        return {"ok": False, "error": auth_err, "success": False}
    patient_id = _session_patient_id(session, None)
    if not patient_id:
        return {"ok": False, "error": LOGIN_REQUIRED, "success": False}
    appointment_id = str(args.get("appointment_id") or "")
    new_datetime = str(args.get("new_datetime") or "")
    appt, err = _find_owned_appointment(session, appointment_id, patient_id, auth or "")
    if err:
        return {"ok": False, "error": err, "success": False}
    doc_id = str((appt or {}).get("doctor_id") or "")
    doc = _load_doctor(session, doc_id) if doc_id else None
    if not doc:
        return {"ok": False, "error": "Could not verify doctor availability for reschedule.", "success": False}
    slot = _resolve_slot(doc, new_datetime)
    if not slot:
        available = [s.get("label") for s in (doc.get("availability_slots") or [])]
        return {
            "ok": False,
            "error": f"Requested slot '{new_datetime}' is not available. Available slots: {available}",
            "success": False,
        }
        
    summary = f"Reschedule appointment with {doc['name']} to {slot.get('label') or slot.get('timestamp')}."
    pid = _create_proposal(session, "reschedule", patient_id, {"appointment_id": appointment_id, "slot": slot, "appt": appt, "doc_id": doc_id, "doc": doc}, summary)
    
    ui = _merge_ui(
        session,
        {"reschedule": {"doctor": doc, "oldSlot": (appt or {}).get("appointment_time"), "newSlot": slot.get("label")}},
    )
    return {"ok": True, "success": True, "proposal_id": pid, "summary": summary, "ui_data": ui}


def tool_propose_cancel_appointment(
    session: dict[str, Any],
    args: dict[str, Any],
    auth: Optional[str],
) -> dict[str, Any]:
    metrics.inc("agent_tool_calls_total")
    auth_err = _require_auth(auth)
    if auth_err:
        return {"ok": False, "error": auth_err, "success": False}
    patient_id = _session_patient_id(session, None)
    if not patient_id:
        return {"ok": False, "error": LOGIN_REQUIRED, "success": False}
    appointment_id = str(args.get("appointment_id") or "")
    _appt, err = _find_owned_appointment(session, appointment_id, patient_id, auth or "")
    if err:
        return {"ok": False, "error": err, "success": False}
        
    doc_id = str((_appt or {}).get("doctor_id") or "")
    doc = _load_doctor(session, doc_id) if doc_id else None
    
    summary = f"Cancel appointment{' with ' + doc['name'] if doc else ''}."
    pid = _create_proposal(session, "cancel", patient_id, {"appointment_id": appointment_id}, summary)
        
    return {"ok": True, "success": True, "proposal_id": pid, "summary": summary}




def tool_execute_confirmed_action(
    session: dict[str, Any],
    args: dict[str, Any],
    auth: Optional[str],
) -> dict[str, Any]:
    metrics.inc("agent_tool_calls_total")
    proposal_id = str(args.get("proposal_id") or "")
    proposal = _PROPOSALS.get(proposal_id)
    
    if not proposal:
        return {"ok": False, "error": "Proposal not found or invalid ID."}
        
    if proposal.get("used"):
        return {"ok": False, "error": "This proposal has already been executed."}
        
    if time.time() - proposal.get("created_at", 0) > 300: # 5 minutes TTL
        return {"ok": False, "error": "This proposal has expired. Please propose the action again."}
        
    patient_id = _session_patient_id(session, None)
    if not patient_id or proposal.get("patient_id") != patient_id:
        return {"ok": False, "error": "Patient ID mismatch. Cannot execute this proposal."}
        
    if proposal.get("session_id") != session.get("conversation_id"):
        return {"ok": False, "error": "Session mismatch. Cannot execute this proposal."}

    proposal["used"] = True
    p_type = proposal["type"]
    data = proposal["data"]
    
    if p_type == "book":
        payload = data["payload"]
        doc = data["doc"]
        slot = data["slot"]
        symptoms = data["symptoms"]
        
        try:
            created = backend_client.create_appointment(payload, auth or "")
        except backend_client.BackendError as exc:
            return {"ok": False, "error": _booking_error(exc)}
            
        appt_id = created.get("appointment_id") or created.get("id")
        session["appointment_booked"] = appt_id
        session["status"] = "completed"
        
        try:
            cal_p = {
                "appointment_id": str(appt_id),
                "doctor_name": doc["name"],
                "patient_name": "Patient",
                "clinic_name": doc["clinic_name"],
                "clinic_address": doc["clinic_address"],
                "appointment_time": slot["timestamp"],
                "duration_minutes": 30,
                "symptoms_reported": symptoms,
            }
            cid = google_calendar.create_calendar_event(cal_p)
            if cid:
                session["google_calendar_event_id"] = cid
            n8n_p = dict(cal_p)
            n8n_p["patient_id"] = patient_id
            n8n_p["doctor_id"] = doc["doctor_id"]
            n8n_p["clinic_id"] = created.get("clinic_id")
            n8n_p["urgency_level"] = payload["urgency_level"]
            n8n_p["google_calendar_event_id"] = session.get("google_calendar_event_id")
            n8n_webhook.dispatch_appointment_created(n8n_p)
        except Exception as exc:
            logger.warning("Integration sync after booking failed: %s", exc)
            
        appointment = {
            "appointment_id": str(appt_id),
            "doctor_id": doc["doctor_id"],
            "doctor_name": doc["name"],
            "datetime": slot.get("label") or slot.get("timestamp"),
            "symptoms": symptoms,
            "status": created.get("status") or "scheduled",
        }
        ui = _merge_ui(
            session,
            {"booking": {"doctor": doc, "selectedSlot": slot.get("label"), "isConfirmed": True}},
        )
        return {"ok": True, "appointment": appointment, "ui_data": ui, "summary": "Booking executed."}
        
    elif p_type == "reschedule":
        appointment_id = data["appointment_id"]
        slot = data["slot"]
        appt = data.get("appt")
        doc_id = data.get("doc_id")
        
        try:
            updated = backend_client.reschedule_appointment(appointment_id, slot["timestamp"], auth or "")
        except backend_client.BackendError as exc:
            return {"ok": False, "error": _booking_error(exc), "success": False}
            
        cal_id = session.get("google_calendar_event_id") or (updated or {}).get("google_calendar_event_id")
        if cal_id:
            try:
                google_calendar.update_calendar_event(cal_id, slot["timestamp"])
            except Exception:
                pass
        try:
            rm = reminders.calculate_reminder_times(slot["timestamp"]) if slot.get("timestamp") else {}
            n8n_webhook.dispatch_appointment_rescheduled(
                {
                    "appointment_id": appointment_id,
                    "patient_id": patient_id,
                    "doctor_id": doc_id,
                    "new_appointment_time": slot["timestamp"],
                    "previous_appointment_time": (appt or {}).get("appointment_time"),
                    "new_reminder_time_1": rm.get("reminder_time_1"),
                    "new_reminder_time_2": rm.get("reminder_time_2"),
                }
            )
        except Exception:
            pass
            
        ui = _merge_ui(
            session,
            {"reschedule": {"doctor": data.get("doc"), "oldSlot": (appt or {}).get("appointment_time"), "newSlot": slot.get("label"), "isConfirmed": True}},
        )
        return {"ok": True, "success": True, "new_datetime": slot.get("label"), "ui_data": ui, "summary": "Reschedule executed."}

    elif p_type == "cancel":
        appointment_id = data["appointment_id"]
        try:
            backend_client.cancel_appointment(appointment_id, auth or "")
        except backend_client.BackendError as exc:
            return {"ok": False, "error": _booking_error(exc), "success": False}
        return {"ok": True, "success": True, "summary": "Cancellation executed."}

    return {"ok": False, "error": "Unknown proposal type."}

def tool_retrieve_medical_knowledge(
    session: dict[str, Any],
    args: dict[str, Any],
    auth: Optional[str],
) -> dict[str, Any]:
    metrics.inc("agent_tool_calls_total")
    symptoms = str(args.get("symptoms") or "").strip()
    
    if not symptoms:
        return {"ok": False, "error": "Symptoms are required for medical knowledge retrieval."}

    from app.rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    
    history = []
    for m in session.get("messages", [])[-4:]:
        role = getattr(m, "role", "user")
        message = getattr(m, "message", "")
        history.append(f"{role}: {message}")
    context = "\n".join(history)
    
    result = pipeline.triage_symptoms(
        message=symptoms,
        conversation_context=context,
        request_id=session.get("conversation_id"),
    )
    
    return {
        "ok": True,
        "bot_message": result.bot_message,
        "specialty": result.specialty,
        "urgency_level": result.urgency_level,
        "needs_emergency_care": result.needs_emergency_care,
        "confidence": result.confidence,
    }


HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "get_patient_appointments": tool_get_patient_appointments,
    "propose_reschedule_appointment": tool_propose_reschedule_appointment,
    "propose_cancel_appointment": tool_propose_cancel_appointment,
    "propose_book_appointment": tool_propose_book_appointment,
    "execute_confirmed_action": tool_execute_confirmed_action,
    "get_doctors_by_specialty": tool_get_doctors_by_specialty,
    "get_availability": tool_get_availability,
    "get_patient_info": tool_get_patient_info,
    "retrieve_medical_knowledge": tool_retrieve_medical_knowledge,
}


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def execute_tool(
    name: str,
    arguments: Any,
    session: dict[str, Any],
    authorization: Optional[str],
) -> dict[str, Any]:
    """Validate parameters, dispatch to the backend, and return JSON-safe results."""
    handler = HANDLERS.get(name)
    if not handler:
        return {"ok": False, "error": f"Unknown tool '{name}'"}
    args = _parse_arguments(arguments)
    required = REQUIRED_PARAMS.get(name) or []
    if name in ("get_patient_appointments", "propose_book_appointment", "get_patient_info"):
        if not args.get("patient_id") and session.get("patient_id"):
            args["patient_id"] = str(session["patient_id"])
    if name == "get_availability" and not args.get("date"):
        args["date"] = today_karachi()
    missing = [p for p in required if args.get(p) in (None, "")]
    if missing:
        return {"ok": False, "error": f"Missing required parameters: {', '.join(missing)}"}
    logger.info("Executing tool=%s", name)
    try:
        result = handler(session, args, authorization)
    except Exception as exc:
        logger.exception("Tool %s failed: %s", name, exc)
        return {"ok": False, "error": "Tool execution failed. Please try again."}
    if isinstance(result, dict) and "ui_data" in result:
        _merge_ui(session, result.get("ui_data") or {})
    return result
