# RAG Setup Guide

## Environment variables

```env
RAG_ENABLED=true
RAG_VECTOR_DB_PATH=/app/data/chroma
RAG_COLLECTION_NAME=medical_knowledge
RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2
RAG_TOP_K=5
RAG_MIN_RELEVANCE_SCORE=0.35
RAG_CACHE_ENABLED=true
RAG_AUTO_LOAD_ON_STARTUP=true
```

## Docker Compose

The `ai-service` mounts a persistent volume at `/app/data/chroma`.

```bash
docker compose up -d --build ai-service
```

On startup, if the collection is empty, knowledge is auto-indexed from `ai-service/app/knowledge_base/`.

## Manual knowledge rebuild

```bash
docker compose exec ai-service python -m app.rag.knowledge_loader --rebuild
```

## Health check

```bash
curl http://localhost:8001/api/rag/health
```

## Testing

```bash
docker compose exec ai-service pytest -v
```

## Troubleshooting

| Issue | Action |
|-------|--------|
| `embedding_model: error` | Ensure container has enough memory; model downloads on first use |
| `document_count: 0` | Run knowledge loader manually |
| RAG always falls back | Check Groq API key and Chroma volume permissions |
| Slow first request | Expected — embedding model cold start |

## Disabling RAG

```env
RAG_ENABLED=false
```

Restart `ai-service`. Symptom triage reverts to deterministic rules in `symptom_triage.py`.
