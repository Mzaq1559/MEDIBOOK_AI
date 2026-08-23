import { apiClient } from './api'

export interface DashboardMetricsResponse {
  date: string
  clinic_id?: string
  clinic_name: string
  total_appointments_today: number
  completed_today: number
  cancelled_today: number
  no_show_today: number
  upcoming_today: number
  total_patients: number
  average_wait_time_minutes: number
  doctor_utilization_percent: number
  no_show_rate_percent: number
  average_rating: number
  high_urgency_appointments: number
  critical_urgency_appointments: number
  common_symptoms: Array<{ symptom: string; count: number }>
}

export async function getDashboardMetrics(params?: { clinic_id?: string; date?: string }) {
  const { data } = await apiClient.get<DashboardMetricsResponse>('/analytics/dashboard', { params })
  return data
}

export async function getDailySummary(params: { date: string; doctor_id?: string; clinic_id?: string }) {
  const { data } = await apiClient.get('/analytics/daily-summary', { params })
  return data
}
