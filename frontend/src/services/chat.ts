import axios from 'axios'
import { chatApiClient, CHAT_API_BASE_URL } from './api'
import { getAccessToken } from './tokenStorage'

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
  urgency_level?: string | null
  urgency_reason?: string | null
}

export type ProposalStatus = 'pending' | 'executed' | 'expired' | 'failed'

export interface ParsedBookingSummary {
  doctor: ParsedDoctorOption
  selectedSlot: string
  /** @deprecated Use `status` instead */
  isConfirmed: boolean
  proposal_id?: string | null
  status?: ProposalStatus | null
}

export interface ParsedRescheduleSummary {
  doctor: ParsedDoctorOption
  oldSlot: string
  newSlot: string
  proposal_id?: string | null
  status?: ProposalStatus | null
}

export interface TriageSource {
  id: string
  title: string
  type: string
}

export interface TriageUiData {
  specialty?: string | null
  urgency?: string
  urgency_reason?: string | null
  confidence?: string
  rag_used?: boolean
  rag_status?: string
  fallback_used?: boolean
  sources?: TriageSource[]
}

export interface ChatUiData {
  doctors?: ParsedDoctorOption[]
  slots?: ParsedSlot[]
  appointments?: ParsedAppointment[]
  booking?: ParsedBookingSummary
  reschedule?: ParsedRescheduleSummary
  triage?: TriageUiData
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

export interface SendChatMessageStreamOptions {
  message: string
  conversation_id?: string | null
  patient_id?: string | null
  onStatus?: (label: string) => void
}

export async function sendChatMessageStream(
  options: SendChatMessageStreamOptions
): Promise<ChatMessageResponse> {
  const body: Record<string, any> = {
    message: options.message,
    stream: true,
  }

  if (options.conversation_id) {
    body.conversation_id = options.conversation_id
  }
  if (options.patient_id) {
    body.patient_id = options.patient_id
  }

  const token = getAccessToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${CHAT_API_BASE_URL}/message`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    let errorMsg = 'Something went wrong while contacting the AI assistant.'
    try {
      const errorJson = await response.json()
      if (errorJson.detail?.message) errorMsg = errorJson.detail.message
      else if (typeof errorJson.detail === 'string') errorMsg = errorJson.detail
    } catch {
      // ignore json parse error
    }
    throw new Error(errorMsg)
  }

  if (!response.body) {
    throw new Error('No response body received from chat service.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let finalResponse: ChatMessageResponse | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''

    for (const block of blocks) {
      if (!block.trim()) continue
      const lines = block.split('\n')
      let eventType = ''
      let dataStr = ''

      for (const line of lines) {
        if (line.startsWith('event:')) {
          eventType = line.replace(/^event:\s*/, '').trim()
        } else if (line.startsWith('data:')) {
          dataStr = line.replace(/^data:\s*/, '').trim()
        }
      }

      if (!dataStr) continue

      try {
        const parsed = JSON.parse(dataStr)
        if (eventType === 'status') {
          if (parsed.label && options.onStatus) {
            options.onStatus(parsed.label)
          }
        } else if (eventType === 'final') {
          finalResponse = parsed as ChatMessageResponse
        } else if (eventType === 'error') {
          throw new Error(parsed.message || 'Error from AI assistant.')
        }
      } catch (err: any) {
        if (eventType === 'error' || (err.message && err.message.includes('Error from AI assistant'))) {
          throw err
        }
        console.warn('Failed to parse SSE event chunk:', block, err)
      }
    }
  }

  if (buffer.trim()) {
    const lines = buffer.split('\n')
    let eventType = ''
    let dataStr = ''
    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventType = line.replace(/^event:\s*/, '').trim()
      } else if (line.startsWith('data:')) {
        dataStr = line.replace(/^data:\s*/, '').trim()
      }
    }
    if (dataStr) {
      try {
        const parsed = JSON.parse(dataStr)
        if (eventType === 'final') {
          finalResponse = parsed as ChatMessageResponse
        } else if (eventType === 'error') {
          throw new Error(parsed.message || 'Error from AI assistant.')
        }
      } catch (err: any) {
        if (eventType === 'error') throw err
      }
    }
  }

  if (!finalResponse) {
    throw new Error('Failed to receive completed message from AI assistant.')
  }

  return finalResponse
}

