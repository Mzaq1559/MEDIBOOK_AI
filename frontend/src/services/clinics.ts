import { apiClient } from './api'

export interface ClinicListItem {
  clinic_id: string
  name: string
  address: string
  city: string
  phone: string
  email: string
  working_hours_start: string
  working_hours_end: string
  working_days: string
  timezone: string
  is_active: boolean
  total_doctors?: number
  total_appointments_this_month?: number
}

export interface ClinicListResponse {
  total: number
  clinics: ClinicListItem[]
}

export async function listClinics(params?: { city?: string; limit?: number; offset?: number }) {
  const { data } = await apiClient.get<ClinicListResponse>('/clinics', { params })
  return data
}

export async function getClinic(id: string) {
  const { data } = await apiClient.get(`/clinics/${id}`)
  return data
}

export async function createClinic(payload: {
  name: string
  address: string
  city: string
  phone: string
  email: string
  working_hours_start?: string
  working_hours_end?: string
  working_days?: string
  timezone?: string
  is_active?: boolean
}) {
  const { data } = await apiClient.post('/clinics', payload)
  return data
}

export async function updateClinic(
  id: string,
  payload: {
    name?: string
    address?: string
    city?: string
    phone?: string
    email?: string
    working_hours_start?: string
    working_hours_end?: string
    working_days?: string
    timezone?: string
    is_active?: boolean
  }
) {
  const { data } = await apiClient.put(`/clinics/${id}`, payload)
  return data
}
