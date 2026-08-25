import axios from 'axios'

/** Relative base paths — Vite dev/preview proxy forwards these to backend & AI service. */
export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'
export const CHAT_API_BASE_URL = import.meta.env.VITE_CHAT_API_URL || '/chat'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

export const chatApiClient = axios.create({
  baseURL: CHAT_API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

export function setAuthToken(token: string | null): void {
  const header = token ? `Bearer ${token}` : undefined

  if (header) {
    apiClient.defaults.headers.common.Authorization = header
    chatApiClient.defaults.headers.common.Authorization = header
  } else {
    delete apiClient.defaults.headers.common.Authorization
    delete chatApiClient.defaults.headers.common.Authorization
  }
}
