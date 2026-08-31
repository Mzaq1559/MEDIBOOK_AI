# MediBook AI Architecture Analysis (Agentic Implementation)

## 1. HIGH-LEVEL SYSTEM MAP

The system consists of several interoperating microservices coordinated via Docker Compose (`docker-compose.yml`):

*   **Frontend (React 18 / Vite)**: Exposed on **Port 3000**. Handles the Chat UI and Dashboard. Routes API requests via a Vite proxy: `/api` proxies to the backend, and `/chat` (or `VITE_CHAT_API_URL`) proxies to the AI service.
*   **Backend API (FastAPI / Uvicorn)**: Exposed on **Port 8000**. Acts as the authoritative data layer, communicating with PostgreSQL.
*   **AI Service (FastAPI / Uvicorn)**: Exposed on **Port 8001**. Hosts the conversational agent and tool-execution engine.
*   **Database (PostgreSQL 15)**: Exposed on **Port 5433** (host) / `5432` (internal). Stores all authoritative operational data.
*   **ChromaDB**: Volume-mapped into the AI service container (`/app/data/chroma`) for RAG vector storage.
*   **n8n**: Exposed on **Port 5678**. Used for automated webhooks (e.g., appointment reminders).

**End-to-End Request Trace (Chat)**
1.  **Patient Message**: User types "I want to see a cardiologist tomorrow" in the frontend (`Chat.tsx`).
2.  **Proxy Routing**: Frontend sends a POST request to `/chat/message` (proxied to AI Service Port 8001).
3.  **Emergency Guard**: Request hits `ai-service/app/main.py` -> `send_chat_message()` -> `handle_message()` in `chatbot.py`. It immediately evaluates `is_emergency()` via `symptom_triage.py`.
4.  **Agent Loop**: If no emergency, it enters `run_agent_loop()`. The message is appended to the in-memory session and sent to the **Groq API** (`groq_client.py`) along with system prompts and available tool schemas.
5.  **Tool Call**: The LLM returns a tool call for `get_availability` or `book_appointment`.
6.  **Backend Request**: `tools.py` intercepts the call, executing the logic using `backend_client.py` (which makes synchronous HTTP requests using `httpx` to the Backend API at Port 8000).
7.  **Database Action**: The Backend (`routes/appointments.py`) validates the request against PostgreSQL models and commits the changes.
8.  **Response back to UI**: The tool result is passed back to Groq for a final conversational wrapper. The AI service responds to the frontend with the text and structured `ui_data`, which `Chat.tsx` renders into rich cards.

---

## 2. AGENT ORCHESTRATION

The orchestration layer entirely replaces a traditional conversational state machine with a dynamic LLM loop.

*   **`chatbot.py` (`run_agent_loop`)**: Implements the core ReAct-style loop. It maintains a session (`_sessions` dict) and can run up to 8 iterations (`MAX_TOOL_ROUNDS`). If Groq returns `tool_calls`, `chatbot.py` extracts them, calls `execute_tool()` from `tools.py`, appends the result to the context, and re-prompts the LLM. It stops when the LLM returns plain conversational text instead of a tool call.
*   **`tools.py`**: The definitive registry for agent capabilities. It maintains `TOOL_DEFINITIONS` (Groq JSON schemas) and maps them to Python handlers (e.g., `tool_book_appointment`). It extracts LLM-provided arguments, performs basic sanity checks (e.g., ensuring `patient_id` matches the session), and executes the action.
*   **`groq_client.py`**: A lightweight wrapper around the Groq SDK, providing retry mechanisms, JSON-mode enforcers, and a fallback response (`LLM_FALLBACK`) if the API errors out.
*   **`backend_client.py`**: An `httpx` HTTP client that bridges the AI service and the Backend API. It forwards the patient's JWT (`authorization` header) to ensure the backend respects the identity of the user talking to the agent.
*   **`chatbot_nlu.py`**: Provides fast-path, regex-based heuristic checks (e.g., `is_confirm`, `extract_appointment_id`). Though its role is diminished in the agentic setup, it acts as a lightweight utility for identifying intent overrides or IDs.

**Available Tools (Actual Code Implementation)**
*   **Read-Only**:
    *   `get_patient_appointments(patient_id)`: Fetches upcoming appointments via backend.
    *   `get_doctors_by_specialty(specialty)`: Lists doctors matching a given medical field.
    *   `get_availability(doctor_id, date)`: Returns open time slots for a doctor on a given day.
    *   `get_patient_info(patient_id)`: Fetches the authenticated user's profile and allergies.
*   **Write**:
    *   `book_appointment(patient_id, doctor_id, datetime, symptoms)`: Creates an appointment.
    *   `reschedule_appointment(appointment_id, new_datetime)`: Updates appointment time.
    *   `cancel_appointment(appointment_id)`: Deletes/cancels an appointment.

---

## 3. THE PROPOSE → VALIDATE → CONFIRM → EXECUTE WRITE GATE (CRITICAL FINDING)

**The README claims there is a rigid two-step transactional gate** (e.g., `propose_book_appointment` and `execute_confirmed_action`). 

**Actual Code Implementation**: **This mechanism does not exist.** 
*   **No Code-Level Guardrail**: Looking at `tools.py`, the tools exposed to the LLM are directly the write actions: `book_appointment`, `reschedule_appointment`, and `cancel_appointment`. 
*   **Prompt-Engineered Guardrail**: The only thing preventing the LLM from writing directly to the database without user confirmation is a line in `build_system_prompt()`: 
    > *"- For booking, reschedule, and cancel: confirm in one short sentence, then wait for a clear yes before calling the write tool."*
*   **Database Writes**: When the LLM decides the user has confirmed (or hallucinates that they did), it calls `book_appointment`. `tools.py` immediately forwards this to `backend_client.create_appointment`, which hits `POST /api/appointments` and commits the write to PostgreSQL. 

Direct LLM-to-database writes are **not** prevented at the code level. The LLM has direct, un-gated access to the mutation endpoints.

---

## 4. EMERGENCY DETECTION

Emergency detection is **truly synchronous and pre-agent**.
*   In `chatbot.py -> handle_message()`, immediately after creating the session, the code checks `is_emergency(message)`.
*   The `is_emergency()` logic lives in `symptom_triage.py`. It uses robust regex patterns (matching English and Roman Urdu) for critical keywords like "chest pain", "can't breathe", or "suicide".
*   If `is_emergency(message)` returns `True`, the function immediately bypasses the `run_agent_loop`, appending a hardcoded `EMERGENCY_ALERT` to the chat history and returning `next_action = "emergency_redirect"`. 
*   **Call Order**: The agent and Groq API are completely circumvented. The LLM cannot hallucinate away a genuine emergency keyword match.

---

## 5. MEDICAL RAG PIPELINE (CRITICAL FINDING)

**The README claims Medical RAG is integrated as an agent tool** (`retrieve_medical_knowledge`).

**Actual Code Implementation**: **The RAG pipeline is entirely orphaned and disconnected in the `agentic` branch.**
*   The pipeline logic exists in `ai-service/app/rag/`: `pipeline.py` defines a robust orchestration class (`RAGPipeline`) that connects `retriever.py` (which embeds queries using `embeddings.py` and searches ChromaDB in `vector_db.py`) to the LLM via `generator.py`.
*   However, `RAGPipeline` and its entry point `triage_symptoms()` are **never called** by `chatbot.py` or `main.py`. 
*   In `tools.py`, the `retrieve_medical_knowledge` tool is **missing from `TOOL_DEFINITIONS`**.
*   The agent has absolutely no way to access the RAG database, and the `/chat/message` endpoint never manually injects it. The RAG architecture exists but is functionally dead code in this branch.

---

## 6. BACKEND & DATA LAYER

**Models & Schema** (`backend/app/models/`)
*   **`User`**: Base authentication table with `user_type` (patient, doctor, admin, receptionist).
*   **`Patient` / `Doctor`**: Profile extensions storing specialties, bios, dob, and medical conditions. They have a 1:1 relationship with `User` via `user_id` (UUID).
*   **`Appointment`**: The core transactional table. Uses UUIDs for primary keys. Contains foreign keys to `clinic_id`, `doctor_id`, and `patient_id`. It includes fields for `appointment_time`, `status`, `symptoms_reported`, and `urgency_level`. 

**Server-Side Authorization**
The backend prevents ID spoofing by enforcing ownership server-side.
*   In `routes/appointments.py`, functions like `bulk_cancel_appointments` or `cancel_appointment` rely on FastAPI's `Depends(get_current_user)`.
*   The system cross-references the authenticated JWT user against the requested appointment. If a patient user tries to cancel an appointment where `Appointment.patient_id != patient.id`, it throws a `403 FORBIDDEN`. 
*   Similarly, `tools.py` in the AI Service uses `_session_patient_id` to override any `patient_id` the LLM attempts to provide, mapping it strictly to the authenticated `patient_id` from the active session.

---

## 7. FRONTEND INTEGRATION

*   **Communication**: The React frontend (`Chat.tsx`) communicates with the `ai-service` via a `sendChatMessage` HTTP fetch to `/chat`. 
*   **UI Rendering**: The chat UI doesn't rely entirely on the LLM's text. The `ai-service` returns a structured `ui_data` payload alongside the bot's text. 
*   **Confirmations UX**: Because there is no actual "proposal lock" in the backend, the UX handles confirmations purely contextually. If the `ui_data.booking` is present but `isConfirmed` is false, it renders a `ConfirmationCard`. If the user clicks "Confirm", the frontend literally just sends the text string `"yes, confirm"` back to the chat API. The LLM reads this text in the conversation history and autonomously decides to execute the `book_appointment` tool.

---

## 8. GAPS, INCONSISTENCIES, OR RISKS

1.  **The "Guardrail" Illusion**: The most critical risk is the complete absence of the `propose -> confirm -> execute` backend gate described in the README. The LLM has direct write access to PostgreSQL via the `book_appointment`, `reschedule_appointment`, and `cancel_appointment` tools. The safety relies 100% on a prompt instruction asking the LLM to wait for confirmation. A determined jailbreak (or a simple hallucination) will result in unauthorized database modifications.
2.  **Disconnected RAG**: The "RAG Clinical Triage" feature highlighted in the UI and README is non-functional. The tool definition for `retrieve_medical_knowledge` was seemingly dropped during the transition from the legacy state-machine to the agentic architecture. The ChromaDB vector store is active but un-queried.
3.  **Ephemeral In-Memory Sessions**: The README claims "session persistence is in-memory". This is accurate (via the `_sessions` dictionary in `chatbot.py`). However, this means if the `ai-service` Docker container crashes, restarts, or scales horizontally, all active conversation histories, pending selections, and loaded contexts are instantly destroyed.
4.  **UI State Desync**: The `Chat.tsx` frontend strips tool cards (like `DoctorCard` or `AppointmentCard`) if the LLM decides to list the details in plain text (`lists_appointment_details`). However, because the agent acts asynchronously and determines its own text, the UI can easily become desynchronized, showing "waiting for confirmation" cards when the backend action has either already failed or the LLM forgot to make the tool call entirely. 
5.  **Patient ID Resolution**: In the AI service (`chatbot.py`), the `patient_id` is passed from the frontend to initialize the session. While the backend verifies ownership via JWT, if the frontend were to omit the JWT but provide a spoofed `patient_id` payload to `/chat/message`, the `_require_auth` helper in `tools.py` checks for the *presence* of a Bearer token, but the AI service doesn't cryptographically validate the JWT itself (it just forwards it). If an endpoint lacked authorization checks on the backend, this could be a spoofing vector.
