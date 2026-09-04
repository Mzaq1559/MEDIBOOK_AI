# MediBook AI — API Contracts

This document specifies the complete REST, SSE, and Tool-Calling API contracts for the MediBook AI platform.

---

## 1. Network Routing & Proxy Architecture

Clients interact with the system via the Frontend (Port 3000), which proxies requests to the appropriate microservice:

```
┌─────────────────────────────────────────────────────────────┐
│                    Vite Client (Port 3000)                  │
├───────────────────────────────┬─────────────────────────────┤
│  Route Prefix: /api/*         │  Route Prefix: /chat/*      │
│  Proxies to:                  │  Rewrites to /api/chat/*    │
│  Backend API (Port 8000)      │  Proxies to AI Service (8001)│
└───────────────────────────────┴─────────────────────────────┘
```

---

## 2. Authentication & Security Headers

All authenticated endpoints require an `Authorization` header containing a valid JWT Bearer token:
```http
Authorization: Bearer <access_token>
```
- Algorithm: `HS256`
- Access Token Expiration: 60 minutes
- Refresh Token Expiration: 1 day
- User types: `patient`, `doctor`, `receptionist`, `admin`

---

## 3. AI Service API (Port 8001 / `/chat`)

Base URL: `http://ai-service:8001` (or `/chat` through frontend proxy)

### 3.1 Send Chat Message
- **Endpoint:** `POST /api/chat/message`
- **Rate Limit:** 60 requests/minute
- **Headers:** `Authorization: Bearer <token>` (optional for general inquiries, required for bookings/history)
- **Request Body:**
```json
{
  "conversation_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "patient_id": "123e4567-e89b-12d3-a456-426614174001",
  "message": "I need to see a cardiologist tomorrow morning",
  "language": "english",
  "stream": false
}
```

#### Synchronous JSON Response (`stream: false`)
- **Status:** `200 OK`
```json
{
  "conversation_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "patient_id": "123e4567-e89b-12d3-a456-426614174001",
  "timestamp": "2026-09-04T11:00:00Z",
  "bot_message": "Dr. Tariq Mahmood is available tomorrow at 10:00 AM. Would you like me to book that for you?",
  "next_action": "waiting_for_confirmation",
  "options": [],
  "ui_data": {
    "booking": {
      "doctor": {
        "doctor_id": "doc-uuid",
        "name": "Dr. Tariq Mahmood",
        "specialization": "Cardiologist",
        "clinic_name": "LifeCare Clinic"
      },
      "selectedSlot": "Tomorrow at 10:00 AM",
      "isConfirmed": false
    }
  },
  "conversation_history": [
    {"role": "user", "message": "I need to see a cardiologist tomorrow morning", "timestamp": "2026-09-04T10:59:58Z"},
    {"role": "assistant", "message": "Dr. Tariq Mahmood is available tomorrow at 10:00 AM...", "timestamp": "2026-09-04T11:00:00Z"}
  ]
}
```

#### Server-Sent Events Streaming (`stream: true` or `Accept: text/event-stream`)
- **Status:** `200 OK`
- **Content-Type:** `text/event-stream`

```text
event: status
data: {"label": "Looking up available doctors..."}

event: status
data: {"label": "Checking availability..."}

event: final
data: {"conversation_id": "9b1deb4d-...", "bot_message": "...", "next_action": "...", "ui_data": {...}, ...}
```

If an error occurs during streaming:
```text
event: error
data: {"message": "Our AI assistant encountered an issue. Please try again in a moment."}
```

---

### 3.2 Get Chat History
- **Endpoint:** `GET /api/chat/history/{conversation_id}`
- **Status:** `200 OK`
```json
{
  "conversation_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "patient_id": "123e4567-e89b-12d3-a456-426614174001",
  "created_at": "2026-09-04T10:00:00Z",
  "updated_at": "2026-09-04T10:05:00Z",
  "messages": [
    {"role": "user", "message": "Hi", "timestamp": "2026-09-04T10:00:00Z"},
    {"role": "assistant", "message": "Hi Ali! How can I help you today?", "timestamp": "2026-09-04T10:00:01Z"}
  ],
  "status": "ongoing",
  "appointment_booked": null
}
```

---

### 3.3 RAG Health Check
- **Endpoint:** `GET /api/rag/health`
- **Status:** `200 OK`
```json
{
  "enabled": true,
  "vector_db": "healthy",
  "embedding_model": "loaded",
  "collection": "medical_knowledge",
  "document_count": 86,
  "metrics": {
    "rag_queries_total": 15,
    "rag_retrieval_success_total": 15,
    "rag_cache_hits_total": 3,
    "rag_fallback_total": 0,
    "agent_tool_calls_total": 48,
    "circuit_breaker_state": "CLOSED"
  }
}
```

---

## 4. Agent Tool-Calling Interface (Internal Schemas)

The Groq LLM selects from these function schemas defined in `ai-service/app/tools.py`.

### 4.1 Read-Only Tools

| Tool | Parameters | Description |
|---|---|---|
| `get_patient_appointments` | `patient_id: string` | Fetches upcoming appointments for authenticated patient. |
| `search_patient_appointments` | `doctor_name?: string`, `status?: enum`, `date_from?: string`, `date_to?: string` | Filtered search over patient's own appointments. |
| `get_doctors_by_specialty` | `specialty: string` | Lists active doctors matching the requested specialization. |
| `get_availability` | `doctor_id: string`, `date: string` | Returns open consultation time slots for doctor starting on date. |
| `get_patient_info` | `patient_id: string` | Returns profile, allergies, and conditions of authenticated patient. |
| `retrieve_medical_knowledge`| `symptoms: string` | Queries RAG ChromaDB knowledge base to return clinical triage and specialist recommendation. |

### 4.2 Write Tools (Propose-Confirm-Execute Gate)

All mutations enforce a two-step validation gate. Proposals are cached in-memory with a 5-minute TTL.

#### 1. `propose_book_appointment`
- **Arguments:** `patient_id`, `doctor_id`, `datetime`, `symptoms`
- **Returns:**
```json
{
  "ok": true,
  "proposal_id": "78e9c402-fa32-4d2a-8833-ff14a27bc911",
  "summary": "Book appointment with Dr. Tariq Mahmood on Tomorrow at 10:00 AM.",
  "ui_data": {"booking": {"isConfirmed": false, "selectedSlot": "Tomorrow at 10:00 AM"}}
}
```

#### 2. `propose_reschedule_appointment`
- **Arguments:** `appointment_id`, `new_datetime`
- **Returns:** `{"ok": true, "proposal_id": "...", "summary": "Reschedule appointment to..."}`

#### 3. `propose_cancel_appointment`
- **Arguments:** `appointment_id`
- **Returns:** `{"ok": true, "proposal_id": "...", "summary": "Cancel appointment with Dr. Tariq Mahmood."}`

#### 4. `execute_confirmed_action`
- **Arguments:** `proposal_id: string`
- **Validation:** Verifies proposal exists, `used == false`, `age <= 300s`, and matches active `patient_id` and `conversation_id`.
- **Commit:** Calls backend API to persist to PostgreSQL, fires Google Calendar sync, and dispatches n8n reminder webhook.

---

## 5. Backend Core API (Port 8000 / `/api`)

Base URL: `http://backend:8000` (or `/api` through frontend proxy)

### 5.1 Authentication (`/api/auth`)

#### User Registration
- `POST /api/auth/register` (Rate limit: 5/min)
- Request:
```json
{
  "email": "ali.khan@example.com",
  "password": "SecurePassword123!",
  "name": "Ali Khan",
  "phone": "03001234567",
  "user_type": "patient"
}
```
- Response (201 Created): `{ "id": "...", "email": "...", "user_type": "patient" }`

#### User Login
- `POST /api/auth/login` (Rate limit: 10/min)
- Request: `{ "email": "ali.khan@example.com", "password": "SecurePassword123!" }`
- Response (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1Ni...",
  "refresh_token": "eyJhbGciOiJIUzI1Ni...",
  "token_type": "bearer",
  "user": { "id": "...", "name": "Ali Khan", "user_type": "patient", "patient_id": "..." }
}
```

#### Refresh Token
- `POST /api/auth/refresh`
- Request: `{ "refresh_token": "eyJhbGciOiJIUzI1Ni..." }`
- Response (200 OK): `{ "access_token": "...", "token_type": "bearer" }`

#### Get Current Profile
- `GET /api/auth/me` (Auth required)
- Response (200 OK): Complete user record with associated `patient` or `doctor` profile.

---

### 5.2 Appointments (`/api/appointments`)

#### Create Appointment
- `POST /api/appointments` (Auth required)
- Request:
```json
{
  "clinic_id": "clinic-uuid",
  "doctor_id": "doctor-uuid",
  "patient_id": "patient-uuid",
  "appointment_time": "2026-09-05T10:00:00Z",
  "symptoms_reported": "Persistent dry cough",
  "urgency_level": "normal",
  "appointment_type": "in_person"
}
```
- Response (201 Created): Returns the created `Appointment` record.

#### List Appointments
- `GET /api/appointments?doctor_id=&patient_id=&status=&date_from=&date_to=&limit=50&offset=0`
- Response (200 OK): Paginated appointments scoped by role (patients only see their own).

#### Search Patient Appointments
- `GET /api/appointments/search?doctor_name=&status=&date_from=&date_to=`
- Response (200 OK): Filtered appointments for the authenticated patient sorted by time ascending.

#### Reschedule Appointment
- `PUT /api/appointments/{id}/reschedule`
- Request: `{ "new_appointment_time": "2026-09-06T11:00:00Z" }`
- Response (200 OK): Updated appointment record.

#### Cancel Appointment
- `PATCH /api/appointments/{id}/cancel` (or `DELETE /api/appointments/{id}`)
- Request: `{ "reason": "Conflict in schedule" }`
- Response (200 OK): `{ "success": true, "message": "Appointment cancelled" }`

#### Bulk Cancel Appointments
- `POST /api/appointments/bulk-cancel`
- Request: `{ "patient_id": "...", "appointment_ids": ["uuid1", "uuid2"] }`
- Response (200 OK): `{ "cancelled_count": 2, "cancelled_ids": [...] }`

---

### 5.3 Doctors (`/api/doctors`)

#### List Doctors
- `GET /api/doctors?specialization=&clinic_id=&is_available=true`
- Response (200 OK): Array of doctor profiles with fees, qualifications, and ratings.

#### Get Doctor Availability
- `GET /api/doctors/{id}/availability?date=2026-09-05&next_days=3`
- Response (200 OK):
```json
{
  "doctor_id": "doc-uuid",
  "doctor_name": "Dr. Tariq Mahmood",
  "specialization": "Cardiologist",
  "availability": [
    {
      "date": "2026-09-05",
      "day_of_week": "Saturday",
      "slots": [
        {"time": "10:00 AM", "timestamp": "2026-09-05T10:00:00Z", "available": true},
        {"time": "10:30 AM", "timestamp": "2026-09-05T10:30:00Z", "available": false}
      ]
    }
  ]
}
```

---

### 5.4 Patients (`/api/patients`)

#### Get Patient Record
- `GET /api/patients/{id}` (Auth required; scoped to own profile or staff)
- Response (200 OK): Profile, allergies, medical conditions, and emergency contacts.

#### Update Patient Record
- `PUT /api/patients/{id}`
- Request: Fields to update (`allergies`, `medical_conditions`, `emergency_contact_phone`, etc.)

---

### 5.5 Clinics (`/api/clinics`)

- `GET /api/clinics` — List registered clinics.
- `GET /api/clinics/{id}` — Get clinic details and working hours.
- `GET /api/clinics/{id}/holidays` — List upcoming clinic closures.

---

### 5.6 Prescriptions (`/api/prescriptions`)

- `GET /api/prescriptions/{id}` — Get prescription details.
- `GET /api/prescriptions?patient_id=&doctor_id=` — List prescriptions (scoped by role).
- `POST /api/prescriptions` — Create prescription (Doctor or staff only).
- `PUT /api/prescriptions/{id}` — Update prescription.
- `DELETE /api/prescriptions/{id}` — Soft delete prescription (`deleted_at` set).

---

### 5.7 Analytics (`/api/analytics`)

- `GET /api/analytics/dashboard` (Admin / Receptionist / Doctor)
  - Returns total appointments today, revenue, cancellation rate, no-show rate, and doctor utilization.
