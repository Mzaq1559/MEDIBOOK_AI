# MediBook AI — Architecture Document

## System Overview

MediBook AI is a four-service, containerized clinic management platform. Each service is independently deployable and communicates over an internal Docker network (`medibook`).

```
┌─────────────────────────────────────────────────────────────┐
│                        Docker Network: medibook              │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Frontend   │    │   Backend    │    │  AI Service  │  │
│  │  React/Vite  │◄──►│   FastAPI    │◄──►│   FastAPI    │  │
│  │  Port: 3000  │    │  Port: 8000  │    │  Port: 8001  │  │
│  └──────────────┘    └──────┬───────┘    └──────┬───────┘  │
│                             │                   │           │
│                      ┌──────▼───────┐    ┌──────▼───────┐  │
│                      │  PostgreSQL  │    │   ChromaDB   │  │
│                      │  Port: 5432  │    │  (in-process)│  │
│                      └──────────────┘    └──────────────┘  │
│                                                             │
│  ┌──────────────┐                                           │
│  │     n8n      │  (Appointment reminder automation)        │
│  │  Port: 5678  │                                           │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Service Breakdown

### 1. Frontend (`/frontend`)
- **Stack**: React 18 + Vite + TypeScript + Tailwind CSS
- **Auth**: JWT tokens stored in `localStorage`; Axios interceptors refresh on 401
- **Routing**: React Router v6 with protected route guards
- **Key pages**: Login, Dashboard, Appointments, Doctors, Patients, Prescriptions, Analytics, Chat

### 2. Backend (`/backend`)
- **Stack**: FastAPI + SQLAlchemy 2.x (async) + Alembic + PostgreSQL 15
- **Auth**: JWT (HS256) with access + refresh token rotation
- **Migrations**: Alembic (`alembic upgrade head` runs at container start)
- **SMTP**: Email notifications via `aiosmtplib`
- **Scheduler**: APScheduler for periodic tasks (no-show sweeps, reminders)

**Core models**:
| Model | Purpose |
|---|---|
| `User` | Auth — doctors, receptionists, admins |
| `Patient` | Patient registry |
| `Doctor` | Doctor profiles + specializations |
| `DoctorSchedule` | Weekly availability slots |
| `Appointment` | Booking records with status FSM |
| `Prescription` | Doctor-issued prescriptions |
| `Clinic` / `ClinicHoliday` | Clinic config and holidays |
| `AuditLog` | Write-action audit trail |

### 3. AI Service (`/ai-service`)
- **Stack**: FastAPI + Groq SDK + ChromaDB + sentence-transformers
- **Agent**: Single Groq tool-calling LLM (`openai/gpt-oss-120b` or configurable)
- **RAG**: ChromaDB vector store, `all-MiniLM-L6-v2` embeddings, cosine similarity

**Conversation flow**:
```
Patient message
      │
      ▼
  chatbot.py (agent loop)
      │
      ├── Groq LLM (tool selection)
      │       │
      │       ├── search_doctors_tool
      │       ├── get_available_slots_tool
      │       ├── book_appointment_tool ──► propose → patient confirms → execute
      │       ├── cancel_appointment_tool
      │       ├── get_appointments_tool
      │       ├── symptom_triage_tool ─────► RAG retrieval
      │       └── ...
      │
      └── Final natural-language response
```

**Safety gate** — All write operations (`book`, `cancel`, `reschedule`) follow:
1. Agent proposes action with summary
2. Patient must reply with explicit confirmation keyword
3. Backend executes only after confirmation; otherwise discards

### 4. n8n (`medibook_n8n`)
- Workflow automation for appointment reminders
- Receives webhooks from AI service when appointments are booked
- Sends SMS/email reminders before appointment time

---

## RAG Pipeline

```
Knowledge Base (Markdown/text files)
        │
        ▼
  Document chunking (recursive character splitter)
        │
        ▼
  Sentence-transformers embeddings (all-MiniLM-L6-v2)
        │
        ▼
  ChromaDB collection (persisted at /app/data/chroma)
        │
        ▼
  Query-time: cosine similarity top-K retrieval
  (configurable: RAG_TOP_K, RAG_MIN_RELEVANCE_SCORE)
        │
        ▼
  Context injected into LLM system prompt
```

---

## Appointment Status State Machine

```
SCHEDULED ──► CONFIRMED ──► COMPLETED
     │              │
     ▼              ▼
CANCELLED       NO_SHOW
```

- Transitions validated server-side in `backend/app/services/`
- `NO_SHOW` can only be set after appointment datetime has passed

---

## Data Flow: Booking a Patient Appointment

```
1. Patient says "Book appointment with Dr. Ahmed tomorrow at 10am"
2. AI Service: Groq agent calls get_available_slots_tool(doctor_id, date)
3. AI Service: Backend API returns available slots
4. Agent proposes: "I'll book you with Dr. Ahmed on Sept 4 at 10:00 AM. Reply 'confirm' to proceed."
5. Patient replies: "confirm"
6. Agent calls book_appointment_tool → POST /api/appointments
7. Backend creates Appointment record, sends confirmation email
8. AI Service fires n8n webhook → reminder scheduled
9. Agent confirms to patient with booking details
```

---

## Security Architecture

| Layer | Implementation |
|---|---|
| Auth | JWT HS256, access token 60min, refresh 1day |
| Password | bcrypt hashing |
| CORS | Configurable `ALLOWED_ORIGINS` |
| Input validation | Pydantic v2 schemas on all endpoints |
| Audit trail | `AuditLog` table for all mutations |
| Env secrets | `.env` excluded from git; injected via Docker env |
| Confirmation gate | Write actions require explicit patient confirmation |

---

## Branch Architecture

| Branch | AI Architecture | RAG | Agent |
|---|---|---|---|
| `baseline` | Deterministic FSM | ❌ | ❌ |
| `rag` | Deterministic FSM | ✅ ChromaDB | ❌ |
| `main` | Groq tool-calling agent | ✅ ChromaDB | ✅ |

---

## Environment Variables Reference

See `.env.example` for all required variables. Key ones:

| Variable | Service | Description |
|---|---|---|
| `GROQ_API_KEY` | ai-service | Groq LLM API key |
| `DATABASE_URL` | backend, ai-service | PostgreSQL connection string |
| `SECRET_KEY` | backend | JWT signing secret (min 32 chars) |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | backend | Email notification credentials |
| `GOOGLE_CREDENTIALS_PATH` | backend | Google Calendar OAuth credentials |

---

## Deployment

### Production (Docker Compose)
```bash
docker-compose up --build -d
```

### Local Development
```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# AI Service
cd ai-service && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Frontend
cd frontend && npm install && npm run dev
```
