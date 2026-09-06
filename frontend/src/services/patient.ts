import { apiClient } from './api';

export interface PatientProfile {
  patient_id: string;
  user_id: string;
  name: string;
  email: string;
  phone?: string | null;
  date_of_birth?: string | null;
  age?: number | null;
  gender?: string | null;
  blood_type?: string | null;
  allergies: string[];
  medical_conditions: string[];
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  emergency_contact_relation?: string | null;
  preferred_notification: string;
  profile_completed: boolean;
  total_appointments: number;
  total_no_shows: number;
  created_at: string;
}

export interface PatientProfileUpdatePayload {
  date_of_birth?: string | null;
  gender?: string | null;
  blood_type?: string | null;
  allergies?: string[];
  medical_conditions?: string[];
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  emergency_contact_relation?: string | null;
  preferred_notification?: string | null;
}

/** Fetch the authenticated patient's own medical profile. */
export async function getMyPatientProfile(): Promise<PatientProfile> {
  const { data } = await apiClient.get<PatientProfile>('/patients/me');
  return data;
}

/** Update the authenticated patient's own medical profile. */
export async function updateMyPatientProfile(
  payload: PatientProfileUpdatePayload
): Promise<PatientProfile> {
  const { data } = await apiClient.put<PatientProfile>('/patients/me', payload);
  return data;
}

/** Fetch a patient profile by patient_id (for doctor/admin views). */
export async function getPatientProfile(patientId: string): Promise<PatientProfile> {
  const { data } = await apiClient.get<PatientProfile>(`/patients/${patientId}`);
  return data;
}
