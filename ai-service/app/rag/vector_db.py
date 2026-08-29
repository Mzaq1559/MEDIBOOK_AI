"""ChromaDB vector database manager with persistent storage."""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.rag.config import rag_settings
from app.rag.metrics import metrics

logger = logging.getLogger("medibook.ai.rag.vector_db")

_collection: Any = None
_client: Any = None


def _import_chromadb():
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
    except ImportError as exc:
        raise RuntimeError("chromadb is not installed") from exc
    return chromadb, ChromaSettings


def get_chroma_client():
    global _client
    if _client is None:
        chromadb, ChromaSettings = _import_chromadb()
        path = str(rag_settings.vector_db_path)
        rag_settings.vector_db_path.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_collection():
    global _collection
    if _collection is None:
        client = get_chroma_client()
        _collection = client.get_or_create_collection(
            name=rag_settings.RAG_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        metrics.set_document_count(_collection.count())
    return _collection


def reset_collection() -> None:
    global _collection, _client
    client = get_chroma_client()
    try:
        client.delete_collection(rag_settings.RAG_COLLECTION_NAME)
    except Exception:
        pass
    _collection = None
    get_collection()


def upsert_documents(
    ids: list[str],
    documents: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict[str, Any]],
) -> int:
    collection = get_collection()
    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    count = collection.count()
    metrics.set_document_count(count)
    return count


def query_vectors(
    embedding: list[float],
    *,
    top_k: int,
    where: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    collection = get_collection()
    kwargs: dict[str, Any] = {
        "query_embeddings": [embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    return collection.query(**kwargs)


def health_status() -> dict[str, str]:
    try:
        collection = get_collection()
        count = collection.count()
        metrics.set_document_count(count)
        return {
            "vector_db": "healthy",
            "collection": rag_settings.RAG_COLLECTION_NAME,
            "document_count": str(count),
        }
    except Exception as exc:
        logger.warning("Vector DB health check failed: %s", exc)
        return {
            "vector_db": "unhealthy",
            "collection": rag_settings.RAG_COLLECTION_NAME,
            "document_count": "0",
        }
