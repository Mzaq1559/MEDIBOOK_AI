# MediBook AI API Contracts

This document outlines the REST API endpoints available in the MediBook AI backend.

---

## Prescriptions API

**Base Path:** `/api/prescriptions`
**Tags:** `prescriptions`

### 1. Get Prescription
- **Endpoint:** `GET /api/prescriptions/{prescription_id}`
- **Authentication:** Required (Bearer Token)
- **Roles:** Admin, Receptionist, Doctor (if created by them), Patient (if it belongs to them)
- **Response (200 OK):**
```json
{
  "medication": "Amoxicillin",
  "dosage": "500mg",
  "duration": "7 days",
  "notes": "Take after meals",
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "patient_id": "123e4567-e89b-12d3-a456-426614174001",
  "doctor_id": "123e4567-e89b-12d3-a456-426614174002",
  "appointment_id": "123e4567-e89b-12d3-a456-426614174003",
  "created_at": "2023-10-27T10:00:00Z"
}
```
- **Errors:** 403 Forbidden (if unauthorized access), 404 Not Found (if deleted or missing)

### 2. List Prescriptions
- **Endpoint:** `GET /api/prescriptions`
- **Query Params:** 
  - `patient_id` (UUID, optional)
  - `doctor_id` (UUID, optional)
  - `appointment_id` (UUID, optional)
  - `limit` (int, default: 10)
  - `offset` (int, default: 0)
- **Authentication:** Required (Bearer Token)
- **Roles:** All (results are scoped: patients only see theirs, doctors only see ones they created)
- **Response (200 OK):**
```json
[
  {
    "medication": "Amoxicillin",
    "dosage": "500mg",
    "duration": "7 days",
    "notes": "Take after meals",
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "patient_id": "123e4567-e89b-12d3-a456-426614174001",
    "doctor_id": "123e4567-e89b-12d3-a456-426614174002",
    "appointment_id": "123e4567-e89b-12d3-a456-426614174003",
    "created_at": "2023-10-27T10:00:00Z"
  }
]
```

### 3. Create Prescription
- **Endpoint:** `POST /api/prescriptions`
- **Authentication:** Required (Bearer Token)
- **Roles:** Admin, Receptionist, Doctor
- **Request Body:**
```json
{
  "medication": "Amoxicillin",
  "dosage": "500mg",
  "duration": "7 days",
  "notes": "Take after meals",
  "patient_id": "123e4567-e89b-12d3-a456-426614174001",
  "doctor_id": "123e4567-e89b-12d3-a456-426614174002",
  "appointment_id": "123e4567-e89b-12d3-a456-426614174003"
}
```
- **Response (201 Created):** Returns the created prescription object.
- **Errors:** 400 Bad Request (invalid IDs), 403 Forbidden (not authorized)

### 4. Update Prescription
- **Endpoint:** `PUT /api/prescriptions/{prescription_id}`
- **Authentication:** Required (Bearer Token)
- **Roles:** Admin, Receptionist, Doctor (only the creator)
- **Request Body (all fields optional):**
```json
{
  "medication": "Amoxicillin",
  "dosage": "250mg",
  "duration": "14 days",
  "notes": "Take with water"
}
```
- **Response (200 OK):** Returns the updated prescription object.
- **Errors:** 403 Forbidden, 404 Not Found

### 5. Delete Prescription
- **Endpoint:** `DELETE /api/prescriptions/{prescription_id}`
- **Authentication:** Required (Bearer Token)
- **Roles:** Admin, Receptionist, Doctor (only the creator)
- **Description:** Performs a soft delete by setting `deleted_at` timestamp.
- **Response (204 No Content):** Empty body.
- **Errors:** 403 Forbidden, 404 Not Found
