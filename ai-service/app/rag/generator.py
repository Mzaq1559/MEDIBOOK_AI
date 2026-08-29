"""Grounded LLM generation with structured JSON validation."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import ValidationError

from app import groq_client
from app.rag.augmentation import PromptAugmenter
from app.rag.models import RetrievedDocument, SourceReference, TriageLLMResponse

logger = logging.getLogger("medibook.ai.rag.generator")


class RAGGenerator:
    def __init__(self) -> None:
        self.augmenter = PromptAugmenter()

    def generate(
        self,
        patient_message: str,
        conversation_context: str,
        retrieved: list[RetrievedDocument],
        *,
        retrieval_status: str,
    ) -> TriageLLMResponse:
        messages = self.augmenter.build_messages(
            patient_message,
            conversation_context,
            retrieved,
            retrieval_status=retrieval_status,
        )
        allowed_ids = {doc.id for doc in retrieved}
        allowed_titles = {doc.title.lower(): doc for doc in retrieved}

        for attempt in range(2):
            try:
                raw = groq_client.complete_json(messages, temperature=0.1, max_tokens=700)
                parsed = self._validate_response(raw, allowed_ids, allowed_titles, retrieved)
                return parsed
            except (groq_client.LLMError, ValidationError) as exc:
                logger.warning("RAG generation failed (attempt %s): %s", attempt + 1, exc)
                if attempt == 0:
                    messages = self.augmenter.build_correction_messages(messages, str(exc))
                else:
                    raise

        raise groq_client.LLMError("RAG generation failed")

    def _validate_response(
        self,
        raw: dict[str, Any],
        allowed_ids: set[str],
        allowed_titles: dict[str, RetrievedDocument],
        retrieved: list[RetrievedDocument],
    ) -> TriageLLMResponse:
        response = TriageLLMResponse.model_validate(raw)
        validated_sources: list[SourceReference] = []

        for src in response.sources:
            if src.id in allowed_ids:
                validated_sources.append(src)
                continue
            match = allowed_titles.get(src.title.lower())
            if match:
                validated_sources.append(
                    SourceReference(id=match.id, title=match.title, type=match.doc_type)
                )

        if not validated_sources and retrieved:
            top = retrieved[0]
            validated_sources.append(
                SourceReference(id=top.id, title=top.title, type=top.doc_type)
            )

        response.sources = validated_sources
        return response
