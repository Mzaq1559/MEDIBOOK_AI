"""Workflow handlers for NEW_BOOKING, RESCHEDULE, CANCEL, LOOKUP."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app import backend_client
from app.chatbot_nlu import extract_appointment_id, extract_option_id, is_confirm, is_decline
from app.chatbot_slots import (
    doctors_ui_data,
    fetch_doctor_slots,
    find_doctor_by_id,
    find_slot_by_ts,
    format_appointment_for_ui,
    match_slot_from_text,
    slots_ui_data,
)
from app.chatbot_state import S
from app.schemas import OptionItem
from app.rag.config import rag_settings
from app.symptom_triage import EMERGENCY_ALERT, follow_ups_for, is_emergency, triage
from integrations import google_calendar, n8n_webhook, reminders

logger = logging.getLogger("medibook.ai.handlers")

LOGIN_REQ_BOOK = "To confirm this appointment you need to be logged in. Please sign in, then send 'yes' again."
LOGIN_REQ_RESCHEDULE = "To reschedule you need to be logged in. Please sign in, then confirm."
LOGIN_REQ_CANCEL = "Please log in to cancel appointments."
LOGIN_REQ_LOOKUP = "Please log in to view your appointments."


def _run_symptom_triage(session: dict[str, Any], symptoms_text: str) -> tuple[str, str, dict[str, Any]]:
    """Run RAG triage when enabled, otherwise use deterministic rules."""
    if rag_settings.RAG_ENABLED:
        from app.rag.pipeline import get_rag_pipeline

        rag_result = get_rag_pipeline().triage_symptoms(
            symptoms_text,
            conversation_context=symptoms_text,
            clinic_id=session.get("clinic_id"),
            request_id=session.get("conversation_id"),
        )
        specialty = rag_result.specialty
        backend_spec = rag_result.backend_specialization
        session["specialty"] = specialty
        session["backend_specialization"] = backend_spec
        session["urgency_level"] = rag_result.urgency_level
        session["rag_used"] = rag_result.rag_used
        session["rag_status"] = rag_result.rag_status

        if rag_result.needs_emergency_care:
            session["state"] = S.EMERGENCY
            return EMERGENCY_ALERT, "emergency_redirect", {}

        follow_spec = specialty or "General Physician"
        session["follow_ups"] = follow_ups_for(follow_spec)
        session["follow_up_index"] = 0
        session["state"] = S.ASKING_FOLLOWUP

        ui_data: dict[str, Any] = {
            "triage": {
                "specialty": specialty,
                "urgency": rag_result.urgency_level,
                "confidence": rag_result.confidence,
                "rag_used": rag_result.rag_used,
                "rag_status": rag_result.rag_status,
                "fallback_used": rag_result.fallback_used,
                "sources": [s.model_dump() for s in rag_result.sources],
            }
        }
        first_question = session["follow_ups"][0]
        bot = f"{rag_result.bot_message}\n\nLet me ask a few quick questions:\n{first_question}"
        return bot, "waiting_for_input", ui_data

    result = triage(symptoms_text)
    session["specialty"] = result.specialty
    session["backend_specialization"] = result.specialty
    session["urgency_level"] = result.urgency_level
    session["follow_ups"] = follow_ups_for(result.specialty)
    session["follow_up_index"] = 0
    session["state"] = S.ASKING_FOLLOWUP
    return (
        f"Thank you. Let me ask a few quick questions:\n{session['follow_ups'][0]}",
        "waiting_for_input",
        {},
    )


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


def handle_new_booking(session: dict[str, Any], text: str, nlu: dict, auth: Optional[str]) -> tuple[str, str, list, dict]:
    state = session["state"]
    intent = nlu.get("intent")
    clean_text = text.lower().strip()

    # 1. Direct Booking Request: bypass symptom triage
    if intent == "appointment" or clean_text in ("book an appointment", "book appointment", "appointment"):
        spec = nlu.get("specialty") or session.get("specialty")
        doc_name = nlu.get("doctor_name")
        docs = backend_client.list_doctors(specialization=spec) or backend_client.list_doctors()
        if doc_name:
            matched = [d for d in docs if doc_name.lower() in d.get("name", "").lower()]
            if matched:
                docs = matched
        enriched = fetch_doctor_slots(docs, next_days=3)
        session["candidate_doctors"] = enriched
        session["state"] = S.SHOWING_DOCTORS
        return "Please select a doctor to book your appointment:", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(enriched)}

    # 2. Off-topic / Hostile input fallback mid-workflow
    if intent == "other":
        if state == S.SHOWING_DOCTORS:
            docs = session.get("candidate_doctors", [])
            return "I didn't understand that. Please select a doctor from the options below:", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(docs)}
        if state == S.SHOWING_SLOTS:
            doc = session.get("selected_doctor")
            return "I didn't understand that. Please select an available time slot:", "waiting_for_slot_selection", [], {"slots": slots_ui_data(doc) if doc else []}
        if state == S.AWAIT_CONFIRM:
            doc = session.get("selected_doctor")
            ui_booking = {"doctor": doc, "selectedSlot": session.get("selected_slot_label"), "isConfirmed": False}
            return "I didn't understand that. Please confirm your appointment or click Change.", "waiting_for_confirmation", [], {"booking": ui_booking}
        if state in (S.ASKING_SYMPTOMS, S.ASKING_FOLLOWUP):
            return "I didn't understand that — would you like to continue booking an appointment, or describe your symptoms?", "waiting_for_input", [], {}

    # 3. Initial state handling (IDLE, FAQ, LOOKUP)
    if state in (S.IDLE, S.FAQ, S.LOOKUP):
        if intent == "symptom" and clean_text and clean_text not in ("hi", "hello", "hey"):
            session["symptoms_text"] = str(nlu.get("symptoms") or text)
            if is_emergency(session["symptoms_text"]):
                session["state"] = S.EMERGENCY
                return EMERGENCY_ALERT, "emergency_redirect", [], {}
            result = triage(session["symptoms_text"])
            session["specialty"] = result.specialty
            session["urgency_level"] = result.urgency_level
            session["follow_ups"] = follow_ups_for(result.specialty)
            session["follow_up_index"] = 0
            session["state"] = S.ASKING_FOLLOWUP
            return f"Thank you. Let me ask a few quick questions:\n{session['follow_ups'][0]}", "waiting_for_input", [], {}

        session["state"] = S.ASKING_SYMPTOMS
        return (
            "Hi! I'm MediBook AI. What brings you in today? Please describe your symptoms.",
            "waiting_for_symptoms",
            [],
            {},
        )

    # 4. Active Symptom Triage Flow
    if state == S.ASKING_SYMPTOMS:
        session["symptoms_text"] = str(nlu.get("symptoms") or text)
        if is_emergency(session["symptoms_text"]):
            session["state"] = S.EMERGENCY
            return EMERGENCY_ALERT, "emergency_redirect", [], {}
        bot, action, ui_data = _run_symptom_triage(session, session["symptoms_text"])
        return bot, action, [], ui_data

    if state == S.ASKING_FOLLOWUP:
        session["symptoms_text"] = f"{session.get('symptoms_text', '')} {text}".strip()
        if is_emergency(session["symptoms_text"]):
            session["state"] = S.EMERGENCY
            return EMERGENCY_ALERT, "emergency_redirect", [], {}
        
        idx = int(session.get("follow_up_index") or 0) + 1
        session["follow_up_index"] = idx
        fu = session.get("follow_ups") or []
        if idx < min(3, len(fu)):
            return f"Thanks. {fu[idx]}", "waiting_for_input", [], {}
        
        # Transition to doctor selection
        spec = session.get("backend_specialization") or session.get("specialty")
        docs = backend_client.list_doctors(specialization=spec) or backend_client.list_doctors()
        enriched = fetch_doctor_slots(docs, next_days=3)
        session["candidate_doctors"] = enriched
        session["state"] = S.SHOWING_DOCTORS
        msg = f"Based on your symptoms, I recommend seeing a {spec or 'doctor'}. Please select a doctor:"
        return msg, "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(enriched)}

    # 5. Doctor Selection
    if state == S.SHOWING_DOCTORS:
        doc_id = extract_option_id(text, nlu)
        if not doc_id:
            return "Please select a doctor by clicking one of the cards.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
        
        doc = find_doctor_by_id(doc_id, session.get("candidate_doctors", []))
        if not doc:
            return "I couldn't find that doctor. Please pick from the list.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
        
        session["selected_doctor"] = doc
        session["state"] = S.SHOWING_SLOTS
        return f"You selected {doc['name']}. Please pick an available time slot:", "waiting_for_slot_selection", [], {"slots": slots_ui_data(doc)}

    # 6. Slot Selection
    if state == S.SHOWING_SLOTS:
        doc = session.get("selected_doctor")
        if not doc:
            session["state"] = S.SHOWING_DOCTORS
            return "Session error: missing doctor. Please pick a doctor.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
        
        slot_ts = extract_option_id(text, nlu)
        if not slot_ts:
            iso_m = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)?)", text)
            if iso_m:
                slot_ts = iso_m.group(1)
        slot = find_slot_by_ts(slot_ts, doc) if slot_ts else match_slot_from_text(text, doc)
        if not slot:
            return "Please select a time slot from the list.", "waiting_for_slot_selection", [], {"slots": slots_ui_data(doc)}
        
        session["selected_slot"] = slot
        session["selected_timestamp"] = slot["timestamp"]
        session["selected_slot_label"] = slot["label"]
        session["state"] = S.AWAIT_CONFIRM
        
        ui_booking = {
            "doctor": doc,
            "selectedSlot": slot["label"],
            "isConfirmed": False
        }
        return "Perfect! Please confirm your appointment details.", "waiting_for_confirmation", [], {"booking": ui_booking}

    # 7. Confirmation State
    if state == S.AWAIT_CONFIRM:
        if is_decline(text, nlu) or text.lower().strip() == "change":
            session["state"] = S.SHOWING_DOCTORS
            docs = session.get("candidate_doctors", [])
            ids = [d["doctor_id"] for d in docs]
            all_d = backend_client.list_doctors()
            filtered = [d for d in all_d if d["doctor_id"] in ids] if ids else all_d
            enriched = fetch_doctor_slots(filtered)
            session["candidate_doctors"] = enriched
            return "No problem. Let's pick a different doctor or time.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(enriched)}
        
        if is_confirm(text, nlu):
            if not auth or not auth.lower().startswith("bearer "):
                return LOGIN_REQ_BOOK, "waiting_for_login", [], {}
            pat_id = session.get("patient_id")
            if not pat_id:
                return "I need your patient profile. Please log in first.", "waiting_for_login", [], {}
            
            doc = session.get("selected_doctor")
            ts = session.get("selected_timestamp")
            if not doc or not ts:
                session["state"] = S.SHOWING_DOCTORS
                return "Lost selected slot. Please pick again.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
            
            payload = {
                "patient_id": pat_id,
                "doctor_id": doc["doctor_id"],
                "appointment_time": ts,
                "symptoms_reported": (session.get("symptoms_text") or "General")[:500],
                "urgency_level": session.get("urgency_level") or "normal",
                "appointment_type": "in_person"
            }
            try:
                created = backend_client.create_appointment(payload, auth)
            except backend_client.BackendError as e:
                ui = {"booking": {"doctor": doc, "selectedSlot": session.get("selected_slot_label"), "isConfirmed": False}}
                return _booking_error(e), "waiting_for_confirmation", [], {"booking": ui}

            session["appointment_booked"] = created.get("appointment_id") or created.get("id")
            session["state"] = S.BOOKED
            session["status"] = "completed"
            
            try:
                cal_p = {
                    "appointment_id": str(session["appointment_booked"]),
                    "doctor_name": doc["name"],
                    "patient_name": "Patient",
                    "clinic_name": doc["clinic_name"],
                    "clinic_address": doc["clinic_address"],
                    "appointment_time": ts,
                    "duration_minutes": 30,
                    "symptoms_reported": session.get("symptoms_text", "")
                }
                cid = google_calendar.create_calendar_event(cal_p)
                if cid: session["google_calendar_event_id"] = cid
            except Exception as e:
                logger.warning(f"Calendar sync failed: {e}")
                
            try:
                n8n_p = cal_p.copy()
                n8n_p["patient_id"] = pat_id
                n8n_p["doctor_id"] = doc["doctor_id"]
                n8n_p["clinic_id"] = created.get("clinic_id")
                n8n_p["urgency_level"] = payload["urgency_level"]
                n8n_p["google_calendar_event_id"] = session.get("google_calendar_event_id")
                n8n_webhook.dispatch_appointment_created(n8n_p)
            except Exception as e:
                logger.warning(f"N8N sync failed: {e}")

            ui_booking = {
                "doctor": doc,
                "selectedSlot": session.get("selected_slot_label"),
                "isConfirmed": True
            }
            return "Your appointment is confirmed!", "appointment_booked", [], {"booking": ui_booking}

    # Fallback
    session["state"] = S.ASKING_SYMPTOMS
    return "Let's start over. What are your symptoms?", "waiting_for_symptoms", [], {}


def handle_lookup(session, user_message, backend_client):
    """Handle appointment lookup"""
    
    pat_id = session.get("patient_id")
    auth = session.get("jwt_token") or session.get("access_token") or ""
    
    if not pat_id or not auth:
        return LOGIN_REQ_LOOKUP, "waiting_for_input", [], {}
    
    try:
        # Fetch appointments from backend
        appts = backend_client.fetch_patient_appointments(pat_id, "")
        
        # Debug: Print what we got
        print(f"DEBUG: fetch_patient_appointments returned: {appts}")
        print(f"DEBUG: Type: {type(appts)}")
        
        # Handle different response formats
        if appts is None:
            return "You have no upcoming appointments.", "waiting_for_input", [], {"appointments": []}
        
        # If it's a dict with 'appointments' key
        if isinstance(appts, dict):
            appointment_list = appts.get("appointments", [])
        # If it's a list directly
        elif isinstance(appts, list):
            appointment_list = appts
        else:
            print(f"DEBUG: Unexpected response type: {type(appts)}")
            return "You have no upcoming appointments.", "waiting_for_input", [], {"appointments": []}
        
        # Filter for scheduled/upcoming appointments
        upcoming = [a for a in appointment_list if a.get("status") == "scheduled"]
        
        print(f"DEBUG: Found {len(upcoming)} upcoming appointments")
        
        if not upcoming:
            return "You have no upcoming appointments.", "waiting_for_input", [], {"appointments": []}
        
        # Format appointments for UI
        formatted = [format_appointment_for_ui(a) for a in upcoming]
        
        session["patient_appointments"] = upcoming
        
        return f"You have {len(upcoming)} upcoming appointments:", "show_appointments", [], {"appointments": formatted}
        
    except Exception as e:
        print(f"ERROR in handle_lookup: {str(e)}")
        return "Error fetching appointments. Please try again.", "waiting_for_input", [], {}

def handle_cancel(session: dict[str, Any], text: str, nlu: dict, auth: Optional[str]) -> tuple[str, str, list, dict]:
    if not auth or not auth.lower().startswith("bearer "):
        return LOGIN_REQ_CANCEL, "waiting_for_login", [], {}
    pat_id = session.get("patient_id")
    if not pat_id:
        return LOGIN_REQ_CANCEL, "waiting_for_login", [], {}
    
    state = session["state"]
    
    if state not in (S.CANCEL_FETCH, S.CANCEL_PICK, S.CANCEL_CONFIRM):
        appts = backend_client.fetch_patient_appointments(pat_id, "")
        if not appts:
            session["state"] = S.IDLE
            return "You have no appointments to cancel.", "show_appointments", [], {"appointments": []}
        
        session["patient_appointments"] = appts
        session["state"] = S.CANCEL_PICK
        formatted = [format_appointment_for_ui(a) for a in appts]
        return "Which appointment would you like to cancel?", "show_appointments", [], {"appointments": formatted}
    
    if state == S.CANCEL_PICK:
        appt_id = extract_option_id(text, nlu) or extract_appointment_id(text, nlu)
        if not appt_id:
            formatted = [format_appointment_for_ui(a) for a in session.get("patient_appointments", [])]
            return "Please select an appointment to cancel.", "show_appointments", [], {"appointments": formatted}
        
        appt = next((a for a in session.get("patient_appointments", []) if str(a.get("id", "")) == appt_id or str(a.get("appointment_id", "")) == appt_id), None)
        if not appt:
            formatted = [format_appointment_for_ui(a) for a in session.get("patient_appointments", [])]
            return "Invalid selection. Please click an appointment to cancel.", "show_appointments", [], {"appointments": formatted}
        
        session["picked_appointment_id"] = appt_id
        session["state"] = S.CANCEL_CONFIRM
        doc_name = appt.get("doctor_name", "your doctor")
        time_lbl = appt.get("appointment_time", "this time")
        return f"Are you sure you want to cancel your appointment with {doc_name} on {time_lbl}? (Reply Yes/No)", "waiting_for_confirmation", [], {}
    
    if state == S.CANCEL_CONFIRM:
        if is_decline(text, nlu):
            session["state"] = S.IDLE
            return "Okay, I won't cancel it.", "waiting_for_input", [], {}
        
        if is_confirm(text, nlu):
            appt_id = session.get("picked_appointment_id")
            if not appt_id:
                session["state"] = S.IDLE
                return "Lost appointment context. Please start over.", "waiting_for_input", [], {}
            
            try:
                backend_client.cancel_appointment(appt_id, auth)
            except backend_client.BackendError as e:
                return _booking_error(e), "waiting_for_confirmation", [], {}
            
            session["state"] = S.IDLE
            return "✅ Your appointment has been cancelled.", "waiting_for_input", [], {}
        
        return "Please reply Yes to confirm cancellation, or No to keep it.", "waiting_for_confirmation", [], {}

    session["state"] = S.IDLE
    return "Let's start over.", "waiting_for_input", [], {}


def handle_reschedule(session: dict[str, Any], text: str, nlu: dict, auth: Optional[str]) -> tuple[str, str, list, dict]:
    if not auth or not auth.lower().startswith("bearer "):
        return LOGIN_REQ_RESCHEDULE, "waiting_for_login", [], {}
    pat_id = session.get("patient_id")
    if not pat_id:
        return LOGIN_REQ_RESCHEDULE, "waiting_for_login", [], {}
    
    state = session["state"]
    
    if state not in (S.RESCHEDULE_FETCH, S.RESCHEDULE_PICK, S.RESCHEDULE_SLOTS, S.RESCHEDULE_CONFIRM):
        appt_id = extract_appointment_id(text, nlu)
        if appt_id:
            # They provided an ID upfront
            session["picked_appointment_id"] = appt_id
            session["state"] = S.RESCHEDULE_FETCH
        else:
            appts = backend_client.fetch_patient_appointments(pat_id, "")
            if not appts:
                session["state"] = S.IDLE
                return "You have no appointments to reschedule. Would you like to book a new one?", "waiting_for_input", [], {}
            session["patient_appointments"] = appts
            session["state"] = S.RESCHEDULE_PICK
            formatted = [format_appointment_for_ui(a) for a in appts]
            return "Which appointment would you like to reschedule?", "show_appointments", [], {"appointments": formatted}

    if state == S.RESCHEDULE_FETCH or state == S.RESCHEDULE_PICK:
        appt_id = session.get("picked_appointment_id")
        if not appt_id:
            appt_id = extract_option_id(text, nlu) or extract_appointment_id(text, nlu)
        
        if not appt_id:
            formatted = [format_appointment_for_ui(a) for a in session.get("patient_appointments", [])]
            return "Please select an appointment to reschedule.", "show_appointments", [], {"appointments": formatted}
        
        session["picked_appointment_id"] = appt_id
        
        # Load the appointment doc and slots
        # In a real app we'd fetch the specific appt to get doctor_id.
        # Since we might not have it in session, we just fetch all doctors and get slots
        docs = backend_client.list_doctors()
        enriched = fetch_doctor_slots(docs)
        session["candidate_doctors"] = enriched
        session["state"] = S.RESCHEDULE_SLOTS
        
        # We need a unified UI for slot picking (same as new booking, but maybe pre-selected doctor)
        # For simplicity, we just show all doctors and let them pick a slot
        # A better UX is showing slots for the SAME doctor. Let's try to extract doc_id if we have it in patient_appointments
        appt = next((a for a in session.get("patient_appointments", []) if str(a.get("id", "")) == appt_id or str(a.get("appointment_id", "")) == appt_id), None)
        if appt:
            session["previous_slot_label"] = appt.get("appointment_time")
            doc_id = appt.get("doctor_id")
            if doc_id:
                doc = find_doctor_by_id(doc_id, enriched)
                if doc:
                    session["selected_doctor"] = doc
                    return f"When would you like to reschedule your appointment with {doc['name']} to?", "waiting_for_new_time", [], {"slots": slots_ui_data(doc)}
        
        return "Please select a new doctor and time.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(enriched)}

    if state == S.RESCHEDULE_SLOTS:
        # User is picking a slot
        slot_ts = extract_option_id(text, nlu)
        # Direct ISO-timestamp fallback for reschedule slot picking
        if not slot_ts:
            iso_m = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)?)", text)
            if iso_m:
                slot_ts = iso_m.group(1)
        
        # Did they pick a doctor instead (UUID, not a timestamp)?
        doc_id = None
        if not slot_ts:
            doc_id = extract_option_id(text, nlu)
        if doc_id:
            doc = find_doctor_by_id(doc_id, session.get("candidate_doctors", []))
            if doc:
                session["selected_doctor"] = doc
                return f"Select a new time with {doc['name']}:", "waiting_for_new_time", [], {"slots": slots_ui_data(doc)}
            
        doc = session.get("selected_doctor")
        if doc and slot_ts:
            slot = find_slot_by_ts(slot_ts, doc)
        else:
            slot = None
            
        if not slot and doc:
            slot = match_slot_from_text(text, doc)
            
        if not slot:
            if doc:
                return "Please select a time slot.", "waiting_for_new_time", [], {"slots": slots_ui_data(doc)}
            else:
                return "Please select a doctor.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
        
        session["selected_slot"] = slot
        session["selected_timestamp"] = slot["timestamp"]
        session["selected_slot_label"] = slot["label"]
        session["state"] = S.RESCHEDULE_CONFIRM
        
        ui_reschedule = {
            "doctor": doc,
            "oldSlot": session.get("previous_slot_label") or "Previous time",
            "newSlot": slot["label"]
        }
        return "Please confirm your new appointment time.", "waiting_for_reschedule_confirm", [], {"reschedule": ui_reschedule}
        
    if state == S.RESCHEDULE_CONFIRM:
        if is_decline(text, nlu) or text.lower().strip() == "change":
            session["state"] = S.RESCHEDULE_SLOTS
            doc = session.get("selected_doctor")
            if doc:
                # Refresh slots
                enriched = fetch_doctor_slots([doc])
                if enriched: doc = enriched[0]
                session["selected_doctor"] = doc
                return "Let's pick a different time.", "waiting_for_new_time", [], {"slots": slots_ui_data(doc)}
            return "Let's pick a different doctor.", "waiting_for_doctor_selection", [], {"doctors": doctors_ui_data(session.get("candidate_doctors", []))}
            
        if is_confirm(text, nlu):
            appt_id = session.get("picked_appointment_id")
            ts = session.get("selected_timestamp")
            if not appt_id or not ts:
                session["state"] = S.IDLE
                return "Lost state. Please start over.", "waiting_for_input", [], {}
            
            try:
                updated = backend_client.reschedule_appointment(appt_id, ts, auth)
            except backend_client.BackendError as e:
                doc = session.get("selected_doctor")
                ui_reschedule = {"doctor": doc, "oldSlot": session.get("previous_slot_label"), "newSlot": session.get("selected_slot_label")}
                return _booking_error(e, is_reschedule=True), "waiting_for_reschedule_confirm", [], {"reschedule": ui_reschedule}
            
            session["state"] = S.IDLE
            
            # Integrations
            cal_id = session.get("google_calendar_event_id") or updated.get("google_calendar_event_id")
            if cal_id:
                try:
                    google_calendar.update_calendar_event(cal_id, ts)
                except Exception:
                    pass
            try:
                rm = reminders.calculate_reminder_times(ts) if ts else {}
                n8n_webhook.dispatch_appointment_rescheduled({
                    "appointment_id": appt_id,
                    "patient_id": pat_id,
                    "doctor_id": str(session.get("selected_doctor", {}).get("doctor_id", "")),
                    "new_appointment_time": ts,
                    "previous_appointment_time": session.get("previous_slot_label"),
                    "new_reminder_time_1": rm.get("reminder_time_1"),
                    "new_reminder_time_2": rm.get("reminder_time_2"),
                })
            except Exception:
                pass
            
            return f"✅ Rescheduled successfully to {session.get('selected_slot_label')}!", "reschedule_complete", [], {}

    session["state"] = S.IDLE
    return "Let's start over.", "waiting_for_input", [], {}
