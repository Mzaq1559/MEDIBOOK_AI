"""Integration tests for chatbot flows with RAG."""

from __future__ import annotations

from unittest.mock import patch

from app.chatbot import handle_message
from app.chatbot_state import S, get_session, new_session
from app.rag.models import SourceReference, TriageResult
from app.symptom_triage import EMERGENCY_ALERT


def _start_booking(conversation_id: str = "test-conv-1"):
    handle_message(
        conversation_id=conversation_id,
        patient_id=None,
        message="I want to book an appointment",
        language="english",
        authorization=None,
    )
    return conversation_id


@patch("app.chatbot_handlers.rag_settings.RAG_ENABLED", False)
def test_booking_flow_starts_without_rag():
    conv_id = _start_booking("booking-flow-1")
    session = get_session(conv_id)
    assert session["state"] == S.ASKING_SYMPTOMS


def test_symptom_triage_uses_rag(monkeypatch):
    monkeypatch.setattr("app.chatbot_handlers.rag_settings.RAG_ENABLED", True)

    class _FakePipeline:
        def triage_symptoms(self, *args, **kwargs):
            return TriageResult(
                bot_message="ENT guidance for sore throat.",
                specialty="ENT Specialist",
                backend_specialization="ENT",
                urgency_level="normal",
                confidence="medium",
                sources=[SourceReference(id="sore_throat_001", title="Sore throat", type="symptom")],
                rag_used=True,
                rag_status="success",
            )

    monkeypatch.setattr("app.rag.pipeline.get_rag_pipeline", lambda: _FakePipeline())

    conv_id = _start_booking("rag-symptom-1")
    result = handle_message(
        conversation_id=conv_id,
        patient_id=None,
        message="I've had a sore throat and cough for two days.",
        language="english",
        authorization=None,
    )
    assert "ENT guidance" in result["bot_message"]
    assert result["ui_data"]["triage"]["rag_used"] is True
    assert result["next_action"] == "waiting_for_input"


def test_emergency_overrides_rag_and_booking():
    conv_id = _start_booking("emergency-1")
    result = handle_message(
        conversation_id=conv_id,
        patient_id=None,
        message="I have severe chest pain and I cannot breathe properly.",
        language="english",
        authorization=None,
    )
    assert result["next_action"] == "emergency_redirect"
    assert "EMERGENCY" in result["bot_message"]
    session = get_session(conv_id)
    assert session["state"] == S.EMERGENCY


@patch("app.chatbot_handlers.rag_settings.RAG_ENABLED", True)
def test_cancel_intent_not_routed_to_rag():
    result = handle_message(
        conversation_id="cancel-1",
        patient_id="33333333-3333-4333-a333-333333333333",
        message="cancel my appointment",
        language="english",
        authorization="Bearer fake-token",
    )
    assert "cancel" in result["bot_message"].lower() or result["next_action"] in (
        "waiting_for_login",
        "show_appointments",
        "waiting_for_input",
    )


@patch("app.chatbot_handlers.rag_settings.RAG_ENABLED", True)
def test_reschedule_intent_not_routed_to_rag():
    result = handle_message(
        conversation_id="reschedule-1",
        patient_id="33333333-3333-4333-a333-333333333333",
        message="reschedule my appointment",
        language="english",
        authorization="Bearer fake-token",
    )
    assert result["next_action"] in (
        "waiting_for_login",
        "show_appointments",
        "waiting_for_input",
        "waiting_for_new_time",
        "waiting_for_reschedule_confirm",
    )
