"""Tool implementations for the MediBook AI agentic system."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

from app import backend_client
from app.chatbot_slots import (
    doctors_ui_data,
    fetch_doctor_slots,
    find_doctor_by_id,
    find_slot_by_ts,
    format_appointment_for_ui,
    match_slot_from_text,
    slots_ui_data,
)
from app.rag.config import rag_settings
from app.rag.metrics import metrics
from app.symptom_triage import EMERGENCY_ALERT, follow_ups_for, is_emergency, triage
from integrations import google_calendar, n8n_webhook, reminders

logger = logging.getLogger("medibook.ai.tools")

LOGIN_REQ_BOOK = "To confirm this appointment you need to be logged in. Please sign in, then confirm."
LOGIN_REQ_RESCHEDULE = "To reschedule you need to be logged in. Please sign in, then confirm."
LOGIN_REQ_CANCEL = "Please log in to cancel appointments."
LOGIN_REQ_LOOKUP = "Please log in to view your appointments."


def _booking_error(exc: backend_client.BackendError, is_reschedule: bool = False) -> str:
    c = exc.error_code
    if c == "INVALID_TIME":
        return "That appointment time is not valid. Please pick another available slot."
    if c == "SLOT_UNAVAILABLE":
        return "That time slot is not available. Please pick another time."
    if c == "DOUBLE_BOOKING":
        return "You already have an appointment at that time. Would you like a different slot?"
    if exc.status_code in (401, 403):
        return LOGIN_REQ_RESCHEDULE if is_reschedule else LOGIN_REQ_BOOK
    return exc.message or "I could not complete the request. Please try again."


# ---------------------------------------------------------------------------
# Read-Only Tools
# ---------------------------------------------------------------------------

def tool_list_doctors(session: dict[str, Any], specialty: Optional[str] = None) -> dict[str, Any]:
    """List available doctors and candidate slots."""
    metrics.inc("agent_tool_calls_total")
    docs = backend_client.list_doctors(specialization=specialty) or backend_client.list_doctors()
    enriched = fetch_doctor_slots(docs, next_days=3)
    session["candidate_doctors"] = enriched
    
    ui = {"doctors": doctors_ui_data(enriched)}
    session["last_ui_data"].update(ui)
    
    doctor_summaries = []
    for d in enriched:
        slots_count = len(d.get("availability_slots") or [])
        doctor_summaries.append(
            f"Doctor ID: {d['doctor_id']}, Name: {d['name']}, Specialization: {d['specialization']}, Clinic: {d['clinic_name']}, Fee: Rs. {d['consultation_fee']}, Available Slots: {slots_count}"
        )
    
    return {
        "status": "success",
        "doctor_count": len(enriched),
        "doctors": doctor_summaries,
        "ui_data": ui
    }


def tool_get_doctor_availability(session: dict[str, Any], doctor_id: str, date: Optional[str] = None) -> dict[str, Any]:
    """Get available slots for a given doctor."""
    metrics.inc("agent_tool_calls_total")
    candidates = session.get("candidate_doctors") or []
    doc = find_doctor_by_id(doctor_id, candidates)
    
    if not doc:
        all_docs = backend_client.list_doctors()
        enriched = fetch_doctor_slots(all_docs)
        session["candidate_doctors"] = enriched
        doc = find_doctor_by_id(doctor_id, enriched)
        
    if not doc:
        return {"status": "error", "message": f"Doctor with ID '{doctor_id}' not found."}
    
    session["selected_doctor"] = doc
    ui = {"slots": slots_ui_data(doc)}
    session["last_ui_data"].update(ui)
    
    slots = doc.get("availability_slots") or []
    return {
        "status": "success",
        "doctor_name": doc["name"],
        "doctor_id": doc["doctor_id"],
        "available_slots": [s["label"] for s in slots if s.get("status") == "available"],
        "ui_data": ui
    }


def tool_get_patient_appointments(session: dict[str, Any], auth: Optional[str], status_filter: str = "scheduled") -> dict[str, Any]:
    """Fetch patient appointments from PostgreSQL backend."""
    metrics.inc("agent_tool_calls_total")
    patient_id = session.get("patient_id")
    if not patient_id or not auth or not auth.lower().startswith("bearer "):
        return {
            "status": "unauthorized",
            "message": LOGIN_REQ_LOOKUP,
            "appointments": []
        }
    
    appts = backend_client.fetch_patient_appointments(patient_id, auth, status_filter=status_filter)
    session["patient_appointments"] = appts
    formatted = [format_appointment_for_ui(a) for a in appts]
    
    ui = {"appointments": formatted}
    session["last_ui_data"].update(ui)
    
    return {
        "status": "success",
        "count": len(appts),
        "appointments": formatted,
        "ui_data": ui
    }


def tool_get_clinic_info(session: dict[str, Any]) -> dict[str, Any]:
    """Return clinic operational info."""
    metrics.inc("agent_tool_calls_total")
    return {
        "status": "success",
        "clinic_name": "MediBook Central Clinic",
        "working_hours": "Mon-Fri: 9:00 AM to 5:00 PM, Sat-Sun: CLOSED",
        "consultation_fees": "Rs. 1,800 to Rs. 2,500 depending on specialist",
        "location": "Main Boulevard, Lahore",
    }


def tool_retrieve_medical_knowledge(session: dict[str, Any], query: str) -> dict[str, Any]:
    """Run medical knowledge retrieval / symptom triage."""
    metrics.inc("agent_tool_calls_total")
    
    if rag_settings.RAG_ENABLED:
        from app.rag.pipeline import get_rag_pipeline
        
        rag_result = get_rag_pipeline().triage_symptoms(
            query,
            conversation_context=query,
            clinic_id=session.get("clinic_id"),
            request_id=session.get("conversation_id"),
        )
        
        if rag_result.needs_emergency_care:
            return {
                "status": "emergency",
                "message": EMERGENCY_ALERT,
                "needs_emergency_care": True
            }
            
        ui_data = {
            "triage": {
                "specialty": rag_result.specialty,
                "urgency": rag_result.urgency_level,
                "confidence": rag_result.confidence,
                "rag_used": rag_result.rag_used,
                "rag_status": rag_result.rag_status,
                "fallback_used": rag_result.fallback_used,
                "sources": [s.model_dump() for s in rag_result.sources],
            }
        }
        session["last_ui_data"].update(ui_data)
        
        return {
            "status": "success",
            "bot_recommendation": rag_result.bot_message,
            "recommended_specialty": rag_result.specialty,
            "urgency_level": rag_result.urgency_level,
            "sources": [s.title for s in rag_result.sources],
            "ui_data": ui_data
        }
    
    res = triage(query)
    return {
        "status": "success",
        "recommended_specialty": res.specialty,
        "urgency_level": res.urgency_level,
        "bot_recommendation": f"Recommended specialty: {res.specialty}.",
        "ui_data": {}
    }


# ---------------------------------------------------------------------------
# Write Tools (Propose & Validate Phase - No DB Mutations)
# ---------------------------------------------------------------------------

def tool_propose_book_appointment(
    session: dict[str, Any],
    doctor_id: str,
    date_time: str,
    symptoms: Optional[str] = None,
    auth: Optional[str] = None,
) -> dict[str, Any]:
    """Validate booking details and store proposal in pending_action."""
    metrics.inc("agent_tool_calls_total")
    
    candidates = session.get("candidate_doctors") or []
    doc = find_doctor_by_id(doctor_id, candidates)
    if not doc:
        all_docs = backend_client.list_doctors()
        enriched = fetch_doctor_slots(all_docs)
        session["candidate_doctors"] = enriched
        doc = find_doctor_by_id(doctor_id, enriched)
        
    if not doc:
        return {"valid": False, "reason": f"Doctor with ID '{doctor_id}' not found."}
    
    slot = find_slot_by_ts(date_time, doc) if date_time else None
    if not slot:
        slot = match_slot_from_text(date_time, doc)
        
    if not slot:
        # Check if date_time matches an available slot label
        for s in doc.get("availability_slots") or []:
            if date_time.lower() in s.get("label", "").lower() or date_time in s.get("timestamp", ""):
                slot = s
                break

    if not slot:
        available_labels = [s["label"] for s in doc.get("availability_slots") or [] if s.get("status") == "available"]
        return {
            "valid": False,
            "reason": f"Requested slot '{date_time}' is unavailable for {doc['name']}. Available slots: {available_labels}"
        }
        
    proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
    pending = {
        "proposal_id": proposal_id,
        "action_type": "book",
        "doctor": doc,
        "doctor_id": doc["doctor_id"],
        "doctor_name": doc["name"],
        "clinic_name": doc["clinic_name"],
        "clinic_address": doc["clinic_address"],
        "slot_timestamp": slot["timestamp"],
        "slot_label": slot["label"],
        "symptoms": symptoms or session.get("symptoms_text") or "General Consultation",
        "auth": auth,
        "status": "proposed",
    }
    
    session["pending_action"] = pending
    session["selected_doctor"] = doc
    
    ui_booking = {
        "doctor": doc,
        "selectedSlot": slot["label"],
        "isConfirmed": False
    }
    ui = {"booking": ui_booking}
    session["last_ui_data"].update(ui)
    
    summary = (
        f"PROPOSAL READY (ID: {proposal_id}): Book an appointment with {doc['name']} "
        f"({doc['specialization']}) on {slot['label']} at {doc['clinic_name']} ({doc['clinic_address']}). "
        f"Consultation Fee: Rs. {doc['consultation_fee']}."
    )
    
    return {
        "valid": True,
        "proposal_id": proposal_id,
        "summary": summary,
        "details": {
            "doctor_name": doc["name"],
            "doctor_specialization": doc["specialization"],
            "clinic_name": doc["clinic_name"],
            "date_time": slot["label"],
            "fee": doc["consultation_fee"]
        },
        "ui_data": ui
    }


def tool_propose_reschedule_appointment(
    session: dict[str, Any],
    appointment_id: str,
    new_date_time: str,
    auth: Optional[str] = None,
) -> dict[str, Any]:
    """Validate reschedule details and store proposal in pending_action."""
    metrics.inc("agent_tool_calls_total")
    
    patient_id = session.get("patient_id")
    if not patient_id or not auth:
        return {"valid": False, "reason": LOGIN_REQ_RESCHEDULE}
    
    appts = session.get("patient_appointments") or backend_client.fetch_patient_appointments(patient_id, auth)
    appt = next((a for a in appts if str(a.get("id", "")) == appointment_id or str(a.get("appointment_id", "")) == appointment_id), None)
    
    if not appt or (appt.get("patient_id") and str(appt.get("patient_id")) != str(patient_id)):
        return {"valid": False, "reason": "Appointment not found or does not belong to authenticated patient."}
    
    old_label = appt.get("appointment_time", "Previous time")
    doc_id = appt.get("doctor_id")
    
    all_docs = backend_client.list_doctors()
    enriched = fetch_doctor_slots(all_docs)
    doc = find_doctor_by_id(str(doc_id), enriched) if doc_id else None
    
    if not doc and enriched:
        doc = enriched[0]
        
    if not doc:
        return {"valid": False, "reason": "Could not verify doctor availability for reschedule."}
    
    slot = find_slot_by_ts(new_date_time, doc) if new_date_time else None
    if not slot:
        slot = match_slot_from_text(new_date_time, doc)
    if not slot:
        for s in doc.get("availability_slots") or []:
            if new_date_time.lower() in s.get("label", "").lower() or new_date_time in s.get("timestamp", ""):
                slot = s
                break

    if not slot:
        available_labels = [s["label"] for s in doc.get("availability_slots") or [] if s.get("status") == "available"]
        return {"valid": False, "reason": f"Requested slot '{new_date_time}' is not available. Available slots: {available_labels}"}

    proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
    pending = {
        "proposal_id": proposal_id,
        "action_type": "reschedule",
        "appointment_id": appointment_id,
        "doctor": doc,
        "doctor_name": appt.get("doctor_name") or doc["name"],
        "old_slot_label": old_label,
        "new_slot_timestamp": slot["timestamp"],
        "new_slot_label": slot["label"],
        "auth": auth,
        "status": "proposed"
    }
    
    session["pending_action"] = pending
    
    ui_reschedule = {
        "doctor": doc,
        "oldSlot": old_label,
        "newSlot": slot["label"]
    }
    ui = {"reschedule": ui_reschedule}
    session["last_ui_data"].update(ui)
    
    summary = (
        f"PROPOSAL READY (ID: {proposal_id}): Reschedule appointment {appointment_id} with {pending['doctor_name']} "
        f"from {old_label} to {slot['label']}."
    )
    
    return {
        "valid": True,
        "proposal_id": proposal_id,
        "summary": summary,
        "details": {
            "doctor_name": pending['doctor_name'],
            "old_time": old_label,
            "new_time": slot["label"]
        },
        "ui_data": ui
    }


def tool_propose_cancel_appointment(
    session: dict[str, Any],
    appointment_id: str,
    auth: Optional[str] = None,
) -> dict[str, Any]:
    """Validate cancel details and store proposal in pending_action."""
    metrics.inc("agent_tool_calls_total")
    
    patient_id = session.get("patient_id")
    if not patient_id or not auth:
        return {"valid": False, "reason": LOGIN_REQ_CANCEL}
        
    appts = session.get("patient_appointments") or backend_client.fetch_patient_appointments(patient_id, auth)
    appt = next((a for a in appts if str(a.get("id", "")) == appointment_id or str(a.get("appointment_id", "")) == appointment_id), None)
    
    if not appt or (appt.get("patient_id") and str(appt.get("patient_id")) != str(patient_id)):
        return {"valid": False, "reason": "Appointment not found or does not belong to authenticated patient."}
        
    proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
    pending = {
        "proposal_id": proposal_id,
        "action_type": "cancel",
        "appointment_id": appointment_id,
        "doctor_name": appt.get("doctor_name", "Doctor"),
        "clinic_name": appt.get("clinic_name", "Clinic"),
        "appointment_time": appt.get("appointment_time", "Scheduled time"),
        "auth": auth,
        "status": "proposed"
    }
    
    session["pending_action"] = pending
    
    summary = (
        f"PROPOSAL READY (ID: {proposal_id}): Cancel appointment with {pending['doctor_name']} "
        f"scheduled for {pending['appointment_time']} at {pending['clinic_name']}."
    )
    
    return {
        "valid": True,
        "proposal_id": proposal_id,
        "summary": summary,
        "details": {
            "doctor_name": pending['doctor_name'],
            "clinic_name": pending['clinic_name'],
            "appointment_time": pending['appointment_time']
        },
        "ui_data": {}
    }


# ---------------------------------------------------------------------------
# Write Tools (Execute Phase - Only After User Confirmation Turn)
# ---------------------------------------------------------------------------

def tool_execute_confirmed_action(session: dict[str, Any], auth: Optional[str]) -> dict[str, Any]:
    """Commit pending write action to PostgreSQL after explicit user confirmation turn."""
    pending = session.get("pending_action")
    if not pending or pending.get("status") != "proposed":
        return {
            "success": False,
            "reason": "No pending proposed action found to confirm."
        }
        
    action_type = pending.get("action_type")
    effective_auth = auth or pending.get("auth")
    
    if not effective_auth or not effective_auth.lower().startswith("bearer "):
        return {
            "success": False,
            "reason": "Authentication required to complete action. Please sign in."
        }
        
    pat_id = session.get("patient_id")
    if not pat_id:
        return {
            "success": False,
            "reason": "Patient session required to complete action. Please sign in."
        }
        
    try:
        if action_type == "book":
            doc = pending["doctor"]
            payload = {
                "patient_id": pat_id,
                "doctor_id": doc["doctor_id"],
                "appointment_time": pending["slot_timestamp"],
                "symptoms_reported": (pending.get("symptoms") or "General Consultation")[:500],
                "urgency_level": session.get("urgency_level") or "normal",
                "appointment_type": "in_person"
            }
            
            created = backend_client.create_appointment(payload, effective_auth)
            appt_id = created.get("appointment_id") or created.get("id")
            session["appointment_booked"] = appt_id
            session["status"] = "completed"
            
            # Integrations
            try:
                cal_p = {
                    "appointment_id": str(appt_id),
                    "doctor_name": doc["name"],
                    "patient_name": "Patient",
                    "clinic_name": doc["clinic_name"],
                    "clinic_address": doc["clinic_address"],
                    "appointment_time": pending["slot_timestamp"],
                    "duration_minutes": 30,
                    "symptoms_reported": pending.get("symptoms", "")
                }
                cid = google_calendar.create_calendar_event(cal_p)
                if cid: session["google_calendar_event_id"] = cid
                
                n8n_p = cal_p.copy()
                n8n_p["patient_id"] = pat_id
                n8n_p["doctor_id"] = doc["doctor_id"]
                n8n_p["clinic_id"] = created.get("clinic_id")
                n8n_p["urgency_level"] = payload["urgency_level"]
                n8n_p["google_calendar_event_id"] = session.get("google_calendar_event_id")
                n8n_webhook.dispatch_appointment_created(n8n_p)
            except Exception as exc:
                logger.warning("Integration sync after booking failed: %s", exc)

            session["pending_action"] = None
            metrics.inc("agent_write_confirmations_total")
            
            ui_booking = {
                "doctor": doc,
                "selectedSlot": pending["slot_label"],
                "isConfirmed": True
            }
            ui = {"booking": ui_booking}
            session["last_ui_data"].update(ui)
            
            return {
                "success": True,
                "message": f"Your appointment with {doc['name']} for {pending['slot_label']} is confirmed!",
                "ui_data": ui
            }

        elif action_type == "reschedule":
            appt_id = pending["appointment_id"]
            new_ts = pending["new_slot_timestamp"]
            new_label = pending["new_slot_label"]
            
            updated = backend_client.reschedule_appointment(appt_id, new_ts, effective_auth)
            
            # Integrations
            cal_id = session.get("google_calendar_event_id") or updated.get("google_calendar_event_id")
            if cal_id:
                try:
                    google_calendar.update_calendar_event(cal_id, new_ts)
                except Exception:
                    pass
            try:
                rm = reminders.calculate_reminder_times(new_ts) if new_ts else {}
                n8n_webhook.dispatch_appointment_rescheduled({
                    "appointment_id": appt_id,
                    "patient_id": pat_id,
                    "doctor_id": str(pending.get("doctor", {}).get("doctor_id", "")),
                    "new_appointment_time": new_ts,
                    "previous_appointment_time": pending.get("old_slot_label"),
                    "new_reminder_time_1": rm.get("reminder_time_1"),
                    "new_reminder_time_2": rm.get("reminder_time_2"),
                })
            except Exception:
                pass

            session["pending_action"] = None
            metrics.inc("agent_write_confirmations_total")
            
            return {
                "success": True,
                "message": f"✅ Rescheduled successfully to {new_label}!",
                "ui_data": {}
            }

        elif action_type == "cancel":
            appt_id = pending["appointment_id"]
            backend_client.cancel_appointment(appt_id, effective_auth)
            
            session["pending_action"] = None
            metrics.inc("agent_write_confirmations_total")
            
            return {
                "success": True,
                "message": f"✅ Your appointment with {pending['doctor_name']} has been cancelled.",
                "ui_data": {}
            }

        else:
            session["pending_action"] = None
            return {"success": False, "reason": f"Unknown action type '{action_type}'."}

    except backend_client.BackendError as exc:
        err_msg = _booking_error(exc, is_reschedule=(action_type == "reschedule"))
        return {"success": False, "reason": err_msg}
    except Exception as exc:
        logger.error("Error executing confirmed action: %s", exc, exc_info=True)
        return {"success": False, "reason": "Failed to commit action to backend."}
