# 🏆 MediBook AI — Hackathon Submission

## Project Overview

**MediBook AI** is an AI-powered virtual receptionist and clinic management platform built for small and medium-sized clinics in Pakistan. It combines an agentic LLM, medical RAG, real-time appointment management, and a full clinic operations dashboard in a single, Dockerized system.

---

## Submission Details

| Field | Value |
|---|---|
| **Project Name** | MediBook AI |
| **Category** | Agentic AI / Healthcare Tech |
| **Primary Language** | Python (FastAPI), TypeScript (React) |
| **LLM Provider** | Groq (tool-calling) |
| **Deployment** | Docker Compose (single command) |

---

## Three Implementations

This submission contains **three independently runnable branches** showcasing an architectural evolution:

| Branch | Description |
|---|---|
| `main` ⭐ | **Agentic RAG** — Groq tool-calling agent + ChromaDB RAG + propose→confirm safety gate |
| `rag` | **RAG-enabled** — ChromaDB medical knowledge retrieval with deterministic state machine |
| `baseline` | **Baseline** — Clean deterministic clinic chatbot, no retrieval |

---

## Key Technical Achievements

1. **Agentic Architecture** — Single Groq LLM drives the entire conversation using tool calling (doctor lookup, slot availability, booking, RAG medical triage, no-show management).
2. **Medical RAG** — ChromaDB vector store with curated medical knowledge base; cosine similarity retrieval with configurable relevance thresholds.
3. **Safety Gate** — All write actions (booking, cancellation) require an explicit patient confirmation before backend execution.
4. **Multilingual Support** — Urdu/English bilingual interface with RTL rendering.
5. **Clinic Dashboard** — Full React frontend for doctors, patients, appointments, schedules, prescriptions, and analytics.
6. **n8n Automation** — Appointment reminder workflows via n8n webhook integration.

---

## Quick Start (Judges)

```bash
# 1. Clone
git clone https://github.com/Mzaq1559/MEDIBOOK_AI.git
cd MEDIBOOK_AI

# 2. Set environment variables
cp .env.example .env
# Fill in your GROQ_API_KEY and SECRET_KEY in .env

# 3. Run everything
docker-compose up --build

# 4. Access
# Frontend:   http://localhost:3000
# Backend API: http://localhost:8000/docs
# AI Service:  http://localhost:8001/docs
# n8n:         http://localhost:5678
```

---

## Architecture at a Glance

```
Patient (Browser)
     │
     ▼
  React Frontend (Vite + TypeScript)
     │
     ├──► FastAPI Backend (auth, appointments, doctors, patients)
     │         └──► PostgreSQL DB
     │
     └──► AI Service (FastAPI)
               ├── Groq LLM Agent (tool-calling)
               ├── ChromaDB RAG (medical knowledge)
               └── n8n Webhooks (appointment reminders)
```

---

## Repository Structure

```
MEDIBOOK_AI/
├── frontend/          # React + Vite + TypeScript clinic dashboard
├── backend/           # FastAPI REST API + PostgreSQL (Alembic migrations)
├── ai-service/        # FastAPI AI service: agentic chatbot + RAG
│   └── app/
│       ├── chatbot.py            # Groq agent orchestration
│       ├── chatbot_handlers.py   # Tool call handlers
│       ├── tools.py              # Tool definitions
│       └── rag/                  # ChromaDB RAG pipeline
├── docker-compose.yml # Single-command deployment
├── .env.example       # Environment variable template
└── README.md          # Full documentation
```

---

## Team

| Name | Role |
|---|---|
| See `README.md → Team` section | Full details in README |

---

## Demo

See the [README.md Demo Scenarios](README.md#-demo-scenarios) section for a walkthrough of chatbot flows.

---

*Submitted for the MediBook AI Hackathon. All source code is original and built during the hackathon period.*
