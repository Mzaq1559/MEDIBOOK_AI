"""Medical knowledge retriever with metadata filtering and relevance threshold."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.rag.cache import retrieval_cache
from app.rag.config import rag_settings
from app.rag.embeddings import embed_query
from app.rag.models import RetrievedDocument
from app.rag.vector_db import query_vectors

logger = logging.getLogger("medibook.ai.rag.retriever")


def normalize_query(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip().lower())
    return cleaned


def _distance_to_score(distance: float) -> float:
    # Chroma cosine distance: 0 = identical, 2 = opposite
    return max(0.0, min(1.0, 1.0 - (distance / 2.0)))


def _build_where_filter(clinic_id: Optional[str]) -> Optional[dict[str, Any]]:
    if clinic_id:
        return {
            "$or": [
                {"clinic_id": ""},
                {"clinic_id": clinic_id},
            ]
        }
    return None


def _dedupe(results: list[RetrievedDocument]) -> list[RetrievedDocument]:
    seen: set[str] = set()
    unique: list[RetrievedDocument] = []
    for doc in results:
        key = doc.id
        if key in seen:
            continue
        seen.add(key)
        unique.append(doc)
    return unique


class MedicalKnowledgeRetriever:
    def retrieve(
        self,
        query: str,
        *,
        clinic_id: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> tuple[list[RetrievedDocument], str]:
        normalized = normalize_query(query)
        if not normalized:
            return [], "insufficient_context"

        cached = retrieval_cache.get(normalized, clinic_id)
        if cached is not None:
            return cached["documents"], cached["status"]

        try:
            embedding = embed_query(normalized)
        except Exception as exc:
            logger.warning("RAG retrieval failed during embedding: %s", exc)
            return [], "error"

        k = top_k or rag_settings.RAG_TOP_K
        where = _build_where_filter(clinic_id)

        try:
            raw = query_vectors(embedding, top_k=k, where=where)
        except Exception as exc:
            logger.warning("RAG retrieval failed during vector query: %s", exc)
            return [], "error"

        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        results: list[RetrievedDocument] = []
        for doc_id, content, meta, dist in zip(ids, documents, metadatas, distances):
            score = _distance_to_score(float(dist))
            if score < rag_settings.RAG_MIN_RELEVANCE_SCORE:
                continue
            metadata = dict(meta or {})
            results.append(
                RetrievedDocument(
                    id=str(metadata.get("doc_id") or doc_id),
                    content=content or "",
                    score=round(score, 4),
                    metadata=metadata,
                )
            )

        results = _dedupe(results)
        status = "success" if results else "insufficient_context"
        retrieval_cache.set(normalized, clinic_id, {"documents": results, "status": status})
        return results, status
