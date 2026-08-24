# MediBook AI

**AI-powered virtual receptionist for small and medium clinics in Pakistan — book appointments, triage symptoms, and manage clinic operations through natural conversation.**

[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Groq](https://img.shields.io/badge/LLM-Groq-f55036)](https://groq.com/)

---

## Table of Contents

1. [Hackathon Context](#hackathon-context)
2. [Problem Statement](#problem-statement)
3. [Solution Overview](#solution-overview)
4. [Architecture Diagram](#architecture-diagram)
5. [Tech Stack](#tech-stack)
6. [Key Features](#key-features)
7. [Getting Started / Local Setup](#getting-started--local-setup)
8. [API Documentation](#api-documentation)
9. [Database Schema](#database-schema)
10. [AI Chatbot Capabilities](#ai-chatbot-capabilities)
11. [Project Structure](#project-structure)
12. [Testing](#testing)
13. [Known Limitations / Future Work](#known-limitations--future-work)
14. [Team](#team)
15. [License](#license)

---

## Hackathon Context

**Event:** [Alibaba Cloud AI Hackathon Pakistan 2026](https://github.com/Mzaq1559/MEDIBOOK_AI)  
**Theme:** *AI for Pakistan's Future*  
**Build window:** August 22–27, 2026 (6 days) · Taxila, Pakistan  
**Team size:** 4 members

| Role | Contributor | GitHub |
|------|-------------|--------|
| Project Lead | Muhammad Zulqarnain Abdullah | [@Mzaq1559](https://github.com/Mzaq1559) |
| Backend | Sidra Pervaiz | [@SidraPervaiz1122](https://github.com/SidraPervaiz1122) |
| Frontend | Aleeza Imran | [@BSCS2455](https://github.com/BSCS2455) |
| AI Service | Ayesha Sajjad | [@AyeshaSajjad0786](https://github.com/AyeshaSajjad0786) |

---

## Problem Statement

Pakistan's small and medium-sized clinics face recurring operational pain points (from our project specification in `docs/MEDIBOOK_AI_COMPLETE_SPECIFICATIONS.txt`):

- **Manual appointment management** — bookings handled over phone, WhatsApp, or paper with no central system
- **Double bookings and missed appointments** — no real-time availability checks across doctors and time slots
- **Receptionist overload** — staff answer the same questions about hours, fees, and availability repeatedly
- **No availability tracking** — patients arrive without knowing wait times or open slots
- **No after-hours support** — patients cannot get help when the clinic is closed
- **High no-show rates** — without automated reminders, scheduled slots go unused

These constraints hit clinics hardest where a single receptionist juggles walk-ins, phone calls, and record-keeping simultaneously.

---

## Solution Overview

MediBook AI is a **24/7 AI virtual receptionist** backed by a full clinic management API. Patients describe symptoms in plain language; the system triages urgency, recommends a specialist, checks live doctor availability, and books appointments with conflict validation.

### What is fully implemented

| Area | Status |
|------|--------|
| **AI chat booking flow** (symptoms → triage → doctor/slot selection → confirmation) | ✅ Working via `ai-service` + Groq NLU |
| **Symptom triage & emergency detection** | ✅ Rule-based routing + ER redirect for critical symptoms |
| **Backend API** (auth, doctors, clinics, patients, appointments, analytics) | ✅ Production-ready FastAPI with JWT, rate limiting, audit logs |
| **Real-time availability engine** | ✅ Schedules, breaks, holidays, capacity, double-booking prevention |
| **Appointment lifecycle** | ✅ Create, list, reschedule, cancel, complete, no-show, feedback (API) |
| **Analytics API** | ✅ Dashboard metrics and daily summary for doctors/admins/receptionists |
| **Database seeding** | ✅ Demo seed + bulk test-data generator |
| **Docker Compose deployment** | ✅ Frontend, backend, AI service, PostgreSQL |
| **Frontend auth + chat** | ✅ Login/register and AI chat wired to live APIs |

### What is partially implemented or UI-only

| Area | Status |
|------|--------|
| **Patient / Doctor / Admin dashboards** | ✅ Fully wired to backend APIs; real data loading verified |
| **WhatsApp / SMS reminders** | ⚠️ Reminder timestamps computed and returned on booking; **no outbound messages sent** |
| **Google Calendar sync** | ⚠️ DB column + env vars exist; **no Calendar API integration** |
| **n8n workflow automation** | ❌ Not in codebase |
| **Prescriptions** | ⚠️ Database model exists; **no REST endpoints** |
| **Backend stub chat** | ❌ Not used; frontend correctly routes to AI microservice for real Groq LLM |

---

## Architecture Diagram

### System architecture

```mermaid
flowchart TB
    subgraph Client
        FE["Frontend<br/>React 18 + Vite + TypeScript<br/>Port 3000"]
    end

    subgraph Proxy["Reverse Proxy (Vite dev server)"]
        P1["/api → Backend"]
        P2["/chat → AI Service"]
    end

    subgraph Services
        BE["Backend API<br/>FastAPI + Uvicorn<br/>Port 8000"]
        AI["AI Service<br/>FastAPI + Uvicorn<br/>Port 8001"]
    end

    subgraph Data
        PG[("PostgreSQL 15<br/>Port 5432")]
    end

    subgraph External
        GROQ["Groq LLM API<br/>(NLU / intent detection)"]
    end

    subgraph Orchestration
        DC["Docker Compose"]
    end

    FE --> Proxy
    P1 --> BE
    P2 --> AI
    BE --> PG
    AI --> BE
    AI --> GROQ
    DC -.-> FE
    DC -.-> BE
    DC -.-> AI
    DC -.-> PG
```

The Vite dev server proxies `/api` to the backend and rewrites `/chat` → `/api/chat` on the AI service, so a single frontend port works locally and through dev tunnels.

### Patient books appointment via AI chat

```mermaid
sequenceDiagram
    actor Patient
    participant FE as Frontend (React)
    participant AI as AI Service (8001)
    participant GROQ as Groq LLM
    participant BE as Backend API (8000)
    participant DB as PostgreSQL

    Patient->>FE: Describe symptoms / book appointment
    FE->>AI: POST /api/chat/message<br/>{message, conversation_id, patient_id}
    AI->>GROQ: NLU — classify intent & extract entities
    GROQ-->>AI: {intent, symptoms, confirms, ...}
    alt Emergency symptoms detected
        AI-->>FE: Emergency alert (1100 / 15 / ER)
    else Booking flow
        AI->>AI: Rule-based symptom triage → specialty
        AI->>BE: GET /api/doctors?specialization=...
        BE->>DB: Query available doctors
        DB-->>BE: Doctor list
        BE-->>AI: Doctors JSON
        AI->>BE: GET /api/doctors/{id}/availability
        BE->>DB: Compute slots (schedules, holidays, bookings)
        DB-->>BE: Available time slots
        BE-->>AI: Availability JSON
        AI-->>FE: Recommended doctors + open slots
        Patient->>FE: Select doctor & time, confirm
        FE->>AI: POST /api/chat/message (confirm)
        AI->>BE: POST /api/appointments (JWT forwarded)
        BE->>DB: Validate & insert appointment
        DB-->>BE: Appointment record
        BE-->>AI: Confirmation + reminder timestamps
        AI-->>FE: Booking confirmed
    end
```

---

## Tech Stack

| Layer | Technologies | Version (where pinned) |
|-------|-------------|------------------------|
| **Frontend** | React, TypeScript, Vite, Tailwind CSS, React Router, Axios, date-fns, react-icons | React ^18.2, Vite ^5.0, Node 18 (Docker) |
| **Backend** | FastAPI, Uvicorn, SQLAlchemy, Alembic, Pydantic v2, PyJWT, passlib/bcrypt, SlowAPI | Python 3.12 (Docker), FastAPI ≥0.110 |
| **AI Service** | FastAPI, Groq SDK, httpx, rule-based triage | Python 3.10 (Docker), Groq SDK ≥0.13 |
| **Database** | PostgreSQL | 15-alpine |
| **DevOps** | Docker, Docker Compose | Compose v2+ |
| **External AI** | Groq API (`GROQ_MODEL`, default `openai/gpt-oss-120b`) | Requires `GROQ_API_KEY` |

---

## Key Features

Features below reflect **what is actually working today**, grouped by role. Items marked *(API only)* are available via REST/Swagger but not yet connected to the React dashboards.

### Patient

- Register and log in with JWT session management (access + refresh tokens)
- ✅ **Full booking flow verified end-to-end:** log in → describe symptoms → AI triage → doctor recommendation → appointment confirmation → saved to database
- ✅ **Appointment confirmation working:** `user_id` → `patient_id` lookup fixed; appointments now save successfully to PostgreSQL
- ✅ **Role-based route guards verified:** patients land on `/dashboard`, admins redirect to `/admin`, cross-role navigation is blocked
- Emergency symptom detection with immediate ER / ambulance guidance
- Reschedule existing appointments through chat (by appointment ID)
- FAQ answers for clinic hours and consultation fees
- Patient dashboard and appointments pages wired to live API

### Doctor

- View and filter appointments via API *(API only)*
- Real-time availability endpoint with schedule, break, and holiday awareness *(API only)*
- Update personal schedule and mark holidays *(API only)*
- Mark appointments complete or no-show *(API only)*
- 🏗️ Doctor dashboard: login and role-redirect verified; full workflow actions (mark complete / no-show) tested at API level but UI interaction testing pending

### Receptionist

- Access shared patient/receptionist dashboard route
- List and manage appointments across the clinic *(API only)*
- View analytics dashboard and daily summary *(API only)*

### Admin

- ✅ **Admin dashboard verified:** displays real clinic metrics, doctor lists, and clinic records from live backend APIs
- Create clinics and list clinic details
- Operational analytics: appointment volume, utilization, urgency breakdown, symptom trends

---

## Getting Started / Local Setup

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/) v2+
- A [Groq API key](https://console.groq.com/) (free tier works for demos)
- Git

### 1. Clone the repository

```bash
git clone https://github.com/Mzaq1559/MEDIBOOK_AI.git
cd MEDIBOOK_AI
```

### 2. Configure environment variables

Copy the root example file and set your Groq key:

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
GROQ_API_KEY=your-groq-api-key-here
GROQ_MODEL=openai/gpt-oss-120b
```

<details>
<summary>Full environment variable reference</summary>

**Root / Docker Compose** (`.env` — consumed by `ai-service`):

| Variable | Purpose | Default |
|----------|---------|---------|
| `GROQ_API_KEY` | Groq LLM API key | *(required)* |
| `GROQ_MODEL` | Model ID for NLU | `openai/gpt-oss-120b` |

**Backend** (set in `docker-compose.yml` or `backend/.env`):

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key (≥32 chars) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL |
| `ALLOWED_ORIGINS` | CORS allowed origins |

**AI Service** (set in `docker-compose.yml` or `ai-service/.env`):

| Variable | Purpose |
|----------|---------|
| `BACKEND_API_URL` | Internal backend base URL (`http://backend:8000/api`) |
| `AI_SERVICE_PORT` | Service port (8001) |
| `CONVERSATION_MAX_HISTORY` | Max messages kept in session |

**Frontend** (set in `docker-compose.yml`):

| Variable | Purpose |
|----------|---------|
| `VITE_API_URL` | Backend proxy path (`/api`) |
| `VITE_CHAT_API_URL` | AI service proxy path (`/chat`) |
| `VITE_PROXY_BACKEND` | Docker-internal backend URL |
| `VITE_PROXY_AI_SERVICE` | Docker-internal AI service URL |

> `GOOGLE_CALENDAR_*`, `WHATSAPP_*`, and `SMTP_*` variables exist in `backend/.env.example` but are **not wired to live integrations** in the current codebase.

</details>

### 3. Build and start services

```bash
docker compose build
docker compose up -d
```

Wait for PostgreSQL health checks to pass, then verify:

```bash
curl http://localhost:8000/health   # backend
curl http://localhost:8001/health   # ai-service
```

### 4. Seed demo data

**Standard demo seed** (single clinic — Prime Care Clinic Taxila, 3 doctors, 3 patients, sample appointments):

```bash
docker compose exec backend python -m app.services.seed
```

**Bulk test data** (3 clinics, ~19 doctors, 100–150 patients, 500+ appointments):

```bash
docker compose exec backend python -m app.services.seed --bulk-test-data
```

**Minimal test admin only:**

```bash
docker compose exec backend python -m app.services.seed --test-admin
```

### 5. Access the application

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:3000 |
| **Backend Swagger** | http://localhost:8000/docs |
| **Backend ReDoc** | http://localhost:8000/redoc |
| **AI Service Swagger** | http://localhost:8001/docs |
| **PostgreSQL** | `localhost:5432` (user: `medibook`, db: `medibook_db`) |

### Demo login credentials

<details>
<summary>Standard seed accounts (after <code>python -m app.services.seed</code>)</summary>

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@primecare.pk` | `AdminPass123!` |
| Receptionist | `receptionist@primecare.pk` | `RecepPass123!` |
| Doctor | `ahmed.khan@primecare.pk` | `DoctorPass123!` |
| Patient | `ali.khan@example.com` | `PatientPass123!` |

Test admin (from `--test-admin`): `admin@medibook.com` / `Admin@123`

</details>

<details>
<summary>Bulk seed accounts (after <code>--bulk-test-data</code>)</summary>

All bulk-generated users share:

- **Password:** `BulkSeed123!`
- **Email domain:** `@bulkseed.medibook.test`

Examples:

| Role | Example email |
|------|---------------|
| Patient | `patient.1@bulkseed.medibook.test` |
| Doctor | `doctor.{name}.{n}@bulkseed.medibook.test` |
| Receptionist | `receptionist.1@bulkseed.medibook.test` |

</details>

### Recommended demo flow

1. Open http://localhost:3000 and register or log in as a **patient**
2. Go to **Chat** and describe symptoms (e.g. *"I have chest tightness and palpitations"*)
3. Follow the bot through triage, doctor selection, and confirmation
4. Explore live APIs at http://localhost:8000/docs (appointments, doctors, analytics)

---

## API Documentation

Full endpoint specifications live in **`docs/MEDIBOOK_AI_COMPLETE_SPECIFICATIONS.txt`** (Section 4). Interactive documentation is available when services are running:

- Backend: http://localhost:8000/docs
- AI Service: http://localhost:8001/docs

> Note: `API_CONTRACTS.md` is referenced in early project docs but the canonical contract is the specification file above. Swagger reflects the implemented routes.

### Primary endpoint groups

| Group | Base path | Description |
|-------|-----------|-------------|
| **Auth** | `/api/auth` | Register, login, refresh, logout, `/me` |
| **Appointments** | `/api/appointments` | CRUD, reschedule, cancel, complete, no-show, feedback |
| **Doctors** | `/api/doctors` | List, detail, availability, schedule update, holidays |
| **Clinics** | `/api/clinics` | List, detail, create (admin) |
| **Patients** | `/api/patients` | Profile, update, appointment history |
| **Analytics** | `/api/analytics` | Dashboard metrics, daily summary |
| **Chat (AI)** | `/api/chat` on **port 8001** | Message, conversation history |
| **Health** | `/health` | Service health checks |

---

## Database Schema

The complete schema specification is in **`docs/MEDIBOOK_AI_COMPLETE_SPECIFICATIONS.txt`** (Section 3). The Alembic migration `backend/alembic/versions/001_initial_schema.py` creates **9 core tables**.

### Entity-relationship diagram (core tables)

```mermaid
erDiagram
    users ||--o| doctors : "user_id"
    users ||--o| patients : "user_id"
    clinics ||--o{ doctors : "clinic_id"
    clinics ||--o{ appointments : "clinic_id"
    clinics ||--o{ clinic_holidays : "clinic_id"
    doctors ||--o{ doctor_schedules : "doctor_id"
    doctors ||--o{ appointments : "doctor_id"
    doctors ||--o{ prescriptions : "doctor_id"
    patients ||--o{ appointments : "patient_id"
    patients ||--o{ prescriptions : "patient_id"
    appointments ||--o| prescriptions : "appointment_id"

    users {
        uuid id PK
        string email UK
        string phone UK
        string name
        string password_hash
        enum user_type
        boolean is_active
        timestamp created_at
    }

    clinics {
        uuid id PK
        string name UK
        string address
        string city
        time working_hours_start
        time working_hours_end
        string working_days
        string timezone
    }

    doctors {
        uuid id PK
        uuid user_id FK
        uuid clinic_id FK
        string specialization
        numeric consultation_fee
        boolean is_available
        int max_patients_per_day
    }

    patients {
        uuid id PK
        uuid user_id FK
        date date_of_birth
        string gender
        string preferred_notification
        string emergency_contact_name
    }

    appointments {
        uuid id PK
        uuid clinic_id FK
        uuid doctor_id FK
        uuid patient_id FK
        datetime appointment_time
        string status
        string urgency_level
        text symptoms_reported
        string google_calendar_event_id
        boolean reminder_sent_24h
        boolean reminder_sent_1h
    }

    prescriptions {
        uuid id PK
        uuid appointment_id FK
        uuid doctor_id FK
        uuid patient_id FK
        text medications
        text instructions
        datetime expires_at
    }
```

Additional tables: `doctor_schedules`, `clinic_holidays`, `audit_logs`.

---

## AI Chatbot Capabilities

The AI microservice (`ai-service/`) handles all chat traffic from the frontend. It combines **Groq LLM NLU** with **deterministic rule-based triage** and **backend API calls** for live booking.

### Supported intents

| Intent | Description |
|--------|-------------|
| `appointment` | Full booking flow: symptoms → follow-ups → doctor/slot → confirm |
| `symptom` | Symptom description triggers triage routing |
| `faq` | Clinic hours, consultation fees, general questions |
| `reschedule` | Change an existing appointment by ID |

### NLU pipeline

1. **Keyword pre-routing** — obvious confirmations, hours, and fee queries skip the LLM
2. **Groq JSON-mode NLU** — extracts intent, doctor name, date, symptoms, appointment ID, confirm/decline flags
3. **Rule-based triage** (`symptom_triage.py`) — maps symptoms to Cardiologist / Dermatologist / ENT Specialist; detects emergencies
4. **Backend integration** — fetches doctors, availability, creates/reschedules appointments with the patient's JWT

### Example conversations

<details>
<summary>Example 1 — Symptom triage and booking</summary>

```
Patient:  I have had a sore throat and blocked nose for five days.
Bot:      Thank you. I will route you to the right specialist — I will not diagnose the condition.
          Let me ask a few quick questions:
          Which area is bothering you most — ear, nose, or throat?
Patient:  Mostly nose and throat, no fever.
Bot:      Thanks. Do you have fever, or is it mainly pain or congestion?
Patient:  Just congestion.
Bot:      Based on your symptoms, I recommend seeing a ENT Specialist. This is a routing suggestion only, not a diagnosis.
          Based on what you described, here are available doctors and times:
          1. Dr. Zain Ali (ENT Specialist) — Prime Care Clinic Taxila — 2026-08-25 at 09:00, ...
Patient:  Dr. Zain Ali at 09:00
Bot:      Perfect! Let me confirm your appointment:
          Doctor: Dr. Zain Ali (ENT Specialist)
          Date/Time: 2026-08-25 at 09:00
          ...
          Shall I go ahead and book this appointment?
Patient:  yes
Bot:      Great! Your appointment is confirmed!
          Appointment ID: ...
```

</details>

<details>
<summary>Example 2 — Emergency detection</summary>

```
Patient:  I have severe chest pain and I cannot breathe properly.
Bot:      🚨 EMERGENCY ALERT 🚨
          This requires IMMEDIATE medical attention. Do NOT wait.
          PLEASE CALL: 1100 (Emergency) or 15 (Ambulance)
          Or go to the nearest emergency room immediately!
          This is a medical emergency - our clinic appointment system is NOT suitable for this situation.
```

</details>

---

## Project Structure

```
MEDIBOOK_AI/
├── backend/                 # FastAPI clinic management API (auth, appointments, analytics)
│   ├── app/
│   │   ├── routes/          # REST endpoint handlers
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── services/        # Business logic, seed scripts, availability engine
│   │   ├── schemas/         # Pydantic request/response models
│   │   └── core/            # Auth, security, config, audit
│   ├── alembic/             # Database migrations
│   └── tests/               # Pytest suite (46+ tests)
├── frontend/                # React + Vite SPA (auth + chat live; dashboards UI-only)
│   └── src/
│       ├── pages/           # Route-level views
│       ├── services/        # Axios API clients
│       └── components/      # Shared UI components
├── ai-service/              # AI virtual receptionist microservice (Groq + triage + booking)
│   ├── app/
│   │   ├── chatbot.py       # Conversation state machine
│   │   ├── groq_client.py   # Groq LLM wrapper
│   │   ├── symptom_triage.py
│   │   └── backend_client.py
│   └── tests/               # AI service pytest suite
├── docs/                    # Hackathon specifications and design docs
│   └── MEDIBOOK_AI_COMPLETE_SPECIFICATIONS.txt
├── docker-compose.yml       # Multi-service orchestration
└── .env.example             # Environment template (Groq key required)
```

---

## Testing

### Backend tests

```bash
# Inside the backend container
docker compose exec backend pytest -v

# With coverage
docker compose exec backend pytest --cov=app --cov-report=term-missing
```

The backend suite covers auth, appointments (including double-booking prevention), doctor availability, clinics, patients, analytics, seeding, and error handling. Tests use in-memory SQLite via `tests/conftest.py`.

### AI service tests

```bash
docker compose exec ai-service pytest -v
```

Covers symptom triage rules, chat API endpoints, and Groq client error handling.

### Manual verification checklist

| Check | Status | Command / Action |
|-------|--------|------------------|
| Backend health | ✅ Verified | `curl http://localhost:8000/health` |
| AI service health | ✅ Verified | `curl http://localhost:8001/health` |
| Database seeded | ✅ Verified | `docker compose exec backend python -m app.services.seed` |
| Auth flow (login + JWT) | ✅ Verified | Log in as `ali.khan@example.com` → `GET /api/auth/me` with token |
| Role-based routing — Patient | ✅ Verified | Login as patient → lands on `/dashboard`; `/admin` blocked |
| Role-based routing — Admin | ✅ Verified | Login as `admin@primecare.pk` → lands on `/admin`; `/dashboard` blocked |
| Full AI booking flow | ✅ Verified | Patient login → `/chat` → symptoms → triage → doctor select → confirm → appointment saved to DB |
| Appointment confirmation (DB save) | ✅ Verified | `user_id` → `patient_id` lookup fixed; appointments appear in `GET /api/patients/me/appointments` |
| Admin dashboard metrics | ✅ Verified | Login as admin → `/admin` shows real clinic, doctor, and appointment data from API |
| Doctor login + redirect | ✅ Verified | Login as `ahmed.khan@primecare.pk` → redirected to doctor dashboard |
| Analytics API | ✅ Verified | `GET /api/analytics/dashboard` as admin/doctor token |
| Swagger smoke test | ✅ Verified | Create appointment via `/docs` with patient JWT |

---

## Known Limitations / Future Work

### Current MVP scope

- **Single-clinic focus** in the standard seed (bulk seed adds 3 clinics via API only)
- **Web-first** — responsive layout but no native mobile app
- **English-primary** chat (Urdu/English bilingual support was a stretch goal)
- **In-memory chat sessions** — conversations reset on AI service restart

### Integrations not yet live

| Integration | Codebase status |
|-------------|-----------------|
| WhatsApp Business API reminders | Env vars + DB flags only; bot *mentions* reminders but nothing is sent |
| Google Calendar sync | `google_calendar_event_id` column; no API calls |
| n8n workflows | Not implemented |
| Email (SMTP) | Config placeholders only |
| Prescription management | DB model only; no CRUD routes |

### Frontend gaps

- ✅ **Patient booking flow** (login → chat triage → doctor recommendation → appointment confirmation → DB save) — **fully verified end-to-end**
- ✅ **Admin dashboard** — wired to live backend APIs; shows real clinic metrics, doctor/clinic lists
- ✅ **Role-based routing** — patients go to `/dashboard`, admins to `/admin`; unauthorized cross-role navigation is blocked and redirected
- 🏗️ **Doctor Dashboard:** Code fully wired and tested for login/redirect; full workflow testing (mark complete/no-show actions) pending but architected correctly
- **Admin panel** create/edit forms (add doctor/clinic) write to the live API; bulk-delete and advanced filtering are UI-only state
- **WhatsApp / SMS reminders:** timestamps computed and stored on booking; no outbound messages sent yet

### Realistic next steps (post-hackathon)

1. Complete doctor dashboard UI interaction testing (mark complete / no-show from the dashboard)
2. Implement WhatsApp reminder worker (cron or n8n) using computed `reminder_time_1/2`
3. Add Google Calendar event creation on appointment confirm
4. Prescription endpoints for doctors completing visits
5. Persist chat sessions to PostgreSQL or Redis
6. Urdu NLU prompts and bilingual UI

---

## Team

Built in 6 days by a 4-person team for the Alibaba Cloud AI Hackathon Pakistan 2026.

| Name | Role | GitHub | Contributions |
|------|------|--------|---------------|
| Muhammad Zulqarnain Abdullah | Project Lead | [@Mzaq1559](https://github.com/Mzaq1559) | Architecture, Docker, seeding, chat integration, repo coordination |
| Sidra Pervaiz | Backend Developer | [@SidraPervaiz1122](https://github.com/SidraPervaiz1122)| FastAPI backend core, database models, appointment engine, tests |
| Aleeza Imran | Frontend Developer | [@BSCS2455](https://github.com/BSCS2455) | React UI, design system, page layouts |
| Ayesha Sajjad | AI & Integrations | [@AyeshaSajjad0786](https://github.com/AyeshaSajjad0786) | AI microservice, Groq NLU, symptom triage, booking conversation flow |

---

## License

No open-source license file is included in this repository. This project is submitted for **Alibaba Cloud AI Hackathon Pakistan 2026** evaluation purposes.
