"""Load JSON knowledge base into ChromaDB."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.rag.config import rag_settings
from app.rag.embeddings import embed_texts
from app.rag.models import KnowledgeDocument
from app.rag.vector_db import get_collection, reset_collection, upsert_documents

logger = logging.getLogger("medibook.ai.rag.knowledge_loader")

KNOWLEDGE_FILES = (
    "symptoms.json",
    "conditions.json",
    "specialties.json",
    "emergency_protocols.json",
    "clinic_procedures.json",
)


def load_json_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        logger.warning("Knowledge file missing: %s", path)
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    return data


def records_to_documents(records: list[dict[str, Any]]) -> list[KnowledgeDocument]:
    docs: list[KnowledgeDocument] = []
    for record in records:
        doc = KnowledgeDocument.model_validate(record)
        if not doc.content:
            doc.content = doc.searchable_text()
        docs.append(doc)
    return docs


def load_all_documents(knowledge_dir: Path | None = None) -> list[KnowledgeDocument]:
    base = knowledge_dir or rag_settings.knowledge_base_dir
    all_docs: list[KnowledgeDocument] = []
    for filename in KNOWLEDGE_FILES:
        records = load_json_records(base / filename)
        all_docs.extend(records_to_documents(records))
    return all_docs


def index_documents(documents: list[KnowledgeDocument], *, rebuild: bool = False) -> dict[str, Any]:
    if rebuild:
        reset_collection()

    if not documents:
        return {"indexed": 0, "total": get_collection().count()}

    ids = [doc.id for doc in documents]
    texts = [doc.searchable_text() for doc in documents]
    metadatas = [doc.to_metadata() for doc in documents]
    embeddings = embed_texts(texts)
    total = upsert_documents(ids, texts, embeddings, metadatas)
    return {"indexed": len(documents), "total": total}


def ensure_knowledge_indexed(*, rebuild: bool = False) -> dict[str, Any]:
    documents = load_all_documents()
    if not documents:
        logger.warning("No knowledge documents found to index")
        return {"indexed": 0, "total": 0}

    collection = get_collection()
    if not rebuild and collection.count() > 0:
        logger.info("Knowledge base already indexed (%s documents)", collection.count())
        return {"indexed": 0, "total": collection.count(), "skipped": True}

    stats = index_documents(documents, rebuild=rebuild)
    logger.info("Knowledge loader complete: %s", stats)
    return stats


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Load MediBook AI knowledge base into ChromaDB")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the vector collection")
    args = parser.parse_args()
    stats = ensure_knowledge_indexed(rebuild=args.rebuild)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
