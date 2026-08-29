"""Tests for RAG safety — emergency rules always take priority."""

from app.rag.pipeline import RAGPipeline
from app.rag.safety import check_emergency, emergency_result, validate_llm_against_emergency
from app.rag.models import TriageLLMResponse
from app.symptom_triage import EMERGENCY_ALERT


def test_emergency_chest_pain_and_breathing():
    assert check_emergency("I have severe chest pain and I cannot breathe properly.")


def test_emergency_result_message():
    result = emergency_result()
    assert result.needs_emergency_care
    assert "EMERGENCY" in result.bot_message
    assert result.urgency_level == "critical"


def test_llm_cannot_downgrade_emergency():
    llm = TriageLLMResponse(
        urgency="routine",
        specialty="Cardiologist",
        recommendation="Book a cardiologist appointment.",
        needs_emergency_care=False,
    )
    validated = validate_llm_against_emergency(
        "I have severe chest pain and I cannot breathe properly.",
        llm,
    )
    assert validated.needs_emergency_care
    assert validated.urgency == "emergency"
    assert "EMERGENCY" in validated.recommendation


def test_rag_pipeline_emergency_skips_retrieval(monkeypatch):
  pipeline = RAGPipeline()
  called = {"retrieve": False}

  class FakeRetriever:
    def retrieve(self, *args, **kwargs):
      called["retrieve"] = True
      return [], "success"

  pipeline.retriever = FakeRetriever()
  result = pipeline.triage_symptoms("severe chest pain and cannot breathe")
  assert result.needs_emergency_care
  assert called["retrieve"] is False
  assert EMERGENCY_ALERT in result.bot_message
