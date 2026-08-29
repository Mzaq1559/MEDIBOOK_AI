"""Embedding service using sentence-transformers."""

from __future__ import annotations

import logging
from typing import Optional

from app.rag.config import rag_settings

logger = logging.getLogger("medibook.ai.rag.embeddings")

_model = None
_model_loaded = False
_model_error: Optional[str] = None


def _load_model():
    global _model, _model_loaded, _model_error
    if _model_loaded:
        return _model
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(rag_settings.RAG_EMBEDDING_MODEL)
        _model_loaded = True
        _model_error = None
        logger.info("Embedding model loaded: %s", rag_settings.RAG_EMBEDDING_MODEL)
    except Exception as exc:
        _model_error = str(exc)
        _model_loaded = True
        logger.error("Failed to load embedding model: %s", exc)
        raise
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _load_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def embedding_status() -> str:
    if _model_error:
        return "error"
    try:
        _load_model()
        return "loaded" if _model is not None else "error"
    except Exception:
        return "error"
