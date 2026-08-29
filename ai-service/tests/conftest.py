"""Shared pytest fixtures for RAG tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def rag_test_env(tmp_path, monkeypatch):
    chroma_path = tmp_path / "chroma"
    chroma_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setenv("RAG_VECTOR_DB_PATH", str(chroma_path))
    monkeypatch.setenv("RAG_AUTO_LOAD_ON_STARTUP", "false")
    monkeypatch.setenv("RAG_CACHE_ENABLED", "false")

    # Reset cached singletons between tests
    from app.rag import config as rag_config
    from app.rag import vector_db as vdb
    from app.rag.cache import retrieval_cache
    from app.rag.circuit_breaker import circuit_breaker

    rag_config.get_rag_settings.cache_clear()
    vdb._client = None
    vdb._collection = None
    retrieval_cache.clear()
    circuit_breaker.reset()
    yield
