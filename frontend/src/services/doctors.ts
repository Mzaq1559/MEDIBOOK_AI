import { apiClient } from './api'

export interface DoctorListItem {
  doctor_id: string
  user_id: string
  name: string
  email: string
  phone?: string
  specialization: string
  consultation_fee: number
  bio?: string
  is_available: boolean
  rating: number
  total_appointments: number
  languages_spoken: string[]
  clinic_id: string
  clinic_name: string
}

export interface DoctorListResponse {
  total: number
  limit: number
  offset: number
  doctors: DoctorListItem[]
}

export async function listDoctors(params?: { clinic_id?: string; limit?: number; offset?: number }) {
  const { data } = await apiClient.get<DoctorListResponse>('/doctors', { params })
  return data
}

export async function getDoctor(id: string) {
  const { data } = await apiClient.get(`/doctors/${id}`)
  return data
}

export async function createDoctor(payload: {
  name: string
  email: string
  specialization: string
  clinic_id: string
  consultation_fee?: number
  max_patients_per_day?: number
  bio?: string
  is_available?: boolean
}) {
  const { data } = await apiClient.post('/doctors', payload)
  return data
}

export async function updateDoctor(
  id: string,
  payload: {
    name?: string
    email?: string
    specialization?: string
    clinic_id?: string
    consultation_fee?: number
    max_patients_per_day?: number
    bio?: string
    is_available?: boolean
  }
) {
  const { data } = await apiClient.put(`/doctors/${id}`, payload)
  return data
}

// ─── Doctor Application Management (Admin) ───────────────────────────────────────

export interface DoctorApplicationItem {
  id: string
  user_id: string
  name: string
  email: string
  phone?: string
  specialization?: string
  qualifications?: string
  bio?: string
  is_verified: boolean
  created_at: string
}

export interface DoctorApplicationListResponse {
  applications: DoctorApplicationItem[]
  total: number
}

export async function listDoctorApplications(statusFilter?: string) {
  const params = statusFilter ? { status_filter: statusFilter } : {}
  const { data } = await apiClient.get<DoctorApplicationListResponse>('/doctors/applications', { params })
  return data
}

export async function approveDoctorApplication(
  doctorId: string,
  payload: {
    clinic_id: string
    specialization: string
    consultation_fee?: number
    qualifications?: string
  }
) {
  const { data } = await apiClient.post(`/doctors/${doctorId}/approve`, payload)
  return data
}

export async function rejectDoctorApplication(doctorId: string, reason?: string) {
  const { data } = await apiClient.post(`/doctors/${doctorId}/reject`, { reason })
  return data
}
