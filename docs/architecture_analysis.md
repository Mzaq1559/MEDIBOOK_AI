# MediBook AI — Architecture Analysis (Agentic Implementation)

## 1. High-Level System Map

The system consists of containerized microservices coordinated via Docker Compose (`docker-compose.yml`) communicating over an internal bridge network (`medibook`):

*   **Frontend (React 18 / Vite / TypeScript)**: Exposed on **Port 3000**. Handles patient and clinic staff portals (Chat, Dashboard, Appointments, Doctors, Patients, Prescriptions, Analytics). Directs traffic via a built-in Vite development proxy:
    *   `/api/*` proxies to the Backend API at `http://backend:8000/api/*`
    *   `/chat/*` proxies to the AI Service at `http://ai-service:8001/api/chat/*`
*   **Backend API (FastAPI / Uvicorn)**: Exposed on **Port 8000**. The authoritative transactional layer interfacing with PostgreSQL. Enforces JWT authentication, role-based access control, appointment availability algorithms, and audit logging.
*   **AI Service (FastAPI / Uvicorn)**: Exposed on **Port 8001**. Hosts the conversational agent loop, tool execution engine, RAG pipeline, and in-memory proposal write gate.
*   **Database (PostgreSQL 15)**: Exposed on **Port 5433** (host) / `5432` (internal). The sole authoritative source of truth for users, clinics, doctors, patients, appointments, schedules, holidays, prescriptions, and audit logs.
*   **ChromaDB**: In-process vector store inside the AI service container persisted at `/app/data/chroma`. Houses vector embeddings strictly for medical knowledge triage.
*   **n8n Automation Engine**: Exposed on **Port 5678**. Receives webhooks from the AI service on appointment creation/rescheduling to trigger reminders.

### End-to-End Request Trace (Chat Interaction)

1.  **Patient Message**: User submits a message via `frontend/src/pages/Chat.tsx`.
2.  **Proxy Forwarding**: Frontend issues `POST /chat/message`, rewritten by Vite proxy to `http://ai-service:8001/api/chat/message`.
3.  **Deterministic Emergency Guard**: Before touching the LLM, `ai-service/app/chatbot.py` calls `symptom_triage.is_emergency(message)`. If matched, the turn halts immediately and emits `EMERGENCY_ALERT` (`next_action = "emergency_redirect"`).
4.  **Agent Loop Initiation**: If clear, `chatbot.py` appends the message to the session history and enters `run_agent_loop_stream` / `run_agent_loop`.
5.  **Groq LLM Reasoning**: The conversation history, system prompt, and `TOOL_DEFINITIONS` schemas are dispatched to Groq API (`app/groq_client.py`).
6.  **Tool Selection**: The LLM autonomously chooses which tool to invoke (e.g. `retrieve_medical_knowledge`, `get_availability`, `propose_book_appointment`).
7.  **Tool Execution**: `app/tools.py` intercepts the call, validates arguments, checks session bounds, and dispatches to either the local RAG pipeline (`app/rag/pipeline.py`) or the Backend API (`app/backend_client.py`).
8.  **Tool Context Feed**: Tool outputs are appended back into the message array with `role: "tool"`, allowing the LLM to synthesize final conversational text.
9.  **Streaming Response**: Results are returned to the client either as standard JSON or as Server-Sent Events (`SSE`) with intermediate status updates (`event: status`) and final payloads (`event: final`).

---

## 2. Agent Orchestration

The conversational layer completely replaces rigid legacy state machines with an autonomous Groq tool-calling agent.

*   **`chatbot.py` (`run_agent_loop` / `run_agent_loop_stream`)**:
    *   ReAct-style execution loop supporting up to 8 tool turns per request (`MAX_TOOL_ROUNDS = 8`).
    *   Maintains conversation session state in an in-memory dictionary (`_sessions`) with a 2-hour TTL (`SESSION_TTL = 7200`).
    *   Emits intermediate SSE status events (e.g., *"Looking up available doctors..."*, *"Checking availability..."*) so the UI shows live progress.
    *   Cleans and strips unnecessary card metadata if the LLM already articulated details conversationally (`_strip_listed_appointment_cards`).
*   **`tools.py`**:
    *   Defines `TOOL_DEFINITIONS` conforming to the OpenAI/Groq function calling schema.
    *   Dispatches tool execution through `execute_tool()` and handler mappings.
    *   Injects authenticated session bounds (`patient_id` from JWT session) to prevent parameter spoofing.
*   **`groq_client.py`**:
    *   Low-level HTTP client wrapping Groq's completions API.
    *   Supports configured model (default: `openai/gpt-oss-120b` or configurable via `GROQ_MODEL`).
    *   Implements graceful fallback handling (`LLM_FALLBACK`) upon upstream API failures.
*   **`backend_client.py`**:
    *   High-performance `httpx.Client` communicating with the FastAPI backend at `http://backend:8000/api`.
    *   Passes through the patient's Bearer token in the `Authorization` header to maintain server-side authorization context.

### Complete Tool Inventory

#### Read-Only Tools
- **`get_patient_appointments(patient_id)`**: Fetches upcoming appointments for the authenticated patient.
- **`search_patient_appointments(doctor_name, status, date_from, date_to)`**: Filtered search over appointments scoped strictly to the current patient.
- **`get_doctors_by_specialty(specialty)`**: Discovers active doctors matching a specialization.
- **`get_availability(doctor_id, date)`**: Queries open 30-minute consultation slots for a doctor across upcoming dates.
- **`get_patient_info(patient_id)`**: Retrieves patient profile, emergency contacts, and recorded allergies.
- **`retrieve_medical_knowledge(symptoms)`**: Evaluates symptoms against the RAG clinical triage knowledge base.

#### Write Tools
- **`propose_book_appointment(patient_id, doctor_id, datetime, symptoms)`**: Creates a pending booking proposal.
- **`propose_reschedule_appointment(appointment_id, new_datetime)`**: Creates a pending reschedule proposal.
- **`propose_cancel_appointment(appointment_id)`**: Creates a pending cancellation proposal.
- **`execute_confirmed_action(proposal_id)`**: Commits the verified proposal to the backend database.

---

## 3. The Propose → Validate → Confirm → Execute Write Gate

To prevent autonomous LLMs from executing unauthorized or hallucinated mutations, MediBook AI enforces a strict multi-stage write gate:

```
[Patient Request]
       │
       ▼
[Agent calls propose_book_appointment / propose_reschedule / propose_cancel]
       │
       ├── 1. Validate doctor, date, and availability against Backend API
       ├── 2. Validate patient ownership (appointment belongs to authenticated patient)
       ├── 3. Generate unique UUID proposal_id
       └── 4. Cache in _PROPOSALS dictionary (5-minute TTL, session-bound, patient-bound)
       │
       ▼
[Agent presents summary & asks patient for explicit confirmation]
       │
       ▼
[Patient replies: "Yes, please confirm"]
       │
       ▼
[Agent calls execute_confirmed_action(proposal_id)]
       │
       ├── 1. Validate proposal exists, is not expired, and has not been executed (used=False)
       ├── 2. Validate proposal patient_id matches active session patient_id
       ├── 3. Validate proposal session_id matches active conversation_id
       ├── 4. Mark proposal used = True
       ├── 5. Commit mutation via Backend API (POST /api/appointments)
       └── 6. Dispatch Google Calendar event & n8n reminder webhooks
       │
       ▼
[Appointment Committed to PostgreSQL]
```

### Key Architectural Guarantees
- **No Direct LLM Writes**: The LLM has zero tools that write directly to PostgreSQL. The only mutation tool is `execute_confirmed_action`.
- **TTL Expiration**: Unconfirmed proposals expire automatically after 300 seconds (5 minutes).
- **Anti-Tampering**: Even if an LLM is prompted to execute an arbitrary proposal ID, the handler verifies that `proposal.patient_id == session.patient_id` and `proposal.session_id == session.conversation_id`.

---

## 4. Deterministic Emergency Guard

Patient safety is guaranteed through a deterministic, pre-agent emergency detection layer:

*   **Execution Timing**: Runs inside `chatbot.py -> handle_message()` as step 1, completely bypassing the Groq LLM agent.
*   **Mechanism**: Implemented in `app/symptom_triage.py -> is_emergency(message)` using comprehensive regex patterns covering English and Roman Urdu (e.g. *"chest pain"*, *"can't breathe"*, *"chhati me dard"*, *"saans nahi aa rahi"*).
*   **Response**: Immediately returns `EMERGENCY_ALERT` and sets `next_action = "emergency_redirect"`. The LLM cannot hallucinate away red-flag clinical emergencies.

---

## 5. Medical RAG Integration

Medical knowledge retrieval is fully operational and embedded directly as an agent tool:

*   **Integration**: `retrieve_medical_knowledge` is registered in `TOOL_DEFINITIONS` and wired to `tool_retrieve_medical_knowledge` in `tools.py`.
*   **Pipeline Flow**:
    1. Symptoms are passed to `pipeline.triage_symptoms()`.
    2. `embeddings.embed_query()` computes a 384-dimensional dense embedding using `sentence-transformers/all-MiniLM-L6-v2`.
    3. `vector_db.query_vectors()` retrieves top-K chunks from ChromaDB (relevance score $\ge 0.35$).
    4. `augmentation.build_augmented_prompt()` formats the retrieved passages into clinical grounding context.
    5. `generator.generate()` invokes Groq in JSON mode to return a structured `TriageResult` (specialty, urgency, bot_message).
    6. `safety.validate_triage_result()` enforces safety rules and disclaimers.
*   **Circuit Breaker & Fallback**: If ChromaDB or Groq fails, `app/rag/circuit_breaker.py` trips after 5 consecutive failures and falls back immediately to deterministic triage rules, keeping the chatbot online.

---

## 6. Backend & Security Architecture

*   **Data Separation**:
    *   **PostgreSQL 15** is the sole transactional truth (users, clinics, doctors, patients, appointments, doctor schedules, clinic holidays, prescriptions, audit logs).
    *   **ChromaDB** stores only medical knowledge vectors. It contains zero patient PII or booking records.
*   **Authentication & Authorization**:
    *   JWT HS256 tokens (60-minute access, 1-day refresh).
    *   All appointment queries and cancellations verify ownership server-side (`Appointment.patient_id == current_user.patient.id`).
    *   The AI service automatically binds the session `patient_id` to the validated JWT token, preventing patient impersonation.

---

## 7. Known Architectural Limitations & Trade-Offs

To maintain architectural transparency, the following design trade-offs and current limitations are acknowledged:

1.  **In-Memory Session & Proposal Storage**:
    *   Active conversation sessions (`_sessions`) and pending proposals (`_PROPOSALS`) are held in memory within the `ai-service` process.
    *   If the container restarts, pending unconfirmed proposals and active conversation contexts are reset. Horizontal scaling requires sticky sessions or external state caching (e.g., Redis).
2.  **Medical Scope Boundaries**:
    *   The RAG knowledge base covers primary outpatient symptoms, conditions, medical specialties, and clinic policies.
    *   The system is explicitly designed for **administrative triage and scheduling**, not clinical diagnosis.
3.  **Language Support**:
    *   Primary communication is English, with regex emergency detection supporting Roman Urdu. Full bilingual English/Urdu conversational generation and vector retrieval is targeted for future iterations.
4.  **Client Platforms**:
    *   The client layer is currently a responsive web application (React 18 + Vite); dedicated native iOS/Android applications are not yet implemented.
