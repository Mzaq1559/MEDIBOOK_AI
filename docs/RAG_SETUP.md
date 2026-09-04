# MediBook AI — RAG Setup & Operations Guide

This guide covers configuration, index management, operations, and troubleshooting for the Medical RAG subsystem in the `ai-service` container.

---

## 1. Environment Configuration

The RAG subsystem is configured via environment variables set in `docker-compose.yml` or your `.env` file:

```env
# ── RAG Subsystem Settings ──
RAG_ENABLED=true
RAG_VECTOR_DB_PATH=/app/data/chroma
RAG_COLLECTION_NAME=medical_knowledge
RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2
RAG_TOP_K=5
RAG_MIN_RELEVANCE_SCORE=0.35
RAG_CACHE_ENABLED=true
RAG_CACHE_TTL_SECONDS=3600
RAG_CIRCUIT_BREAKER_THRESHOLD=5
RAG_CIRCUIT_BREAKER_COOLDOWN_SECONDS=60
RAG_AUTO_LOAD_ON_STARTUP=true
```

| Variable | Default | Purpose |
|---|---|---|
| `RAG_ENABLED` | `true` | Master switch. When `false`, symptom triage falls back immediately to deterministic rules. |
| `RAG_VECTOR_DB_PATH` | `/app/data/chroma` | Persistent directory path for ChromaDB files. |
| `RAG_COLLECTION_NAME` | `medical_knowledge` | ChromaDB collection name for medical documents. |
| `RAG_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformer embedding model (384 dimensions). |
| `RAG_TOP_K` | `5` | Maximum number of relevant chunks to retrieve per query. |
| `RAG_MIN_RELEVANCE_SCORE` | `0.35` | Minimum cosine similarity threshold; lower-scoring chunks are filtered out. |
| `RAG_CACHE_ENABLED` | `true` | Enables query-level caching for frequent symptom queries. |
| `RAG_CACHE_TTL_SECONDS` | `3600` | In-memory cache time-to-live in seconds (1 hour). |
| `RAG_CIRCUIT_BREAKER_THRESHOLD` | `5` | Number of consecutive failures before the circuit opens. |
| `RAG_CIRCUIT_BREAKER_COOLDOWN_SECONDS` | `60` | Cooldown period before testing half-open recovery. |
| `RAG_AUTO_LOAD_ON_STARTUP` | `true` | Automatically index JSON knowledge base on startup if collection is empty. |

---

## 2. Docker Volume & Persistence

ChromaDB data is persisted on host storage through a named Docker volume (`chroma_data`) defined in `docker-compose.yml`:

```yaml
services:
  ai-service:
    volumes:
      - chroma_data:/app/data/chroma

volumes:
  chroma_data:
```

This guarantees that vector embeddings survive container restarts and deployments without needing to be recomputed.

---

## 3. Knowledge Base Ingestion

The raw medical guidelines are stored as version-controlled JSON files in `ai-service/app/knowledge_base/`:
- `symptoms.json`: Detailed symptom definitions, severity indicators, and triage guidelines.
- `conditions.json`: Clinical conditions, common presentations, and associated specialties.
- `specialties.json`: Medical specialties, treatment scopes, and typical consult reasons.
- `emergency_protocols.json`: Critical warning signs requiring immediate emergency room transfer.
- `clinic_procedures.json`: Clinic policies, appointment guidelines, and prep procedures.

### Automatic Startup Indexing
When `RAG_AUTO_LOAD_ON_STARTUP=true`, the `ai-service` startup event (`app/main.py`) checks if the collection contains documents. If empty, it indexes all JSON knowledge files automatically.

### Manual Re-indexing
To force a clean rebuild of the ChromaDB collection from disk:

**Inside Docker:**
```bash
docker compose exec ai-service python -m app.rag.knowledge_loader --rebuild
```

**Local Development:**
```bash
cd ai-service
python -m app.rag.knowledge_loader --rebuild
```

---

## 4. Verification & Health Monitoring

### Health Check Endpoint
Query the RAG subsystem health endpoint directly on Port 8001:

```bash
curl -s http://localhost:8001/api/rag/health | jq
```

**Example 200 OK Response:**
```json
{
  "enabled": true,
  "vector_db": "healthy",
  "embedding_model": "loaded",
  "collection": "medical_knowledge",
  "document_count": 86,
  "metrics": {
    "rag_queries_total": 42,
    "rag_retrieval_success_total": 41,
    "rag_cache_hits_total": 12,
    "rag_fallback_total": 0,
    "agent_tool_calls_total": 118,
    "circuit_breaker_state": "CLOSED"
  }
}
```

---

## 5. Agent Tool Invocation

RAG is consumed by the Groq tool-calling agent via the `retrieve_medical_knowledge` tool:
1. When a patient says: *"I have a sore throat and fever for 3 days"*, the Groq agent emits a function call:
   ```json
   {
     "name": "retrieve_medical_knowledge",
     "arguments": "{\"symptoms\": \"sore throat and fever for 3 days\"}"
   }
   ```
2. The tool execution engine (`tools.py`) forwards the arguments to `pipeline.triage_symptoms()`.
3. The RAG pipeline returns structured clinical guidance (recommended specialty: ENT or General Physician, normal urgency) to the agent context.
4. The agent wraps the clinical recommendation into a short, empathetic response for the patient.

---

## 6. Automated Testing

Run the automated test suite covering RAG embeddings, vector retrieval, circuit breaker, safety filters, and agent tool execution:

```bash
docker compose exec ai-service pytest -v
```

---

## 7. Troubleshooting

| Symptom | Probable Cause | Corrective Action |
|---|---|---|
| `embedding_model: error` | Insufficient RAM or network issue downloading model weights on first start. | Ensure container has at least 2 GB RAM. The `all-MiniLM-L6-v2` weights download automatically on first initialization. |
| `document_count: 0` | Knowledge files were not indexed on startup. | Run `docker compose exec ai-service python -m app.rag.knowledge_loader --rebuild`. |
| `circuit_breaker_state: OPEN` | Repeated ChromaDB or Groq timeouts exceeded the threshold. | Check `docker compose logs ai-service` for underlying timeout errors; verify Groq API key and rate limits. The breaker auto-recovers after 60s cooldown. |
| Agent returns fallback message | LLM or backend network timeout. | Verify `GROQ_API_KEY` is set and valid in `.env`. Check backend connectivity at `http://backend:8000/health`. |
| Slow initial response (3–5s) | SentenceTransformer cold start. | Expected behavior during the very first turn as PyTorch and embedding weights load into memory; subsequent queries run in milliseconds. |
