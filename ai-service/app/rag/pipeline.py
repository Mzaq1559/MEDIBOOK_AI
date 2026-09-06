"""RAG triage pipeline orchestrating safety, retrieval, generation, and fallback."""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import Any, Optional

from app.rag.augmentation import PromptAugmenter
from app.rag.circuit_breaker import circuit_breaker
from app.rag.config import rag_settings
from app.rag.generator import RAGGenerator
from app.rag.metrics import metrics
from app.rag.models import SourceReference, TriageResult
from app.rag.retriever import MedicalKnowledgeRetriever, normalize_query
from app.rag.safety import (
    URGENCY_TO_LEVEL,
    build_bot_message,
    check_emergency,
    deterministic_fallback,
    emergency_result,
    map_specialty_to_backend,
    validate_llm_against_emergency,
)

logger = logging.getLogger("medibook.ai.rag.pipeline")


class RAGPipeline:
    def __init__(self) -> None:
        self.retriever = MedicalKnowledgeRetriever()
        self.generator = RAGGenerator()
        self.augmenter = PromptAugmenter()

    def triage_symptoms(
        self,
        message: str,
        *,
        conversation_context: str = "",
        clinic_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> TriageResult:
        start = time.perf_counter()
        metrics.inc("rag_requests_total")

        if check_emergency(message):
            logger.info(
                "RAG skipped — emergency detected request_id=%s", request_id or "n/a"
            )
            return emergency_result()

        if not rag_settings.RAG_ENABLED:
            result = deterministic_fallback(message)
            result.fallback_used = True
            metrics.inc("rag_fallback_total")
            return result

        if not circuit_breaker.allow_request():
            logger.warning("RAG circuit breaker open — using fallback request_id=%s", request_id)
            result = deterministic_fallback(message)
            result.fallback_used = True
            metrics.inc("rag_fallback_total")
            return result

        try:
            retrieval_start = time.perf_counter()
            query = normalize_query(message)
            retrieved, retrieval_status = self.retriever.retrieve(query, clinic_id=clinic_id)
            retrieval_ms = (time.perf_counter() - retrieval_start) * 1000
            metrics.record_latency("rag_retrieval_latency_ms", retrieval_ms)

            if retrieval_status == "error":
                raise RuntimeError("RAG retrieval failed")

            generation_start = time.perf_counter()
            if retrieval_status == "insufficient_context":
                llm = self._insufficient_context_response(message)
            else:
                llm = self.generator.generate(
                    message,
                    conversation_context,
                    retrieved,
                    retrieval_status=retrieval_status,
                )
            generation_ms = (time.perf_counter() - generation_start) * 1000
            metrics.record_latency("rag_generation_latency_ms", generation_ms)

            llm = validate_llm_against_emergency(message, llm)
            if llm.needs_emergency_care or check_emergency(message):
                circuit_breaker.record_success()
                return emergency_result()

            sources = llm.sources or [
                SourceReference(id=d.id, title=d.title, type=d.doc_type) for d in retrieved[:3]
            ]
            backend_spec = map_specialty_to_backend(llm.specialty)
            urgency_level = URGENCY_TO_LEVEL.get(llm.urgency, "normal")
            # Derive urgency reason from LLM red flags and urgency level
            if llm.needs_emergency_care:
                urgency_reason = "standalone_emergency_pattern"
            elif llm.red_flags:
                urgency_reason = "high_urgency_marker"
            elif llm.specialty and llm.specialty.lower() in ("cardiologist", "cardiology"):
                urgency_reason = "cardiology_route"
            elif llm.specialty:
                urgency_reason = "specialty_route"
            else:
                urgency_reason = "insufficient_detail"

            result = TriageResult(
                bot_message=build_bot_message(llm, sources),
                specialty=llm.specialty,
                backend_specialization=backend_spec,
                urgency_level=urgency_level,
                urgency_reason=urgency_reason,
                confidence=llm.confidence,
                sources=sources,
                rag_used=True,
                rag_status=retrieval_status,
                fallback_used=False,
                needs_emergency_care=False,
            )
            circuit_breaker.record_success()
            metrics.inc("rag_success_total")
            total_ms = (time.perf_counter() - start) * 1000
            metrics.record_latency("rag_total_latency_ms", total_ms)
            self._audit_log(
                request_id=request_id,
                retrieval_status=retrieval_status,
                source_ids=[s.id for s in sources],
                retrieval_count=len(retrieved),
                fallback_used=False,
                retrieval_ms=retrieval_ms,
                generation_ms=generation_ms,
                total_ms=total_ms,
            )
            return result

        except Exception as exc:
            logger.warning("RAG fallback activated: %s", exc, exc_info=True)
            circuit_breaker.record_failure()
            metrics.inc("rag_errors_total")
            metrics.inc("rag_fallback_total")
            result = deterministic_fallback(message)
            result.fallback_used = True
            total_ms = (time.perf_counter() - start) * 1000
            metrics.record_latency("rag_total_latency_ms", total_ms)
            self._audit_log(
                request_id=request_id,
                retrieval_status="error",
                source_ids=[],
                retrieval_count=0,
                fallback_used=True,
                retrieval_ms=0,
                generation_ms=0,
                total_ms=total_ms,
            )
            return result

    def _insufficient_context_response(self, message: str) -> Any:
        from app.rag.models import TriageLLMResponse

        fallback = deterministic_fallback(message)
        urgency_map = {
            "low": "routine",
            "normal": "routine",
            "high": "urgent",
            "critical": "emergency",
        }
        return TriageLLMResponse(
            urgency=urgency_map.get(fallback.urgency_level, "routine"),
            specialty=fallback.specialty or "General Physician",
            recommendation=fallback.bot_message,
            reasoning_summary="Limited matching medical knowledge was found for these symptoms.",
            red_flags=[],
            confidence="low",
            needs_emergency_care=False,
            sources=[],
        )

    def _audit_log(
        self,
        *,
        request_id: Optional[str],
        retrieval_status: str,
        source_ids: list[str],
        retrieval_count: int,
        fallback_used: bool,
        retrieval_ms: float,
        generation_ms: float,
        total_ms: float,
    ) -> None:
        logger.info(
            "rag_audit request_id=%s rag_used=%s retrieval_status=%s retrieval_count=%s "
            "source_ids=%s fallback_used=%s retrieval_ms=%.1f generation_ms=%.1f total_ms=%.1f",
            request_id or "n/a",
            True,
            retrieval_status,
            retrieval_count,
            source_ids,
            fallback_used,
            retrieval_ms,
            generation_ms,
            total_ms,
        )


@lru_cache
def get_rag_pipeline() -> RAGPipeline:
    return RAGPipeline()
