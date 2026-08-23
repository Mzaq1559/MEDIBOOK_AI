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
