"""Unit tests for Doctor Agent functionality, suggestions, routing, and backend methods."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from app import backend_client
from app.chatbot import handle_message, handle_message_stream, new_session
from app.chatbot_doctor import handle_doctor_message
from app.chatbot_nlu import classify, CANCEL_RE, RESCHEDULE_RE, LOOKUP_RE


SAMPLE_DOCTOR_CONTEXT = {
    "doctor_id": "doc-ahmed-123",
    "user_id": "user-doc-123",
    "name": "Dr. Ahmed Khan",
    "specialization": "Cardiology",
}

SAMPLE_APPOINTMENTS = [
    {
        "appointment_id": "c1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c",
        "doctor_id": "doc-ahmed-123",
        "doctor_name": "Dr. Ahmed Khan",
        "patient_name": "Ali Hassan",
        "appointment_time": "2026-09-10T10:00:00+05:00",
        "status": "scheduled",
        "symptoms_reported": "Chest heaviness and fatigue",
        "urgency_level": "high",
        "notes": "Follow up on ECG",
    },
    {
        "appointment_id": "d2b3c4d5-e6f7-4a8b-9c0d-1e2f3a4b5c6d",
        "doctor_id": "doc-ahmed-123",
        "doctor_name": "Dr. Ahmed Khan",
        "patient_name": "Fatima Noor",
        "appointment_time": "2026-09-10T11:30:00+05:00",
        "status": "scheduled",
        "symptoms_reported": "Routine checkup",
        "urgency_level": "normal",
        "notes": "Annual review",
    },
]


class TestDoctorNLUClassification:
    def test_regex_matching_english_and_urdu(self):
        # Lookup
        assert LOOKUP_RE.search("Show my appointments")
        assert LOOKUP_RE.search("What are my appointments?")
        assert LOOKUP_RE.search("meri appointment dikhao")
        assert LOOKUP_RE.search("میری اپوائنٹمنٹ دکھاؤ")

        # Cancel
        assert CANCEL_RE.search("Cancel appointment")
        assert CANCEL_RE.search("Cancel a patient's appointment")
        assert CANCEL_RE.search("appointment cancel kar do")
        assert CANCEL_RE.search("کینسل کر دو")

        # Reschedule
        assert RESCHEDULE_RE.search("Reschedule appointment")
        assert RESCHEDULE_RE.search("Reschedule a patient's appointment")
        assert RESCHEDULE_RE.search("waqt badal do")
        assert RESCHEDULE_RE.search("دوبارہ بک کرو")

    def test_classify_doctor_intents_via_regex_override(self):
        # When groq fails or is not called, regex overrides fire reliably
        with patch("app.groq_client.complete_json", side_effect=Exception("Mock LLM offline")):
            res_lookup = classify("Show my appointments")
            assert res_lookup["intent"] == "lookup"

            res_cancel = classify("Cancel appointment")
            assert res_cancel["intent"] == "cancel"

            res_reschedule = classify("Reschedule appointment")
            assert res_reschedule["intent"] == "reschedule"

            res_urdu_cancel = classify("میری اپوائنٹمنٹ کینسل کر دو")
            assert res_urdu_cancel["intent"] == "cancel"

    def test_classify_patient_details_intent(self):
        mock_result = {
            "intent": "patient_details",
            "doctor_name": None,
            "patient_name": "Ali",
            "specialty": None,
            "wants_doctor_list": False,
            "date": None,
            "symptoms": None,
            "appointment_id": None,
            "confirms": False,
            "declines": False,
            "faq_topic": None,
            "option_id": None,
        }
        with patch("app.groq_client.complete_json", return_value=mock_result):
            res = classify("Show Ali's details")
            assert res["intent"] == "patient_details"


class TestDoctorChatWorkflow:
    @pytest.fixture
    def session(self):
        return new_session("conv-doc-1", None)

    @patch("app.backend_client.fetch_doctor_appointments", return_value=SAMPLE_APPOINTMENTS)
    def test_show_my_appointments(self, mock_fetch, session):
        res = handle_doctor_message(
            session=session,
            message="Show my appointments",
            authorization="Bearer valid-doctor-token",
            doctor_context=SAMPLE_DOCTOR_CONTEXT,
        )
        assert res["next_action"] == "doctor_appointments"
        assert "appointments" in res["ui_data"]
        assert len(res["ui_data"]["appointments"]) == 2
        assert "Ali Hassan" in res["bot_message"]
        assert session.get("last_doctor_action") == "lookup"

    @patch("app.backend_client.fetch_doctor_appointments", return_value=SAMPLE_APPOINTMENTS)
    def test_cancel_appointment_flow(self, mock_fetch, session):
        # Turn 1: Doctor requests to cancel
        res_t1 = handle_doctor_message(
            session=session,
            message="Cancel appointment",
            authorization="Bearer valid-doctor-token",
            doctor_context=SAMPLE_DOCTOR_CONTEXT,
        )
        assert res_t1["next_action"] == "doctor_cancel"
        assert len(res_t1["ui_data"]["appointments"]) == 2
        assert session.get("last_doctor_action") == "cancel"

        # Turn 2: Doctor selects the first appointment
        with patch("app.backend_client.cancel_appointment", return_value={"status": "cancelled"}) as mock_cancel:
            res_t2 = handle_doctor_message(
                session=session,
                message=f"Selected Appointment {SAMPLE_APPOINTMENTS[0]['appointment_id']}",
                authorization="Bearer valid-doctor-token",
                doctor_context=SAMPLE_DOCTOR_CONTEXT,
            )
            mock_cancel.assert_called_once_with(SAMPLE_APPOINTMENTS[0]["appointment_id"], "Bearer valid-doctor-token")
            assert res_t2["next_action"] == "doctor_cancel"
            assert "Cancelled Ali Hassan's appointment" in res_t2["bot_message"]

    @patch("app.backend_client.fetch_doctor_appointments", return_value=SAMPLE_APPOINTMENTS)
    @patch("app.backend_client.list_doctors", return_value=[SAMPLE_DOCTOR_CONTEXT])
    @patch("app.chatbot_doctor.fetch_doctor_slots")
    def test_reschedule_appointment_flow(self, mock_slots, mock_list, mock_fetch, session):
        mock_slots.return_value = [
            {
                **SAMPLE_DOCTOR_CONTEXT,
                "slots": [
                    {
                        "time": "02:00 PM",
                        "date": "2026-09-12",
                        "timestamp": "2026-09-12T14:00:00+05:00",
                        "label": "2026-09-12 at 02:00 PM",
                    }
                ],
            }
        ]

        # Turn 1: Doctor asks to reschedule
        res_t1 = handle_doctor_message(
            session=session,
            message="Reschedule appointment",
            authorization="Bearer valid-doctor-token",
            doctor_context=SAMPLE_DOCTOR_CONTEXT,
        )
        assert res_t1["next_action"] == "doctor_reschedule"
        assert len(res_t1["ui_data"]["appointments"]) == 2

        # Turn 2: Doctor picks appointment -> returns slots
        res_t2 = handle_doctor_message(
            session=session,
            message=f"Selected Appointment {SAMPLE_APPOINTMENTS[0]['appointment_id']}",
            authorization="Bearer valid-doctor-token",
            doctor_context=SAMPLE_DOCTOR_CONTEXT,
        )
        assert res_t2["next_action"] == "doctor_reschedule"
        assert "slots" in res_t2["ui_data"]
        assert len(res_t2["ui_data"]["slots"]) == 1

        # Turn 3: Doctor selects slot -> calls reschedule
        with patch("app.backend_client.reschedule_appointment", return_value={"status": "rescheduled"}) as mock_resched:
            res_t3 = handle_doctor_message(
                session=session,
                message="Selected Time Slot 2026-09-12T14:00:00+05:00",
                authorization="Bearer valid-doctor-token",
                doctor_context=SAMPLE_DOCTOR_CONTEXT,
            )
            mock_resched.assert_called_once_with(
                SAMPLE_APPOINTMENTS[0]["appointment_id"],
                "2026-09-12T14:00:00+05:00",
                "Bearer valid-doctor-token",
            )
            assert res_t3["next_action"] == "doctor_reschedule"
            assert "Rescheduled Ali Hassan's appointment" in res_t3["bot_message"]

    @patch("app.backend_client.fetch_doctor_appointments", return_value=SAMPLE_APPOINTMENTS)
    @patch("app.backend_client.get_appointment_details", return_value={
        **SAMPLE_APPOINTMENTS[0],
        "patient_history": '{"conditions": ["Hypertension"], "allergies": ["Penicillin"]}',
    })
    def test_doctor_patient_details(self, mock_details, mock_fetch, session):
        res = handle_doctor_message(
            session=session,
            message=f"Selected Appointment {SAMPLE_APPOINTMENTS[0]['appointment_id']}",
            authorization="Bearer valid-doctor-token",
            doctor_context=SAMPLE_DOCTOR_CONTEXT,
        )
        assert res["next_action"] == "doctor_appointment_details"
        assert "Ali Hassan" in res["bot_message"]
        assert "Patient Medical Summary" in res["bot_message"]
        assert "Hypertension" in res["bot_message"]
        assert "Penicillin" in res["bot_message"]

    def test_doctor_unsupported_new_booking(self, session):
        with patch("app.chatbot_doctor.classify", return_value={"intent": "appointment"}):
            res = handle_doctor_message(
                session=session,
                message="Book an appointment",
                authorization="Bearer valid-doctor-token",
                doctor_context=SAMPLE_DOCTOR_CONTEXT,
            )
            assert res["next_action"] == "doctor_unsupported"
            assert "dashboard to manage scheduling" in res["bot_message"]


class TestDoctorRoutingInChatbot:
    @patch("app.backend_client.get_current_user")
    @patch("app.backend_client.list_doctors")
    @patch("app.backend_client.fetch_doctor_appointments")
    def test_handle_message_routes_doctor_user(self, mock_fetch, mock_list, mock_get_user):
        mock_get_user.return_value = {
            "user_id": "user-doc-123",
            "doctor_id": "doc-ahmed-123",
            "user_type": "doctor",
            "name": "Dr. Ahmed Khan",
        }
        mock_list.return_value = [SAMPLE_DOCTOR_CONTEXT]
        mock_fetch.return_value = SAMPLE_APPOINTMENTS

        res = handle_message(
            conversation_id="conv-test-route",
            patient_id=None,
            message="Show my appointments",
            language="english",
            authorization="Bearer doc-token",
        )
        assert res["next_action"] == "doctor_appointments"
        assert "appointments" in res["ui_data"]
        assert len(res["ui_data"]["appointments"]) == 2

    @patch("app.backend_client.get_current_user")
    @patch("app.backend_client.list_doctors")
    @patch("app.backend_client.fetch_doctor_appointments")
    def test_handle_message_stream_routes_doctor_user(self, mock_fetch, mock_list, mock_get_user):
        mock_get_user.return_value = {
            "user_id": "user-doc-123",
            "doctor_id": "doc-ahmed-123",
            "user_type": "doctor",
            "name": "Dr. Ahmed Khan",
        }
        mock_list.return_value = [SAMPLE_DOCTOR_CONTEXT]
        mock_fetch.return_value = SAMPLE_APPOINTMENTS

        stream = handle_message_stream(
            conversation_id="conv-test-stream",
            patient_id=None,
            message="Show my appointments",
            language="english",
            authorization="Bearer doc-token",
        )
        events = list(stream)
        assert len(events) >= 2
        assert "event: status" in events[0]
        assert "event: final" in events[-1]

        final_data = json.loads(events[-1].replace("event: final\ndata: ", "").strip())
        assert final_data["next_action"] == "doctor_appointments"
        assert len(final_data["ui_data"]["appointments"]) == 2

    @patch("app.backend_client.get_current_user")
    def test_non_doctor_user_does_not_route_to_doctor_agent(self, mock_get_user):
        mock_get_user.return_value = {
            "user_id": "user-patient-456",
            "user_type": "patient",
            "name": "Patient User",
        }
        # A patient asking an emergency message triggers emergency guard, proving doctor routing did not hijack it
        res = handle_message(
            conversation_id="conv-test-patient",
            patient_id="user-patient-456",
            message="I have severe chest pain",
            language="english",
            authorization="Bearer patient-token",
        )
        assert res["next_action"] == "emergency_redirect"
        assert "EMERGENCY ALERT" in res["bot_message"]
