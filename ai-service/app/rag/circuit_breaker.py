"""Lightweight circuit breaker for RAG failures."""

from __future__ import annotations

import logging
import time
from enum import Enum

from app.rag.config import rag_settings

logger = logging.getLogger("medibook.ai.rag.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class RAGCircuitBreaker:
    def __init__(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            elapsed = time.time() - self._opened_at
            if elapsed >= rag_settings.RAG_CIRCUIT_BREAKER_COOLDOWN_SECONDS:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def allow_request(self) -> bool:
        st = self.state
        return st in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        self._failure_count = 0
        self._opened_at = None
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= rag_settings.RAG_CIRCUIT_BREAKER_THRESHOLD:
            self._state = CircuitState.OPEN
            self._opened_at = time.time()
            logger.warning("RAG circuit breaker OPEN after %s failures", self._failure_count)

    def reset(self) -> None:
        self._failure_count = 0
        self._opened_at = None
        self._state = CircuitState.CLOSED


circuit_breaker = RAGCircuitBreaker()
