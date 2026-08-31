import re

with open("ai-service/app/tools.py", "r") as f:
    content = f.read()

# Replace tool_book_appointment
old_book = """def tool_book_appointment(
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
    return {"ok": True, "appointment": appointment, "ui_data": ui}"""

new_book = """def tool_propose_book_appointment(
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
    return {"ok": True, "proposal_id": pid, "summary": summary, "ui_data": ui}"""

content = content.replace(old_book, new_book)

# Replace tool_reschedule_appointment
old_reschedule = """def tool_reschedule_appointment(
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
        {"reschedule": {"doctor": doc, "oldSlot": (appt or {}).get("appointment_time"), "newSlot": slot.get("label")}},
    )
    return {"ok": True, "success": True, "new_datetime": slot.get("label"), "ui_data": ui}"""

new_reschedule = """def tool_propose_reschedule_appointment(
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
    return {"ok": True, "success": True, "proposal_id": pid, "summary": summary, "ui_data": ui}"""

content = content.replace(old_reschedule, new_reschedule)

# Replace tool_cancel_appointment
old_cancel = """def tool_cancel_appointment(
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
    try:
        backend_client.cancel_appointment(appointment_id, auth or "")
    except backend_client.BackendError as exc:
        return {"ok": False, "error": _booking_error(exc), "success": False}
    return {"ok": True, "success": True}"""

new_cancel = """def tool_propose_cancel_appointment(
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
        
    return {"ok": True, "success": True, "proposal_id": pid, "summary": summary}"""

content = content.replace(old_cancel, new_cancel)

execute_confirmed = """

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
"""

content = content.replace('def tool_retrieve_medical_knowledge', execute_confirmed + '\ndef tool_retrieve_medical_knowledge')

# Update HANDLERS
old_handlers = """HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "get_patient_appointments": tool_get_patient_appointments,
    "reschedule_appointment": tool_reschedule_appointment,
    "cancel_appointment": tool_cancel_appointment,
    "book_appointment": tool_book_appointment,
    "get_doctors_by_specialty": tool_get_doctors_by_specialty,
    "get_availability": tool_get_availability,
    "get_patient_info": tool_get_patient_info,
    "retrieve_medical_knowledge": tool_retrieve_medical_knowledge,
}"""

new_handlers = """HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "get_patient_appointments": tool_get_patient_appointments,
    "propose_reschedule_appointment": tool_propose_reschedule_appointment,
    "propose_cancel_appointment": tool_propose_cancel_appointment,
    "propose_book_appointment": tool_propose_book_appointment,
    "execute_confirmed_action": tool_execute_confirmed_action,
    "get_doctors_by_specialty": tool_get_doctors_by_specialty,
    "get_availability": tool_get_availability,
    "get_patient_info": tool_get_patient_info,
    "retrieve_medical_knowledge": tool_retrieve_medical_knowledge,
}"""

content = content.replace(old_handlers, new_handlers)

# Fix book_appointment missing patient_id auto insert
content = content.replace('"book_appointment"', '"propose_book_appointment"')

with open("ai-service/app/tools.py", "w") as f:
    f.write(content)
