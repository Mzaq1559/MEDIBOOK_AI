import axios from 'axios'
import { chatApiClient } from './api'

export interface ChatOptionItem {
  option_id: string
  text: string
  doctor_id?: string | null
}

export interface ChatMessageResponse {
  conversation_id: string
  patient_id?: string | null
  timestamp: string
  bot_message: string
  next_action?: string | null
  options: ChatOptionItem[]
  conversation_history?: Array<{ role: string; message: string; timestamp: string }>
}

export interface ParsedDoctorOption {
  id: string
  name: string
  specialization: string
  clinic: string
  address: string
  fee: string
  avatarBg: string
  slots: string[]
}

export interface ParsedBookingSummary {
  doctor: ParsedDoctorOption
  selectedSlot: string
  isConfirmed: boolean
}

const AVATAR_BACKGROUNDS = [
  'bg-primary/10 text-primary',
  'bg-secondaryContainer/50 text-secondary',
  'bg-tertiary/10 text-tertiary',
]

export function isValidUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
}

export function avatarBgForName(name: string): string {
  const index = name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
  return AVATAR_BACKGROUNDS[index % AVATAR_BACKGROUNDS.length]
}

export function parseDoctorOptionsFromMessage(
  botMessage: string,
  options: ChatOptionItem[]
): ParsedDoctorOption[] {
  const doctors: ParsedDoctorOption[] = []

  for (const rawLine of botMessage.split('\n')) {
    const line = rawLine.trim()
    if (!/^\d+\./.test(line)) continue

    const content = line.replace(/^\d+\.\s*/, '')
    const parts = content.split(' — ')
    if (parts.length < 3) continue

    const nameSpec = parts[0]
    const clinic = parts[1].trim()
    const slotsStr = parts.slice(2).join(' — ')
    const nameMatch = nameSpec.match(/^(.+?)\s*\((.+)\)$/)
    const name = (nameMatch?.[1] ?? nameSpec).trim()
    const specialization = (nameMatch?.[2] ?? '').trim()
    const slots = slotsStr
      .split(',')
      .map((slot) => slot.trim())
      .filter(Boolean)

    const optionIndex = doctors.length
    const option = options[optionIndex]
    const doctorId = option?.doctor_id ?? option?.option_id ?? `doc-${optionIndex}`

    doctors.push({
      id: String(doctorId),
      name,
      specialization,
      clinic,
      address: '',
      fee: '',
      avatarBg: avatarBgForName(name),
      slots,
    })
  }

  return doctors
}

export function parseBookingSummary(botMessage: string): ParsedBookingSummary | null {
  const doctorMatch = botMessage.match(/Doctor:\s*(.+?)\s*\((.+?)\)/)
  const dateMatch = botMessage.match(/Date\/Time:\s*(.+)/)
  const clinicMatch = botMessage.match(/Clinic:\s*(.+)/)
  const addressMatch = botMessage.match(/Address:\s*(.+)/)
  const feeMatch = botMessage.match(/Consultation Fee:\s*(.+)/)

  if (!doctorMatch || !dateMatch) return null

  const name = doctorMatch[1].trim()

  return {
    doctor: {
      id: 'selected',
      name,
      specialization: doctorMatch[2].trim(),
      clinic: clinicMatch?.[1]?.trim() ?? '',
      address: addressMatch?.[1]?.trim() ?? '',
      fee: feeMatch?.[1]?.trim() ?? '',
      avatarBg: avatarBgForName(name),
      slots: [],
    },
    selectedSlot: dateMatch[1].trim(),
    isConfirmed: false,
  }
}

export function parseConfirmedBooking(botMessage: string): ParsedBookingSummary | null {
  const doctorMatch = botMessage.match(/Doctor:\s*(.+?)(?:\n|$)/)
  const dateMatch = botMessage.match(/Date\/Time:\s*(.+)/)
  const locationMatch = botMessage.match(/Location:\s*(.+)/)

  if (!doctorMatch) return null

  const name = doctorMatch[1].trim()

  return {
    doctor: {
      id: 'confirmed',
      name,
      specialization: '',
      clinic: locationMatch?.[1]?.trim() ?? '',
      address: '',
      fee: '',
      avatarBg: avatarBgForName(name),
      slots: [],
    },
    selectedSlot: dateMatch?.[1]?.trim() ?? '',
    isConfirmed: true,
  }
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
