import axios from 'axios'
import { chatApiClient } from './api'

export interface ChatOptionItem {
  option_id: string
  text: string
  doctor_id?: string | null
}

export interface ParsedDoctorOption {
  doctor_id: string
  name: string
  specialization: string
  clinic_name: string
  clinic_address: string
  consultation_fee: string | number
  rating: number
}

export interface ParsedSlot {
  time: string
  date: string
  timestamp: string
  label: string
}

export interface ParsedAppointment {
  appointment_id: string
  doctor_name: string
  doctor_specialization: string
  appointment_time: string
  status: string
  clinic_name: string
  symptoms_reported: string
}

export interface ParsedBookingSummary {
  doctor: ParsedDoctorOption
  selectedSlot: string
  isConfirmed: boolean
}

export interface ParsedRescheduleSummary {
  doctor: ParsedDoctorOption
  oldSlot: string
  newSlot: string
}

export interface ChatUiData {
  doctors?: ParsedDoctorOption[]
  slots?: ParsedSlot[]
  appointments?: ParsedAppointment[]
  booking?: ParsedBookingSummary
  reschedule?: ParsedRescheduleSummary
}

export interface ChatMessageResponse {
  conversation_id: string
  patient_id?: string | null
  timestamp: string
  bot_message: string
  next_action?: string | null
  options: ChatOptionItem[]
  ui_data?: ChatUiData | null
  conversation_history?: Array<{ role: string; message: string; timestamp: string }>
}

export function isValidUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
}

const AVATAR_BACKGROUNDS = [
  'bg-primary/10 text-primary',
  'bg-secondaryContainer/50 text-secondary',
  'bg-tertiary/10 text-tertiary',
]

export function avatarBgForName(name: string): string {
  const index = name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
  return AVATAR_BACKGROUNDS[index % AVATAR_BACKGROUNDS.length]
}

export function formatChatTimestamp(isoOrDate?: string): string {
  if (!isoOrDate) {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  const parsed = new Date(isoOrDate)
  if (Number.isNaN(parsed.getTime())) {
    return isoOrDate
  }

  return parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function getChatErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'object' && detail?.message) {
      return detail.message
    }
    if (typeof detail === 'string') {
      return detail
    }
    if (error.response?.status === 500) {
      return 'Our AI assistant is temporarily unavailable. Please try again in a moment.'
    }
    if (error.response?.status === 400) {
      return 'That message could not be processed. Please try rephrasing your request.'
    }
  }

  return 'Something went wrong while contacting the AI assistant. Please try again.'
}

export async function sendChatMessage(payload: {
  message: string
  conversation_id?: string | null
  patient_id?: string | null
}): Promise<ChatMessageResponse> {
  const body: Record<string, string> = { message: payload.message }

  if (payload.conversation_id) {
    body.conversation_id = payload.conversation_id
  }
  if (payload.patient_id) {
    body.patient_id = payload.patient_id
  }

  const { data } = await chatApiClient.post<ChatMessageResponse>('/message', body)
  return data
}
