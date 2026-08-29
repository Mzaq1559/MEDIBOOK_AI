# RAG Architecture

MediBook AI uses a retrieval-augmented generation (RAG) pipeline for **symptom triage only**. Booking, rescheduling, cancellation, lookup, and FAQ flows are unchanged.

## Flow

```text
User message
  → Existing chatbot state machine
  → Emergency detection (deterministic, first)
  → Intent classification
  → booking/reschedule/cancel/lookup → existing handlers
  → symptom triage (ASKING_SYMPTOMS) → RAG pipeline
       → retrieval (ChromaDB)
       → grounded Groq LLM (structured JSON)
       → safety validation + fallback
```

## Safety hierarchy

1. Deterministic emergency rules (`app/symptom_triage.py`)
2. Existing business logic and state machine
3. RAG medical grounding
4. LLM generation

RAG never overrides confirmed emergencies.

## Components

| Module | Responsibility |
|--------|----------------|
| `app/rag/config.py` | Environment configuration |
| `app/rag/vector_db.py` | Persistent ChromaDB client |
| `app/rag/embeddings.py` | `sentence-transformers` embeddings |
| `app/rag/retriever.py` | Top-K retrieval + metadata filters |
| `app/rag/augmentation.py` | Grounded prompt builder |
| `app/rag/generator.py` | Structured Groq JSON output |
| `app/rag/safety.py` | Emergency validation + fallback mapping |
| `app/rag/pipeline.py` | Orchestration + audit logging |
| `app/rag/knowledge_loader.py` | JSON → Chroma indexing |
| `app/knowledge_base/*.json` | Version-controlled medical knowledge |

## API

- `GET /api/rag/health` — RAG subsystem health and document count
- Chat responses may include `ui_data.triage` with `sources`, `rag_used`, `rag_status`

## Feature flag

Set `RAG_ENABLED=false` to restore deterministic triage behavior.

## Clinic-specific knowledge

Documents with `clinic_id=null` are global. Clinic-specific entries use a real clinic UUID and are only returned for matching clinic retrieval queries.

## Fallback

On embedding, retrieval, generation, or validation failure:

- Circuit breaker tracks repeated failures
- Deterministic `symptom_triage.triage()` is used
- Chatbot remains operational

## Observability

Structured counters in `app/rag/metrics.py` and audit logs from the pipeline.
