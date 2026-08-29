"""Tests for RAG pipeline generation and fallback."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app import groq_client
from app.rag.circuit_breaker import circuit_breaker
from app.rag.models import RetrievedDocument, SourceReference, TriageLLMResponse
from app.rag.pipeline import RAGPipeline


def _sample_llm():
    return TriageLLMResponse(
        urgency="routine",
        specialty="ENT Specialist",
        recommendation="An ENT specialist can evaluate sore throat and cough symptoms.",
        reasoning_summary="Symptoms are commonly evaluated by ENT.",
        confidence="medium",
        needs_emergency_care=False,
        sources=[SourceReference(id="sore_throat_001", title="Sore throat", type="symptom")],
    )


@patch("app.rag.pipeline.rag_settings.RAG_ENABLED", True)
def test_pipeline_successful_generation(monkeypatch):
    pipeline = RAGPipeline()

    class FakeRetriever:
        def retrieve(self, query, clinic_id=None, top_k=None):
            return [
                RetrievedDocument(
                    id="sore_throat_001",
                    content="Sore throat guidance",
                    score=0.9,
                    metadata={"type": "symptom", "name": "Sore throat"},
                )
            ], "success"

    pipeline.retriever = FakeRetriever()
    monkeypatch.setattr(pipeline.generator, "generate", lambda *a, **k: _sample_llm())

    result = pipeline.triage_symptoms("I've had a sore throat and cough for two days.")
    assert result.rag_used
    assert result.specialty == "ENT Specialist"
    assert result.fallback_used is False
    assert len(result.sources) >= 1


@patch("app.rag.pipeline.rag_settings.RAG_ENABLED", True)
def test_pipeline_fallback_on_generation_failure(monkeypatch):
    pipeline = RAGPipeline()

    class FakeRetriever:
        def retrieve(self, query, clinic_id=None, top_k=None):
            return [
                RetrievedDocument(
                    id="cough_001",
                    content="Cough guidance",
                    score=0.8,
                    metadata={"type": "symptom", "name": "Cough"},
                )
            ], "success"

    pipeline.retriever = FakeRetriever()

    def _fail(*args, **kwargs):
        raise groq_client.LLMError("fail")

    monkeypatch.setattr(pipeline.generator, "generate", _fail)
    result = pipeline.triage_symptoms("mild cough")
    assert result.fallback_used
    assert result.rag_used is False


@patch("app.rag.pipeline.rag_settings.RAG_ENABLED", True)
def test_pipeline_fallback_on_chroma_failure(monkeypatch):
    pipeline = RAGPipeline()

    class FailingRetriever:
        def retrieve(self, query, clinic_id=None, top_k=None):
            return [], "error"

    pipeline.retriever = FailingRetriever()
    result = pipeline.triage_symptoms("mild cough")
    assert result.fallback_used


@patch("app.rag.pipeline.rag_settings.RAG_ENABLED", False)
def test_pipeline_disabled_uses_deterministic_fallback():
    pipeline = RAGPipeline()
    result = pipeline.triage_symptoms("skin rash itching")
    assert result.fallback_used
    assert result.rag_used is False


@patch("app.rag.pipeline.rag_settings.RAG_ENABLED", True)
def test_circuit_breaker_opens_after_failures(monkeypatch):
    circuit_breaker.reset()
    pipeline = RAGPipeline()

    class FailingRetriever:
        def retrieve(self, query, clinic_id=None, top_k=None):
            raise RuntimeError("chroma down")

    pipeline.retriever = FailingRetriever()
    for _ in range(6):
        pipeline.triage_symptoms("headache")

    assert circuit_breaker.state.value in ("open", "half_open")
