"""Tests for vector DB and retriever."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.rag.knowledge_loader import ensure_knowledge_indexed
from app.rag.retriever import MedicalKnowledgeRetriever, normalize_query
from app.rag import vector_db as vdb


def _fake_embed(texts):
    vectors = []
    for text in texts:
        base = float((hash(text) % 1000) / 1000.0)
        vectors.append([base, 1.0 - base, 0.5])
    return vectors


class _FakeCollection:
    def __init__(self):
        self._docs: dict[str, dict] = {}

    def count(self):
        return len(self._docs)

    def upsert(self, ids, documents, embeddings, metadatas):
        for doc_id, content, embedding, meta in zip(ids, documents, embeddings, metadatas):
            self._docs[doc_id] = {
                "document": content,
                "metadata": meta,
                "embedding": embedding,
            }

    def query(self, query_embeddings, n_results, include=None, where=None):
        # Simple brute-force cosine-ish scoring for tests
        query = query_embeddings[0]
        scored = []
        for doc_id, payload in self._docs.items():
            meta = payload["metadata"]
            clinic_id = meta.get("clinic_id", "")
            if where and "$or" in where:
                allowed = {item.get("clinic_id") for item in where["$or"]}
                if clinic_id and clinic_id not in allowed:
                    continue
            emb = payload["embedding"]
            score = sum(a * b for a, b in zip(query, emb))
            scored.append((score, doc_id, payload))
        scored.sort(reverse=True)
        top = scored[:n_results]
        return {
            "ids": [[doc_id for _, doc_id, _ in top]],
            "documents": [[p["document"] for _, _, p in top]],
            "metadatas": [[p["metadata"] for _, _, p in top]],
            "distances": [[1.0 - s for s, _, _ in top]],
        }


@pytest.fixture
def fake_chroma(monkeypatch):
    collection = _FakeCollection()

    class _FakeClient:
        def get_or_create_collection(self, name, metadata=None):
            return collection

        def delete_collection(self, name):
            collection._docs.clear()

    vdb._client = _FakeClient()
    vdb._collection = collection
    yield collection
    vdb._client = None
    vdb._collection = None


@patch("app.rag.knowledge_loader.embed_texts", side_effect=_fake_embed)
@patch("app.rag.retriever.embed_query", side_effect=lambda q: _fake_embed([q])[0])
def test_knowledge_loader_indexes_documents(mock_embed_query, mock_embed_texts, fake_chroma):
    stats = ensure_knowledge_indexed(rebuild=True)
    assert stats["indexed"] > 0
    assert stats["total"] > 0
    assert fake_chroma.count() > 0


@patch("app.rag.retriever.embed_query", side_effect=lambda q: _fake_embed([q])[0])
@patch("app.rag.knowledge_loader.embed_texts", side_effect=_fake_embed)
def test_retriever_returns_results_for_symptom_query(mock_loader_embed, mock_query_embed, fake_chroma):
    ensure_knowledge_indexed(rebuild=True)
    retriever = MedicalKnowledgeRetriever()
    docs, status = retriever.retrieve("sore throat and cough for two days")
    assert status in ("success", "insufficient_context")
    if status == "success":
        assert len(docs) >= 1
        assert docs[0].score >= 0


@patch("app.rag.retriever.embed_query", side_effect=lambda q: _fake_embed([q])[0])
@patch("app.rag.knowledge_loader.embed_texts", side_effect=_fake_embed)
def test_retriever_clinic_filter_excludes_other_clinic_only_docs(mock_loader_embed, mock_query_embed, fake_chroma):
    fake_chroma.upsert(
        ids=["clinic_only_doc"],
        documents=["Clinic-only secret policy"],
        embeddings=[[0.9, 0.1, 0.5]],
        metadatas=[{
            "doc_id": "clinic_only_doc",
            "type": "clinic_procedure",
            "name": "Secret Clinic Policy",
            "clinic_id": "99999999-9999-4999-a999-999999999999",
            "urgency": "routine",
            "source": "test",
            "version": "1.0",
            "last_updated": "2026-08-28",
            "specialty": "",
        }],
    )
    retriever = MedicalKnowledgeRetriever()
    docs, _ = retriever.retrieve("secret clinic policy", clinic_id="11111111-1111-4111-a111-111111111111")
    ids = {d.id for d in docs}
    assert "clinic_only_doc" not in ids


def test_normalize_query_collapses_whitespace():
    assert normalize_query("  Sore   Throat  ") == "sore throat"
