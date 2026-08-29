"""RAG configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"
_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"


class RAGSettings(BaseSettings):
    RAG_ENABLED: bool = True
    RAG_VECTOR_DB_PATH: str = "/app/data/chroma"
    RAG_COLLECTION_NAME: str = "medical_knowledge"
    RAG_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    RAG_TOP_K: int = 5
    RAG_MIN_RELEVANCE_SCORE: float = 0.35
    RAG_CACHE_ENABLED: bool = True
    RAG_CACHE_TTL_SECONDS: int = 3600
    RAG_CIRCUIT_BREAKER_THRESHOLD: int = 5
    RAG_CIRCUIT_BREAKER_COOLDOWN_SECONDS: int = 60
    RAG_KNOWLEDGE_VERSION: str = "1.0"
    RAG_AUTO_LOAD_ON_STARTUP: bool = True

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def knowledge_base_dir(self) -> Path:
        return _KNOWLEDGE_DIR

    @property
    def vector_db_path(self) -> Path:
        return Path(self.RAG_VECTOR_DB_PATH)


@lru_cache
def get_rag_settings() -> RAGSettings:
    return RAGSettings()


rag_settings = get_rag_settings()
