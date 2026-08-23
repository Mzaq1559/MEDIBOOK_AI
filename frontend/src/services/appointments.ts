import { apiClient } from './api'

export interface AppointmentListParams {
  doctor_id?: string
  patient_id?: string
  clinic_id?: string
  status?: string
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
}

export async function listAppointments(params?: AppointmentListParams) {
  const { data } = await apiClient.get('/appointments', { params })
  return data
}

export async function getAppointment(appointmentId: string) {
  const { data } = await apiClient.get(`/appointments/${appointmentId}`)
  return data
}

export async function createAppointment(payload: Record<string, unknown>) {
  const { data } = await apiClient.post('/appointments', payload)
  return data
}

export async function cancelAppointment(appointmentId: string) {
  const { data } = await apiClient.delete(`/appointments/${appointmentId}`)
  return data
}

export async function submitAppointmentFeedback(
  appointmentId: string,
  payload: { rating: number; feedback?: string }
) {
  const { data } = await apiClient.post(`/appointments/${appointmentId}/feedback`, payload)
  return data
}
