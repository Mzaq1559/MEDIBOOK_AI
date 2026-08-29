"""In-memory cache for medical knowledge retrieval (no PHI)."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Optional

from app.rag.config import rag_settings
from app.rag.metrics import metrics


class RetrievalCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def _key(self, normalized_query: str, clinic_id: Optional[str]) -> str:
        raw = f"{normalized_query}|{clinic_id or 'global'}|{rag_settings.RAG_KNOWLEDGE_VERSION}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, normalized_query: str, clinic_id: Optional[str]) -> Optional[Any]:
        if not rag_settings.RAG_CACHE_ENABLED:
            return None
        key = self._key(normalized_query, clinic_id)
        entry = self._store.get(key)
        if not entry:
            metrics.inc("rag_cache_misses")
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            self._store.pop(key, None)
            metrics.inc("rag_cache_misses")
            return None
        metrics.inc("rag_cache_hits")
        return value

    def set(self, normalized_query: str, clinic_id: Optional[str], value: Any) -> None:
        if not rag_settings.RAG_CACHE_ENABLED:
            return
        key = self._key(normalized_query, clinic_id)
        expires_at = time.time() + rag_settings.RAG_CACHE_TTL_SECONDS
        self._store[key] = (expires_at, value)

    def clear(self) -> None:
        self._store.clear()


retrieval_cache = RetrievalCache()
