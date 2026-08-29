"""Lightweight in-process RAG metrics counters."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class RAGMetrics:
    rag_requests_total: int = 0
    rag_success_total: int = 0
    rag_fallback_total: int = 0
    rag_errors_total: int = 0
    rag_cache_hits: int = 0
    rag_cache_misses: int = 0
    rag_documents_count: int = 0
    rag_retrieval_latency_ms: list[float] = field(default_factory=list)
    rag_generation_latency_ms: list[float] = field(default_factory=list)
    rag_total_latency_ms: list[float] = field(default_factory=list)
    agent_tool_calls_total: int = 0
    agent_write_confirmations_total: int = 0
    agent_fallback_total: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            current = getattr(self, name, 0)
            setattr(self, name, current + value)

    def record_latency(self, name: str, ms: float) -> None:
        with self._lock:
            bucket: list[float] = getattr(self, name)
            bucket.append(ms)
            if len(bucket) > 200:
                del bucket[: len(bucket) - 200]

    def set_document_count(self, count: int) -> None:
        with self._lock:
            self.rag_documents_count = count

    def snapshot(self) -> dict:
        with self._lock:
            def _avg(vals: list[float]) -> float:
                return round(sum(vals) / len(vals), 2) if vals else 0.0

            return {
                "rag_requests_total": self.rag_requests_total,
                "rag_success_total": self.rag_success_total,
                "rag_fallback_total": self.rag_fallback_total,
                "rag_errors_total": self.rag_errors_total,
                "rag_cache_hits": self.rag_cache_hits,
                "rag_cache_misses": self.rag_cache_misses,
                "rag_documents_count": self.rag_documents_count,
                "rag_retrieval_latency_avg_ms": _avg(self.rag_retrieval_latency_ms),
                "rag_generation_latency_avg_ms": _avg(self.rag_generation_latency_ms),
                "rag_total_latency_avg_ms": _avg(self.rag_total_latency_ms),
                "agent_tool_calls_total": self.agent_tool_calls_total,
                "agent_write_confirmations_total": self.agent_write_confirmations_total,
                "agent_fallback_total": self.agent_fallback_total,
            }


metrics = RAGMetrics()
