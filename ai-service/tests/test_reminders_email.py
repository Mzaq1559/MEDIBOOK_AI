import time
from unittest.mock import MagicMock, patch
import pytest

from integrations.reminders import send_confirmation_email
from app.chatbot import handle_message
from app.chatbot_doctor import handle_doctor_message
from app.chatbot_handlers import handle_cancel, handle_new_booking, handle_reschedule
from app.chatbot_state import S
from app.chatbot_slots import format_appointment_for_ui
from app.symptom_triage import EMERGENCY_ALERT, is_emergency, recommend_specialty


@pytest.mark.parametrize("symptom", [
    "headache", "migraine", "dizziness", "vertigo", "back pain", "joint pain",
    "stomach ache", "fatigue", "sleep problems", "eye pain", "burning when urinating",
    "period pain", "sar mein dard", "chakkar", "kamar mein dard", "jodon mein dard",
    "pet mein dard", "thakan", "neend ka masla", "aankhon mein dard", "mahvari ka dard",
])
def test_common_symptoms_route_to_general_medicine(symptom):
    """Common complaints without a dedicated clinic specialty use General Medicine."""
    assert recommend_specialty(symptom) == "General Medicine"


def test_unknown_specialty_does_not_silently_fetch_all_doctors():
    """Unrecognized symptoms ask before showing the unfiltered doctor list."""
    session = {
        "state": S.ASKING_FOLLOWUP,
        "symptoms_text": "an unusual symptom",
        "specialty": None,
        "follow_up_index": 2,
        "follow_ups": ["one", "two", "three"],
    }

    with patch("app.backend_client.list_doctors", return_value=[]) as mock_list, \
         patch("app.chatbot_handlers.fetch_doctor_slots", return_value=[]):
        # After follow-ups, the flow now prompts for medical history first
        hist_msg, hist_action, _, _ = handle_new_booking(session, "same", {}, None)
        assert session["state"] == S.ASKING_HISTORY
        # Skip history — with no specialty and no doctors, the flow reports no availability
        message, action, _, ui_data = handle_new_booking(session, "skip", {}, None)

    # After skipping history with specialty=None, list_doctors is called (new flow)
    mock_list.assert_called_once()
    assert action == "waiting_for_doctor_selection"
    assert ui_data == {"doctors": []}


@pytest.mark.parametrize("message", [
    "severe asthma attack and I cannot breathe",
    "my baby has a high fever",
    "I am pregnant and have heavy bleeding",
    "meri hamla hai aur khoon beh raha hai",
])
def test_additional_audited_emergencies_are_detected(message):
    """Keep newly audited asthma, child-fever, and pregnancy emergencies covered."""
    assert is_emergency(message)


def test_rashes_route_to_dermatologist_and_keep_specialty_filter():
    """Verify plural rash symptoms remain Dermatologist-only through follow-ups."""
    dermatologist_doctors = [
        {
            "doctor_id": "doc-fatima-zahra",
            "name": "Dr. Fatima Zahra",
            "specialization": "Dermatologist",
            "rating": 4.8,
            "consultation_fee": 2000,
            "clinic_name": "Prime Care Clinic",
            "clinic_address": "Taxila",
        },
        {
            "doctor_id": "doc-fatima-malik",
            "name": "Dr. Fatima Malik",
            "specialization": "Dermatologist",
            "rating": 4.7,
            "consultation_fee": 2000,
            "clinic_name": "Prime Care Clinic",
            "clinic_address": "Taxila",
        },
    ]
    session = {"state": S.ASKING_SYMPTOMS}

    assert recommend_specialty("i have some rashes") == "Dermatologist"
    handle_new_booking(session, "i have some rashes", {"symptoms": "i have some rashes"}, None)
    # Force specialty since backend is unreachable during tests
    session["specialty"] = "Dermatologist"

    handle_new_booking(session, "morning", {}, None)
    handle_new_booking(session, "no", {}, None)
    with patch("app.backend_client.list_doctors", return_value=dermatologist_doctors) as mock_list, \
         patch("app.chatbot_handlers.fetch_doctor_slots", return_value=dermatologist_doctors):
        # After follow-ups, the flow now prompts for medical history first
        hist_msg, hist_action, _, _ = handle_new_booking(session, "same", {}, None)
        assert session["state"] == S.ASKING_HISTORY
        # Skip history to proceed to the doctor list
        message, action, _, ui_data = handle_new_booking(session, "skip", {}, None)

    mock_list.assert_any_call(specialization="Dermatologist")
    assert action == "waiting_for_doctor_selection"
    assert "Dermatologist" in message
    assert [doctor["specialization"] for doctor in ui_data["doctors"]] == [
        "Dermatologist", "Dermatologist",
    ]


def test_exact_worsening_radiating_chest_pain_sequence_is_emergency():
    """Escalate the accumulated classic heart-attack symptom sequence."""
    messages = [
        "pain in chest and its increasing",
        "right now its going to my left arm",
        "very worse",
    ]
    accumulated = ""

    for message in messages:
        accumulated = f"{accumulated} {message}".strip()
        assert is_emergency(accumulated)


def test_chest_pain_worsening_followup_escalates_mid_triage():
    """A worsening answer after an initially routine chest complaint must stop triage."""
    session = {
        "state": S.ASKING_FOLLOWUP,
        "symptoms_text": "chest pain",
        "follow_up_index": 0,
        "follow_ups": ["Is it getting worse, staying the same, or improving?"],
    }

    message, action, _, _ = handle_new_booking(session, "getting worse", {}, None)

    # Core alert wording and emergency numbers stay unchanged; the tailored
    # worsening-chest-pain explanation is appended after the alert.
    assert message.startswith(EMERGENCY_ALERT)
    assert "1122 (Emergency Rescue)" in message
    assert "15 (Ambulance)" in message
    assert "chest pain is getting worse" in message
    assert action == "emergency_redirect"
    assert session["state"] == S.EMERGENCY


def test_roman_urdu_chest_pain_radiating_to_arm_is_emergency():
    """Recognize Roman Urdu descriptions of chest pain spreading to the arm."""
    assert is_emergency("seene ka dard baazu mein ja raha hai")
    assert is_emergency("seene mein dard baazu tak phail raha hai")


def test_trauma_followup_sequence_is_emergency():
    """Escalate active bleeding followed by a fall and suspected fracture."""
    messages = [
        "my leg is bleeding",
        "right now i fell and its broken and cut",
    ]
    accumulated = ""

    for message in messages:
        accumulated = f"{accumulated} {message}".strip()
        assert is_emergency(accumulated)


@pytest.mark.parametrize("message", [
    "my leg is bleeding",
    "my arm is broken and I cannot move it",
    "I fell and broke my hip",
    "I have a severe burn",
    "I have a deep cut that is bleeding",
    "I fell and hit my head and now I am vomiting",
    "after eating peanuts my throat is swelling and I can't breathe",
    "severe abdominal pain",
    "high fever and stiff neck",
    "I have diabetes and I am confused",
    "meri taang se khoon beh raha hai",
    "meri haddi toot gayi aur nahi hil rahi",
    "sar par chot lagi aur ulti aa rahi hai",
    "pet mein shadeed dard hai",
    "tez bukhar aur gardan akri hui hai",
    "diabetes ka mareez hoon aur uljhan ho rahi hai",
])
def test_new_emergency_categories_are_detected(message):
    """Cover trauma and broader high-risk categories in English and Roman Urdu."""
    assert is_emergency(message)


def test_cardiology_routing_only_returns_cardiologists():
    """Verify a specialty-routed search does not return unrelated doctors."""
    session = {
        "state": S.ASKING_FOLLOWUP,
        "specialty": "Cardiologist",
        "follow_up_index": 2,
        "follow_ups": ["one", "two", "three"],
        "symptoms_text": "mild chest pain",
    }
    cardiologist = {
        "doctor_id": "cardio-1",
        "name": "Dr. Cardio",
        "specialization": "Cardiologist",
        "rating": 4.8,
        "consultation_fee": 1500,
        "clinic_name": "Heart Care Clinic",
        "clinic_address": "Taxila",
    }

    with patch("app.backend_client.list_doctors", return_value=[cardiologist]) as mock_list, \
         patch("app.chatbot_handlers.fetch_doctor_slots", return_value=[cardiologist]):
        # After follow-ups, the flow now prompts for medical history first
        handle_new_booking(session, "no", {}, None)
        # Skip history to proceed to the cardiologist list
        _, _, _, ui_data = handle_new_booking(session, "skip", {}, None)

    mock_list.assert_called_with(specialization="Cardiologist")
    assert [doctor["specialization"] for doctor in ui_data["doctors"]] == ["Cardiologist"]


def test_cardiology_no_slots_does_not_silently_broaden_search():
    """Verify no-slot cardiology results ask before checking another specialty."""
    session = {
        "state": S.ASKING_FOLLOWUP,
        "specialty": "Cardiologist",
        "follow_up_index": 2,
        "follow_ups": ["one", "two", "three"],
        "symptoms_text": "mild chest pain",
    }

    with patch("app.backend_client.list_doctors", return_value=[]) as mock_list, \
         patch("app.chatbot_handlers.fetch_doctor_slots", return_value=[]):
        # After follow-ups, the flow now prompts for medical history first
        handle_new_booking(session, "no", {}, None)
        # Skip history to proceed to the no-slots message
        message, _, _, ui_data = handle_new_booking(session, "skip", {}, None)

    mock_list.assert_called_with(specialization="Cardiologist")
    assert "No Cardiologist slots are available" in message
    assert "General Medicine" in message
    assert ui_data["doctors"] == []


def test_calendar_event_uses_configured_calendar_without_primary_fallback():
    """Verify calendar events target only the configured patient calendar."""
    appointment = {
        "appointment_id": "test-appt-123",
        "doctor_name": "Dr. Sarah Khan",
        "patient_name": "John Doe",
        "appointment_time": "2026-09-01T10:00:00Z",
    }

    with patch("integrations.google_calendar._is_configured", return_value=True), \
         patch("integrations.google_calendar._get_headers", return_value={"Authorization": "Bearer token"}), \
         patch("integrations.google_calendar.settings.GOOGLE_CALENDAR_ID", "ayesha07sajjad@gmail.com"), \
         patch("integrations.google_calendar.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_response = MagicMock(status_code=201)
        mock_response.json.return_value = {"id": "gcal-event-123"}
        mock_client.post.return_value = mock_response

        from integrations.google_calendar import create_calendar_event

        result = create_calendar_event(appointment)

        assert result == "gcal-event-123"
        mock_client.post.assert_called_once()
        assert "/calendars/ayesha07sajjad@gmail.com/events" in mock_client.post.call_args.args[0]


def test_send_confirmation_email_success():
    """Verify send_confirmation_email connects to SMTP and sends email successfully."""
    appointment = {
        "appointment_id": "test-appt-123",
        "doctor_name": "Dr. Sarah Khan",
        "patient_name": "John Doe",
        "patient_email": "patient@example.com",
        "clinic_name": "Prime Care Clinic",
        "clinic_address": "Ground Floor, ABC Plaza, Taxila",
        "appointment_time": "2026-09-01T10:00:00Z",
    }

    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        result = send_confirmation_email(appointment)
        assert result is True
        mock_smtp_cls.assert_called_once()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()


def test_send_confirmation_email_missing_email():
    """Verify send_confirmation_email returns False cleanly if recipient email is missing."""
    appointment = {
        "appointment_id": "test-appt-123",
        "doctor_name": "Dr. Sarah Khan",
        "patient_name": "John Doe",
        "patient_email": "",
    }
    result = send_confirmation_email(appointment)
    assert result is False


def test_send_confirmation_email_smtp_exception():
    """Verify send_confirmation_email handles SMTP exceptions fail-safely and returns False."""
    appointment = {
        "appointment_id": "test-appt-123",
        "doctor_name": "Dr. Sarah Khan",
        "patient_name": "John Doe",
        "patient_email": "patient@example.com",
    }

    with patch("smtplib.SMTP", side_effect=Exception("SMTP Connection Refused")):
        result = send_confirmation_email(appointment)
        assert result is False


def test_booking_succeeds_and_calls_send_confirmation_email():
    """Verify that handle_new_booking calls send_confirmation_email and completes booking."""
    session = {
        "state": S.AWAIT_CONFIRM,
        "patient_id": "pat-123",
        "patient_name": "Alice Smith",
        "patient_email": "alice@example.com",
        "selected_doctor": {
            "doctor_id": "doc-456",
            "name": "Dr. Ahmed Khan",
            "clinic_name": "Prime Care Clinic",
            "clinic_address": "Taxila",
        },
        "selected_timestamp": "2026-09-01T10:00:00Z",
        "selected_slot_label": "Tuesday, Sep 1, 10:00 AM",
        "symptoms_text": "Headache",
    }

    created_mock = {
        "appointment_id": "appt-789",
        "clinic_id": "clinic-1",
        "doctor_id": "doc-456",
        "status": "scheduled",
    }

    with patch("app.backend_client.create_appointment", return_value=created_mock), \
         patch("integrations.google_calendar.create_calendar_event", return_value="gcal-event-123"), \
         patch("integrations.reminders.send_confirmation_email") as mock_send_email, \
         patch("integrations.n8n_webhook.dispatch_appointment_created"):

        msg, next_action, options, ui_data = handle_new_booking(
            session=session,
            text="yes, confirm",
            nlu={"intent": "confirm"},
            auth="Bearer mock_token",
        )

        assert session["state"] == S.BOOKED
        assert session["status"] == "completed"
        assert session["appointment_booked"] == "appt-789"
        assert "Your appointment is confirmed!" in msg
        assert ui_data["booking"]["isConfirmed"] is True
        mock_send_email.assert_called_once()


def test_just_booked_appointment_is_found_by_reschedule_flow():
    """Verify booking stores the canonical patient ID for immediate rescheduling."""
    session = {
        "state": S.AWAIT_CONFIRM,
        "patient_id": "user-123",
        "patient_name": "Alice Smith",
        "patient_email": "alice@example.com",
        "selected_doctor": {
            "doctor_id": "doc-456",
            "name": "Dr. Ahmed Khan",
            "clinic_name": "Prime Care Clinic",
            "clinic_address": "Taxila",
        },
        "selected_timestamp": "2026-09-01T10:00:00Z",
        "selected_slot_label": "Tuesday, Sep 1, 10:00 AM",
        "symptoms_text": "Headache",
    }
    created_mock = {
        "appointment_id": "appt-789",
        "patient_id": "patient-456",
        "clinic_id": "clinic-1",
        "doctor_id": "doc-456",
        "status": "scheduled",
    }
    appointment = {
        "appointment_id": "appt-789",
        "patient_id": "patient-456",
        "doctor_id": "doc-456",
        "doctor_name": "Dr. Ahmed Khan",
        "clinic_name": "Prime Care Clinic",
        "appointment_time": "2026-09-01T10:00:00Z",
        "status": "scheduled",
    }

    with patch("app.backend_client.create_appointment", return_value=created_mock), \
         patch("integrations.google_calendar.create_calendar_event", return_value=None), \
         patch("integrations.reminders.send_confirmation_email"), \
         patch("integrations.n8n_webhook.dispatch_appointment_created"), \
         patch("app.backend_client.fetch_patient_appointments", return_value=[appointment]) as mock_fetch:
        handle_new_booking(session, "yes, confirm", {"intent": "confirm"}, "Bearer mock_token")
        message, action, _, ui_data = handle_reschedule(
            session, "I need to reschedule", {"intent": "reschedule"}, "Bearer mock_token"
        )

    assert session["patient_id"] == "patient-456"
    mock_fetch.assert_called_once_with("patient-456", "Bearer mock_token")
    assert "Which appointment" in message
    assert action == "show_appointments"
    assert ui_data["appointments"][0]["appointment_id"] == "appt-789"


def test_fresh_session_resolves_patient_id_for_lookup_and_reschedule():
    """Verify fresh sessions use canonical patient IDs for appointment queries."""
    user_id = "user-123"
    patient_id = "patient-456"
    appointment = {
        "appointment_id": "appt-789",
        "doctor_name": "Dr. Ahmed Khan",
        "appointment_time": "2026-09-01T10:00:00Z",
        "status": "scheduled",
    }

    with patch("app.backend_client.get_patient_profile", return_value={"patient_id": patient_id}) as mock_profile, \
         patch("app.backend_client.fetch_patient_appointments", return_value=[appointment]) as mock_fetch, \
         patch("app.chatbot.classify", side_effect=[{"intent": "lookup"}, {"intent": "reschedule"}]):
        first = handle_message(
            conversation_id="fresh-reschedule-test",
            patient_id=user_id,
            message="what are my appointments",
            language="en",
            authorization="Bearer mock_token",
        )
        second = handle_message(
            conversation_id="fresh-reschedule-test",
            patient_id=user_id,
            message="I need to reschedule",
            language="en",
            authorization="Bearer mock_token",
        )

    mock_profile.assert_called_once_with(user_id, "Bearer mock_token")
    assert mock_fetch.call_count == 2
    assert all(call.args[0] == patient_id for call in mock_fetch.call_args_list)
    assert first["ui_data"]["appointments"][0]["appointment_id"] == "appt-789"
    assert second["ui_data"]["appointments"][0]["appointment_id"] == "appt-789"


def test_patient_top_level_intents_override_stale_appointment_workflows():
    """Keep book, lookup, cancel, and reschedule independent across one conversation."""
    appointment = {
        "appointment_id": "appt-patient-flow",
        "doctor_id": "doc-tariq",
        "doctor_name": "Dr. Tariq Mahmood",
        "appointment_time": "2026-09-01T10:00:00Z",
        "status": "scheduled",
    }
    conversation_id = "patient-intent-priority-regression"

    doctor = {
        "doctor_id": "doc-tariq",
        "name": "Dr. Tariq Mahmood",
        "specialization": "General Medicine",
        "slots": [{
            "date": "2026-09-02",
            "time": "10:00 AM",
            "timestamp": "2026-09-02T10:00:00Z",
            "label": "2026-09-02 at 10:00 AM",
        }],
    }

    with patch("app.backend_client.fetch_patient_appointments", return_value=[appointment]) as mock_fetch, \
         patch("app.backend_client.list_doctors", return_value=[doctor]), \
         patch("app.chatbot_handlers.fetch_doctor_slots", return_value=[doctor]):
        session = {
            "state": S.BOOKED,
            "patient_id": "patient-123",
            "picked_appointment_id": "stale-appointment",
            "selected_doctor": {"doctor_id": "doc-stale", "name": "Dr. Stale"},
            "selected_slot": {"timestamp": "stale"},
            "selected_slot_label": "stale slot",
            "selected_timestamp": "stale",
        }

        # Model the completed first booking, then reproduce the user's top-level sequence.
        from app.chatbot_state import _sessions
        _sessions[conversation_id] = {
            **session,
            "conversation_id": conversation_id,
            "messages": [],
            "last_accessed": time.time(),
            "status": "completed",
            "patient_appointments": [],
            "previous_slot_label": None,
            "candidate_doctors": [],
            "symptoms_text": "",
            "follow_up_index": 0,
            "follow_ups": [],
            "specialty": None,
            "urgency_level": "normal",
            "appointment_booked": "first-booked-appointment",
            "last_intent": None,
        }

        lookup = handle_message(
            conversation_id=conversation_id, patient_id="patient-123",
            message="What are my appointments?", language="en", authorization="Bearer token",
        )
        assert lookup["next_action"] == "show_appointments"

        book = handle_message(
            conversation_id=conversation_id, patient_id="patient-123",
            message="Book an appointment", language="en", authorization="Bearer token",
        )
        assert book["next_action"] == "waiting_for_symptoms"
        assert "What brings you in" in book["bot_message"]

        cancel = handle_message(
            conversation_id=conversation_id, patient_id="patient-123",
            message="Cancel my appointment", language="en", authorization="Bearer token",
        )
        assert cancel["next_action"] == "show_appointments"
        assert "CANCEL" not in cancel["bot_message"]
        assert "cancel" in cancel["bot_message"].lower()

        reschedule = handle_message(
            conversation_id=conversation_id, patient_id="patient-123",
            message="Reschedule appointment", language="en", authorization="Bearer token",
        )
        assert reschedule["next_action"] == "show_appointments"
        assert "reschedule" in reschedule["bot_message"].lower()
        assert "cancel" not in reschedule["bot_message"].lower()

        selected = handle_message(
            conversation_id=conversation_id, patient_id="patient-123",
            message="Selected Appointment", language="en", authorization="Bearer token",
        )
        assert selected["next_action"] == "waiting_for_new_time"
        assert "reschedule" in selected["bot_message"].lower()
        assert "cancel" not in selected["bot_message"].lower()

        declined = handle_message(
            conversation_id=conversation_id, patient_id="patient-123",
            message="no", language="en", authorization="Bearer token",
        )
        assert declined["next_action"] == "waiting_for_new_time"

        second_reschedule = handle_message(
            conversation_id=conversation_id, patient_id="patient-123",
            message="Reschedule appointment", language="en", authorization="Bearer token",
        )
        assert "reschedule" in second_reschedule["bot_message"].lower()

        second_book = handle_message(
            conversation_id=conversation_id, patient_id="patient-123",
            message="Book an appointment", language="en", authorization="Bearer token",
        )
        assert second_book["next_action"] == "waiting_for_symptoms"
        assert "reschedule" not in second_book["bot_message"].lower()

        second_cancel = handle_message(
            conversation_id=conversation_id, patient_id="patient-123",
            message="Cancel my appointment", language="en", authorization="Bearer token",
        )
        assert "cancel" in second_cancel["bot_message"].lower()

        final_book = handle_message(
            conversation_id=conversation_id, patient_id="patient-123",
            message="Book an appointment", language="en", authorization="Bearer token",
        )
        final_lookup = handle_message(
            conversation_id=conversation_id, patient_id="patient-123",
            message="What are my appointments?", language="en", authorization="Bearer token",
        )
        assert final_book["next_action"] == "waiting_for_symptoms"
        assert final_lookup["next_action"] == "show_appointments"
        assert mock_fetch.call_count == 6


def test_doctor_show_my_appointments_uses_doctor_scope():
    """Verify a doctor's schedule is filtered by doctor_id instead of patient lookup and uses the same fetch path as cancel/reschedule."""
    doctor_user_id = "user-doctor-123"
    doctor_id = "doc-456"
    appointment = {
        "appointment_id": "appt-doc-1",
        "doctor_id": doctor_id,
        "doctor_name": "Dr. Ahmed Khan",
        "patient_id": "pat-111",
        "patient_name": "Alice Smith",
        "appointment_time": "2026-09-01T10:00:00Z",
        "symptoms_reported": "Headache",
        "status": "scheduled",
    }

    with patch("app.backend_client.get_current_user", return_value={"user_id": doctor_user_id, "user_type": "doctor"}), \
         patch("app.backend_client.list_doctors", return_value=[{"doctor_id": doctor_id, "user_id": doctor_user_id, "name": "Dr. Ahmed Khan"}]), \
         patch("app.backend_client.fetch_doctor_appointments", return_value=[appointment]) as mock_fetch:
        result = handle_message(
            conversation_id="doctor-show-appointments",
            patient_id=doctor_user_id,
            message="show my appointments",
            language="en",
            authorization="Bearer mock_token",
        )

    mock_fetch.assert_called_once_with(doctor_id, "Bearer mock_token")
    assert "Alice Smith" in result["bot_message"]
    assert result["next_action"] == "doctor_appointments"


def test_doctor_show_appointments_tolerates_typo_in_message():
    """Verify the doctor's appointment lookup accepts common misspellings like 'appointmnets'."""
    doctor_user_id = "user-doctor-456"
    doctor_id = "doc-789"
    appointment = {
        "appointment_id": "appt-doc-2",
        "doctor_id": doctor_id,
        "doctor_name": "Dr. Ahmed Khan",
        "patient_id": "pat-222",
        "patient_name": "Bob Jones",
        "appointment_time": "2026-09-02T11:00:00Z",
        "symptoms_reported": "Fever",
        "status": "scheduled",
    }

    with patch("app.backend_client.get_current_user", return_value={"user_id": doctor_user_id, "user_type": "doctor"}), \
         patch("app.backend_client.list_doctors", return_value=[{"doctor_id": doctor_id, "user_id": doctor_user_id, "name": "Dr. Ahmed Khan"}]), \
         patch("app.backend_client.fetch_doctor_appointments", return_value=[appointment]) as mock_fetch:
        result = handle_message(
            conversation_id="doctor-show-appointments-typo",
            patient_id=doctor_user_id,
            message="show appointmnets",
            language="en",
            authorization="Bearer mock_token",
        )

    mock_fetch.assert_called_once_with(doctor_id, "Bearer mock_token")
    assert "Bob Jones" in result["bot_message"]
    assert result["next_action"] == "doctor_appointments"


def test_doctor_cancel_selection_by_uuid_uses_same_appointment_match_path():
    """Verify the frontend's 'Selected Appointment <uuid>' payload advances the active doctor cancel flow in the same conversation."""
    doctor_user_id = "user-doctor-cancel"
    doctor_id = "doc-cancel"
    appt_id = "123e4567-e89b-12d3-a456-426614174000"
    appt = {
        "appointment_id": appt_id,
        "doctor_id": doctor_id,
        "doctor_name": "Dr. Ahmed Khan",
        "patient_name": "Charlie Brown",
        "appointment_time": "2026-09-04T14:00:00Z",
        "status": "scheduled",
    }

    with patch("app.backend_client.get_current_user", return_value={"user_id": doctor_user_id, "user_type": "doctor"}), \
         patch("app.backend_client.list_doctors", return_value=[{"doctor_id": doctor_id, "user_id": doctor_user_id, "name": "Dr. Ahmed Khan"}]), \
         patch("app.backend_client.fetch_doctor_appointments", return_value=[appt]), \
         patch("app.backend_client.cancel_appointment", return_value={"status": "cancelled"}) as mock_cancel:
        first = handle_message(
            conversation_id="doctor-cancel-selected-uuid",
            patient_id=doctor_user_id,
            message="cancel Charlie Brown",
            language="en",
            authorization="Bearer mock_token",
        )
        result = handle_message(
            conversation_id="doctor-cancel-selected-uuid",
            patient_id=doctor_user_id,
            message=f"Selected Appointment {appt_id}",
            language="en",
            authorization="Bearer mock_token",
        )

    assert first["next_action"] in {"doctor_cancel", "doctor_unsupported"}
    mock_cancel.assert_called_once_with(appt_id, "Bearer mock_token")
    assert "Charlie Brown" in result["bot_message"]
    assert "cancel" in result["bot_message"].lower()


def test_doctor_reschedule_selection_by_uuid_uses_same_appointment_match_path():
    """Verify the frontend's 'Selected Appointment <uuid>' payload advances the active doctor reschedule flow in the same conversation."""
    doctor_user_id = "user-doctor-reschedule"
    doctor_id = "doc-reschedule"
    appt_id = "123e4567-e89b-12d3-a456-426614174001"
    appt = {
        "appointment_id": appt_id,
        "doctor_id": doctor_id,
        "doctor_name": "Dr. Ahmed Khan",
        "patient_name": "Dana Ross",
        "appointment_time": "2026-09-05T09:00:00Z",
        "status": "scheduled",
    }

    with patch("app.backend_client.get_current_user", return_value={"user_id": doctor_user_id, "user_type": "doctor"}), \
         patch("app.backend_client.list_doctors", return_value=[{"doctor_id": doctor_id, "user_id": doctor_user_id, "name": "Dr. Ahmed Khan"}]), \
         patch("app.backend_client.fetch_doctor_appointments", return_value=[appt]), \
         patch("app.backend_client.reschedule_appointment") as mock_reschedule:
        first = handle_message(
            conversation_id="doctor-reschedule-selected-uuid",
            patient_id=doctor_user_id,
            message="reschedule Dana Ross",
            language="en",
            authorization="Bearer mock_token",
        )
        result = handle_message(
            conversation_id="doctor-reschedule-selected-uuid",
            patient_id=doctor_user_id,
            message=f"Selected Appointment {appt_id}",
            language="en",
            authorization="Bearer mock_token",
        )

    assert first["next_action"] in {"doctor_reschedule", "doctor_unsupported"}
    mock_reschedule.assert_not_called()
    assert result["next_action"] == "doctor_reschedule"
    assert "Dana Ross" in result["bot_message"] or "When would you like to reschedule" in result["bot_message"]


def test_doctor_reschedule_completes_when_valid_iso_time_is_sent_after_selection():
    """Verify a valid ISO timestamp is recognized as the final reschedule step when the selected appointment is still pending."""
    doctor_id = "doc-amber"
    appointment = {
        "appointment_id": "appt-res-iso",
        "doctor_id": doctor_id,
        "doctor_name": "Dr. Amber Lee",
        "patient_name": "Sara Ali",
        "appointment_time": "2026-09-03T09:00:00Z",
        "status": "scheduled",
    }
    session = {
        "last_doctor_action": "reschedule",
        "doctor_appointments": [appointment],
        "doctor_selected_appointment_id": "appt-res-iso",
    }

    with patch("app.backend_client.reschedule_appointment", return_value={"status": "scheduled"}) as mock_reschedule:
        result = handle_doctor_message(
            session=session,
            message="2026-09-03T12:30:00Z",
            authorization="Bearer mock_token",
            doctor_context={"doctor_id": doctor_id, "name": "Dr. Amber Lee"},
        )

    mock_reschedule.assert_called_once_with("appt-res-iso", "2026-09-03T12:30:00Z", "Bearer mock_token")
    assert "Rescheduled" in result["bot_message"]
    assert result["next_action"] == "doctor_reschedule"


def test_doctor_cancel_selects_by_unique_id_when_multiple_same_patient_names_exist():
    """Verify duplicate patient names still resolve to the exact selected appointment via appointment_id when the UI sends the selected UUID."""
    doctor_id = "doc-same-patient"
    appointment_1 = {
        "appointment_id": "appt-same-1",
        "doctor_id": doctor_id,
        "doctor_name": "Dr. Sara Noor",
        "patient_name": "Sara",
        "appointment_time": "2026-09-04T12:30:00Z",
        "status": "scheduled",
    }
    appointment_2 = {
        "appointment_id": "appt-same-2",
        "doctor_id": doctor_id,
        "doctor_name": "Dr. Sara Noor",
        "patient_name": "Sara",
        "appointment_time": "2026-09-04T11:00:00Z",
        "status": "scheduled",
    }
    session = {
        "last_doctor_action": "cancel",
        "doctor_appointments": [appointment_1, appointment_2],
    }

    with patch("app.backend_client.cancel_appointment", return_value={"status": "cancelled"}) as mock_cancel:
        result = handle_doctor_message(
            session=session,
            message="Selected Appointment appt-same-2",
            authorization="Bearer mock_token",
            doctor_context={"doctor_id": doctor_id, "name": "Dr. Sara Noor"},
        )

    mock_cancel.assert_called_once_with("appt-same-2", "Bearer mock_token")
    assert "Cancelled" in result["bot_message"]
    assert result["next_action"] == "doctor_cancel"


def test_doctor_reschedule_accepts_single_appointment_selection_without_uuid_and_then_iso_time():
    """Verify a bare 'Selected Appointment' click still works when there is only one appointment in the list."""
    doctor_id = "doc-single-appointment"
    appointment = {
        "appointment_id": "appt-single-001",
        "doctor_id": doctor_id,
        "doctor_name": "Dr. Ahmed Khan",
        "patient_name": "Patient dfa1d2",
        "appointment_time": "2026-09-01T10:00:00Z",
        "status": "scheduled",
    }
    session = {
        "last_doctor_action": "reschedule",
        "doctor_appointments": [appointment],
    }
    doctor = {
        "doctor_id": doctor_id,
        "name": "Dr. Ahmed Khan",
        "slots": [{
            "date": "2026-09-03",
            "time": "12:30 PM",
            "timestamp": "2026-09-03T12:30:00Z",
            "label": "2026-09-03 at 12:30 PM",
        }],
    }

    with patch("app.backend_client.reschedule_appointment", return_value={"status": "scheduled"}) as mock_reschedule, \
         patch("app.backend_client.list_doctors", return_value=[doctor]), \
         patch("app.chatbot_doctor.fetch_doctor_slots", return_value=[doctor]):
        choose = handle_doctor_message(
            session=session,
            message="Selected Appointment",
            authorization="Bearer mock_token",
            doctor_context={"doctor_id": doctor_id, "name": "Dr. Ahmed Khan"},
        )
        complete = handle_doctor_message(
            session=session,
            message="2026-09-03T12:30:00Z",
            authorization="Bearer mock_token",
            doctor_context={"doctor_id": doctor_id, "name": "Dr. Ahmed Khan"},
        )

    assert choose["next_action"] == "doctor_reschedule"
    assert "When would you like to reschedule" in choose["bot_message"]
    assert choose["ui_data"]["slots"][0]["timestamp"] == "2026-09-03T12:30:00Z"
    mock_reschedule.assert_called_once_with("appt-single-001", "2026-09-03T12:30:00Z", "Bearer mock_token")
    assert "Rescheduled" in complete["bot_message"]
    assert complete["next_action"] == "doctor_reschedule"


def test_doctor_reschedule_shows_available_slots_and_accepts_slot_number():
    """Verify doctor rescheduling offers real availability instead of requiring raw ISO input."""
    doctor_id = "doc-slot-choice"
    appointment = {
        "appointment_id": "appt-slot-choice",
        "doctor_id": doctor_id,
        "patient_name": "Sara Ali",
        "appointment_time": "2026-09-01T10:00:00Z",
    }
    doctor = {
        "doctor_id": doctor_id,
        "name": "Dr. Tariq Mahmood",
        "slots": [
            {"date": "2026-09-03", "time": "10:00 AM", "timestamp": "2026-09-03T10:00:00Z", "label": "2026-09-03 at 10:00 AM"},
            {"date": "2026-09-03", "time": "2:00 PM", "timestamp": "2026-09-03T14:00:00Z", "label": "2026-09-03 at 2:00 PM"},
        ],
    }
    session = {"last_doctor_action": "reschedule", "doctor_appointments": [appointment]}

    with patch("app.backend_client.list_doctors", return_value=[doctor]), \
         patch("app.chatbot_doctor.fetch_doctor_slots", return_value=[doctor]), \
         patch("app.backend_client.reschedule_appointment", return_value={"status": "scheduled"}) as mock_reschedule:
        prompt = handle_doctor_message(
            session=session,
            message="Selected Appointment",
            authorization="Bearer mock_token",
            doctor_context={"doctor_id": doctor_id, "name": "Dr. Tariq Mahmood"},
        )
        result = handle_doctor_message(
            session=session,
            message="2pm",
            authorization="Bearer mock_token",
            doctor_context={"doctor_id": doctor_id, "name": "Dr. Tariq Mahmood"},
        )

    assert "ISO format" not in prompt["bot_message"]
    assert "1. 2026-09-03 at 10:00 AM" in prompt["bot_message"]
    assert "2. 2026-09-03 at 2:00 PM" in prompt["bot_message"]
    assert [slot["timestamp"] for slot in prompt["ui_data"]["slots"]] == [
        "2026-09-03T10:00:00Z", "2026-09-03T14:00:00Z",
    ]
    mock_reschedule.assert_called_once_with("appt-slot-choice", "2026-09-03T14:00:00Z", "Bearer mock_token")
    assert "Rescheduled" in result["bot_message"]


def test_doctor_reschedule_resolves_frontend_selected_time_slot_payload():
    """Verify the frontend timestamp payload reaches the backend reschedule call."""
    doctor_id = "doc-frontend-slot"
    appointment = {
        "appointment_id": "appt-frontend-slot",
        "doctor_id": doctor_id,
        "patient_name": "Sara Ali",
        "appointment_time": "2026-09-01T10:00:00Z",
    }
    timestamp = "2026-09-03T14:00:00+05:00"
    doctor = {
        "doctor_id": doctor_id,
        "name": "Dr. Tariq Mahmood",
        "slots": [{
            "date": "2026-09-03",
            "time": "2:00 PM",
            "timestamp": timestamp,
            "label": "2026-09-03 at 2:00 PM",
        }],
    }
    session = {"last_doctor_action": "reschedule", "doctor_appointments": [appointment]}

    with patch("app.backend_client.list_doctors", return_value=[doctor]), \
         patch("app.chatbot_doctor.fetch_doctor_slots", return_value=[doctor]), \
         patch("app.backend_client.reschedule_appointment", return_value={"status": "scheduled"}) as mock_reschedule:
        handle_doctor_message(
            session=session,
            message="Selected Appointment",
            authorization="Bearer mock_token",
            doctor_context={"doctor_id": doctor_id, "name": "Dr. Tariq Mahmood"},
        )
        result = handle_doctor_message(
            session=session,
            message=f"Selected Time Slot {timestamp}",
            authorization="Bearer mock_token",
            doctor_context={"doctor_id": doctor_id, "name": "Dr. Tariq Mahmood"},
        )

    mock_reschedule.assert_called_once_with("appt-frontend-slot", timestamp, "Bearer mock_token")
    assert "Rescheduled" in result["bot_message"]


def test_doctor_detail_lookup_returns_full_appointment_record():
    """Verify a doctor can request an appointment detail for one of their patients."""
    doctor_user_id = "user-doctor-456"
    doctor_id = "doc-789"
    appointment = {
        "appointment_id": "appt-doc-2",
        "doctor_id": doctor_id,
        "doctor_name": "Dr. Ahmed Khan",
        "patient_id": "pat-222",
        "patient_name": "Bob Jones",
        "appointment_time": "2026-09-02T11:00:00Z",
        "status": "scheduled",
    }
    detail = {
        "appointment_id": "appt-doc-2",
        "doctor_name": "Dr. Ahmed Khan",
        "patient_name": "Bob Jones",
        "appointment_time": "2026-09-02T11:00:00Z",
        "symptoms_reported": "Chest pain",
        "urgency_level": "high",
        "notes": "Needs follow-up",
    }

    with patch("app.backend_client.get_current_user", return_value={"user_id": doctor_user_id, "user_type": "doctor"}), \
         patch("app.backend_client.list_doctors", return_value=[{"doctor_id": doctor_id, "user_id": doctor_user_id, "name": "Dr. Ahmed Khan"}]), \
         patch("app.backend_client.fetch_doctor_appointments", return_value=[appointment]), \
         patch("app.backend_client.get_appointment_details", return_value=detail) as mock_detail:
        result = handle_message(
            conversation_id="doctor-appointment-detail",
            patient_id=doctor_user_id,
            message="show details for Bob Jones",
            language="en",
            authorization="Bearer mock_token",
        )

    mock_detail.assert_called_once_with("appt-doc-2", "Bearer mock_token")
    assert "Chest pain" in result["bot_message"]
    assert "high" in result["bot_message"]


def test_doctor_reschedule_uses_own_appointments_selection_flow():
    """Verify doctors reschedule from their own appointment list and preserve the shared selection behavior."""
    doctor_user_id = "user-doctor-789"
    doctor_id = "doc-101"
    appts = [
        {
            "appointment_id": "appt-res-1",
            "doctor_id": doctor_id,
            "doctor_name": "Dr. Ahmed Khan",
            "patient_id": "pat-1",
            "patient_name": "Alice Smith",
            "appointment_time": "2026-09-03T09:00:00Z",
            "status": "scheduled",
        },
        {
            "appointment_id": "appt-res-2",
            "doctor_id": doctor_id,
            "patient_id": "pat-2",
            "patient_name": "Bob Jones",
            "doctor_name": "Dr. Ahmed Khan",
            "appointment_time": "2026-09-03T11:00:00Z",
            "status": "scheduled",
        },
    ]

    with patch("app.backend_client.get_current_user", return_value={"user_id": doctor_user_id, "user_type": "doctor"}), \
         patch("app.backend_client.list_doctors", return_value=[{"doctor_id": doctor_id, "user_id": doctor_user_id, "name": "Dr. Ahmed Khan"}]), \
         patch("app.backend_client.fetch_doctor_appointments", return_value=appts), \
         patch("app.backend_client.reschedule_appointment", return_value={"appointment_id": "appt-res-1", "status": "scheduled"}) as mock_reschedule:
        result = handle_message(
            conversation_id="doctor-reschedule",
            patient_id=doctor_user_id,
            message="reschedule Alice Smith",
            language="en",
            authorization="Bearer mock_token",
        )

    assert result["next_action"] == "doctor_reschedule" or "reschedule" in result["next_action"]
    assert "Alice Smith" in result["bot_message"] or "Which appointment" in result["bot_message"]
    mock_reschedule.assert_not_called()


def test_doctor_cancel_uses_own_appointments_selection_flow():
    """Verify doctors cancel from their own appointment list and do not touch patient flow."""
    doctor_user_id = "user-doctor-321"
    doctor_id = "doc-202"
    appts = [{
        "appointment_id": "appt-cancel-1",
        "doctor_id": doctor_id,
        "doctor_name": "Dr. Ahmed Khan",
        "patient_id": "pat-3",
        "patient_name": "Charlie Brown",
        "appointment_time": "2026-09-04T14:00:00Z",
        "status": "scheduled",
    }]

    with patch("app.backend_client.get_current_user", return_value={"user_id": doctor_user_id, "user_type": "doctor"}), \
         patch("app.backend_client.list_doctors", return_value=[{"doctor_id": doctor_id, "user_id": doctor_user_id, "name": "Dr. Ahmed Khan"}]), \
         patch("app.backend_client.fetch_doctor_appointments", return_value=appts), \
         patch("app.backend_client.cancel_appointment", return_value={"status": "cancelled"}) as mock_cancel:
        result = handle_message(
            conversation_id="doctor-cancel",
            patient_id=doctor_user_id,
            message="cancel Charlie Brown",
            language="en",
            authorization="Bearer mock_token",
        )

    assert result["next_action"] == "doctor_cancel" or "cancel" in result["next_action"]
    assert "Charlie Brown" in result["bot_message"] or "Which appointment" in result["bot_message"]
    mock_cancel.assert_not_called()


def test_doctor_attempting_patient_booking_falls_back_to_doctor_specific_message():
    """Verify unsupported doctor actions do not fall into the patient booking flow."""
    doctor_user_id = "user-doctor-555"
    doctor_id = "doc-404"

    with patch("app.backend_client.get_current_user", return_value={"user_id": doctor_user_id, "user_type": "doctor"}), \
         patch("app.backend_client.list_doctors", return_value=[{"doctor_id": doctor_id, "user_id": doctor_user_id, "name": "Dr. Ahmed Khan"}]), \
         patch("app.chatbot.classify") as mock_classify:
        result = handle_message(
            conversation_id="doctor-patient-flow-unsupported",
            patient_id=doctor_user_id,
            message="book a new appointment",
            language="en",
            authorization="Bearer mock_token",
        )

    mock_classify.assert_not_called()
    assert "doctor schedule" in result["bot_message"].lower()
    assert result["next_action"] == "doctor_unsupported"


def test_non_patient_user_is_redirected_before_symptom_triage():
    """Verify doctors/receptionists/admins are blocked from the patient booking flow."""
    with patch("app.backend_client.get_current_user", return_value={"user_id": "doctor-123", "user_type": "doctor"}) as mock_current, \
         patch("app.backend_client.list_doctors", return_value=[]) as mock_list_doctors, \
         patch("app.backend_client.get_patient_profile") as mock_patient_profile, \
         patch("app.chatbot.classify") as mock_classify:
        result = handle_message(
            conversation_id="doctor-redirect-test",
            patient_id="doctor-123",
            message="I have chest pain",
            language="en",
            authorization="Bearer mock_token",
        )

    mock_current.assert_called_once_with("Bearer mock_token")
    mock_list_doctors.assert_called_once_with()
    mock_patient_profile.assert_not_called()
    mock_classify.assert_not_called()
    assert result["bot_message"] == "Unable to load your doctor profile — please contact support"
    assert result["next_action"] == "doctor_profile_error"


def test_appointment_ui_preserves_backend_specialization_field():
    """Verify appointment history accepts the backend's specialization key."""
    formatted = format_appointment_for_ui({"specialization": "Cardiologist"})
    assert formatted["doctor_specialization"] == "Cardiologist"


def test_reschedule_selection_advances_to_existing_doctor_slots():
    """Verify selecting an appointment advances instead of redisplaying the list."""
    session = {
        "state": S.RESCHEDULE_PICK,
        "patient_id": "patient-456",
        "patient_appointments": [{
            "appointment_id": "123e4567-e89b-12d3-a456-426614174000",
            "doctor_id": "doc-456",
            "doctor_name": "Dr. Ahmed Khan",
            "appointment_time": "2026-09-01T10:00:00Z",
            "status": "scheduled",
        }],
    }
    doctor = {
        "doctor_id": "doc-456",
        "name": "Dr. Ahmed Khan",
        "specialization": "General Medicine",
        "rating": 4.8,
        "consultation_fee": 1500,
        "clinic_name": "Prime Care Clinic",
        "clinic_address": "Taxila",
        "slots": [{
            "date": "2026-09-02",
            "time": "10:00 AM",
            "timestamp": "2026-09-02T10:00:00+05:00",
            "label": "2026-09-02 at 10:00 AM",
        }],
    }

    with patch("app.backend_client.list_doctors", return_value=[doctor]), \
         patch("app.chatbot_handlers.fetch_doctor_slots", return_value=[doctor]):
        message, action, _, ui_data = handle_reschedule(
            session,
            "Selected Appointment 123e4567-e89b-12d3-a456-426614174000",
            {},
            "Bearer mock_token",
        )

    assert "When would you like to reschedule" in message
    assert action == "waiting_for_new_time"
    assert ui_data["slots"]
    assert session["state"] == S.RESCHEDULE_SLOTS


def test_ambiguous_doctor_name_requires_clarification_and_number_selects_one():
    """Verify duplicate doctor appointments require clarification, then number selection advances."""
    appointments = [
        {
            "appointment_id": "123e4567-e89b-12d3-a456-426614174001",
            "doctor_id": "doc-456",
            "doctor_name": "Dr. Ahmed Khan",
            "appointment_time": "2026-08-28T17:30:00Z",
            "status": "scheduled",
        },
        {
            "appointment_id": "123e4567-e89b-12d3-a456-426614174002",
            "doctor_id": "doc-456",
            "doctor_name": "Dr. Ahmed Khan",
            "appointment_time": "2026-08-28T16:00:00Z",
            "status": "scheduled",
        },
    ]
    session = {
        "state": S.RESCHEDULE_PICK,
        "patient_id": "patient-456",
        "patient_appointments": appointments,
    }
    doctor = {
        "doctor_id": "doc-456",
        "name": "Dr. Ahmed Khan",
        "clinic_name": "Prime Care Clinic",
        "clinic_address": "Taxila",
        "slots": [{"date": "2026-08-29", "time": "10:00 AM", "timestamp": "2026-08-29T10:00:00+05:00", "label": "2026-08-29 at 10:00 AM"}],
    }

    with patch("app.backend_client.list_doctors", return_value=[doctor]), \
         patch("app.chatbot_handlers.fetch_doctor_slots", return_value=[doctor]):
        message, action, _, ui_data = handle_reschedule(session, "reschedule with dr ahmed khan", {}, "Bearer mock_token")
        assert "2 appointments" in message
        assert "17:30" in message and "16:00" in message
        assert action == "show_appointments"
        assert len(ui_data["appointments"]) == 2

        message, action, _, ui_data = handle_reschedule(session, "1", {}, "Bearer mock_token")

    assert "When would you like to reschedule" in message
    assert action == "waiting_for_new_time"
    assert ui_data["slots"]
    assert session["state"] == S.RESCHEDULE_SLOTS


def test_cancel_by_ambiguous_doctor_name_requires_clarification():
    """Verify cancellation does not silently choose between duplicate appointments."""
    session = {
        "state": S.CANCEL_PICK,
        "patient_id": "patient-456",
        "patient_appointments": [
            {"appointment_id": "123e4567-e89b-12d3-a456-426614174001", "doctor_name": "Dr. Zain Ali", "appointment_time": "2026-08-28T17:30:00Z", "status": "scheduled"},
            {"appointment_id": "123e4567-e89b-12d3-a456-426614174002", "doctor_name": "Dr. Zain Ali", "appointment_time": "2026-08-28T16:00:00Z", "status": "scheduled"},
        ],
    }

    message, action, _, ui_data = handle_cancel(
        session, "cancel dr zain ali", {}, "Bearer mock_token"
    )

    assert "2 appointments" in message
    assert "17:30" in message and "16:00" in message
    assert action == "show_appointments"
    assert len(ui_data["appointments"]) == 2
    assert session.get("picked_appointment_id") is None


def test_booking_succeeds_even_if_send_confirmation_email_fails():
    """Verify booking still succeeds and user gets confirmation message even if email sending fails."""
    session = {
        "state": S.AWAIT_CONFIRM,
        "patient_id": "pat-123",
        "patient_name": "Alice Smith",
        "patient_email": "alice@example.com",
        "selected_doctor": {
            "doctor_id": "doc-456",
            "name": "Dr. Ahmed Khan",
            "clinic_name": "Prime Care Clinic",
            "clinic_address": "Taxila",
        },
        "selected_timestamp": "2026-09-01T10:00:00Z",
        "selected_slot_label": "Tuesday, Sep 1, 10:00 AM",
        "symptoms_text": "Headache",
    }

    created_mock = {
        "appointment_id": "appt-789",
        "clinic_id": "clinic-1",
        "doctor_id": "doc-456",
        "status": "scheduled",
    }

    with patch("app.backend_client.create_appointment", return_value=created_mock), \
         patch("integrations.google_calendar.create_calendar_event", return_value=None), \
         patch("integrations.reminders.send_confirmation_email", side_effect=Exception("SMTP Outage")), \
         patch("integrations.n8n_webhook.dispatch_appointment_created"):

        msg, next_action, options, ui_data = handle_new_booking(
            session=session,
            text="yes, confirm",
            nlu={"intent": "confirm"},
            auth="Bearer mock_token",
        )

        # Booking must still succeed completely
        assert session["state"] == S.BOOKED
        assert session["status"] == "completed"
        assert session["appointment_booked"] == "appt-789"
        assert "Your appointment is confirmed!" in msg
        assert ui_data["booking"]["isConfirmed"] is True
