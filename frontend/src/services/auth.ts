import { apiClient } from './api';
import type {
  AuthUser,
  LoginResponse,
  RegisterResponse,
  UserMeResponse,
  UserType,
} from '../types/auth';

export interface RegisterPayload {
  email: string;
  phone: string;
  name: string;
  password: string;
  user_type: UserType;
}

export interface LoginPayload {
  email: string;
  password: string;
}

function mapMeResponse(data: UserMeResponse): AuthUser {
  return {
    id: data.user_id,
    name: data.name,
    email: data.email,
    userType: data.user_type,
    avatarUrl: data.avatar_url ?? undefined,
  };
}

function mapAuthResponse(data: LoginResponse | RegisterResponse): AuthUser {
  return {
    id: data.user_id,
    name: data.name,
    email: data.email,
    userType: data.user_type,
  };
}

export async function registerUser(payload: RegisterPayload): Promise<{
  user: AuthUser;
  accessToken: string;
  refreshToken: string;
}> {
  const { data } = await apiClient.post<RegisterResponse>('/auth/register', payload);
  return {
    user: mapAuthResponse(data),
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
  };
}

export async function loginUser(payload: LoginPayload): Promise<{
  user: AuthUser;
  accessToken: string;
  refreshToken: string;
}> {
  const { data } = await apiClient.post<LoginResponse>('/auth/login', payload);
  return {
    user: mapAuthResponse(data),
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
  };
}

export async function logoutUser(): Promise<void> {
  await apiClient.post('/auth/logout');
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  const { data } = await apiClient.get<UserMeResponse>('/auth/me');
  return mapMeResponse(data);
}
