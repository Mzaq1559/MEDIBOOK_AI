export type UserType = 'patient' | 'doctor' | 'receptionist' | 'admin';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  userType: UserType;
  phone?: string;
  avatarUrl?: string;
  /** patients.id — the FK stored in appointments.patient_id (differs from users.id) */
  patientId?: string;
  /** doctors.id — the FK stored in appointments.doctor_id (differs from users.id) */
  doctorId?: string;
  /** Whether the user's account has been verified (false for pending doctor applications) */
  isVerified?: boolean;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

export interface LoginResponse {
  user_id: string;
  email: string;
  name: string;
  user_type: UserType;
  access_token: string;
  refresh_token: string;
  expires_in: number;
  /** patients.id returned by /auth/login for patient users */
  patient_id?: string | null;
  patientId?: string | null;
  doctor_id?: string | null;
  is_verified?: boolean | null;
}

export interface RegisterResponse extends LoginResponse {
  message: string;
}

export interface UserMeResponse {
  user_id: string;
  email: string;
  name: string;
  user_type: UserType;
  avatar_url?: string | null;
  is_active: boolean;
  is_verified?: boolean | null;
  created_at: string;
  patient_id?: string | null;
  doctor_id?: string | null;
}

export interface ApiErrorBody {
  error?: boolean;
  message?: string;
  error_code?: string;
  status_code?: number;
}
