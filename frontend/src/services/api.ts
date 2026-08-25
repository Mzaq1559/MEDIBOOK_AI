import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import {
  getRefreshToken,
  setAccessToken,
  clearTokens,
} from './tokenStorage';

/** Relative base paths — Vite dev/preview proxy forwards these to backend & AI service. */
export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';
export const CHAT_API_BASE_URL = import.meta.env.VITE_CHAT_API_URL || '/chat';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

export const chatApiClient = axios.create({
  baseURL: CHAT_API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

const AUTH_SKIP_RETRY = ['/auth/login', '/auth/register', '/auth/refresh'];

let refreshPromise: Promise<string> | null = null;
let onSessionExpired: () => void = () => {};

export function configureAuthHandlers(handlers: { onSessionExpired: () => void }): void {
  onSessionExpired = handlers.onSessionExpired;
}

export function setAuthToken(token: string | null): void {
  const header = token ? `Bearer ${token}` : undefined;

  if (header) {
    apiClient.defaults.headers.common.Authorization = header;
    chatApiClient.defaults.headers.common.Authorization = header;
  } else {
    delete apiClient.defaults.headers.common.Authorization;
    delete chatApiClient.defaults.headers.common.Authorization;
  }
}

function shouldSkipAuthRetry(url?: string): boolean {
  if (!url) return false;
  return AUTH_SKIP_RETRY.some((path) => url.includes(path));
}

async function refreshAccessTokenDirect(refreshToken: string): Promise<string> {
  const { data } = await axios.post<{ access_token: string }>(
    `${API_BASE_URL}/auth/refresh`,
    { refresh_token: refreshToken },
    { headers: { 'Content-Type': 'application/json' } }
  );
  return data.access_token;
}

function attachResponseInterceptor(client: typeof apiClient): void {
  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

      if (
        error.response?.status !== 401 ||
        !originalRequest ||
        originalRequest._retry ||
        shouldSkipAuthRetry(originalRequest.url)
      ) {
        return Promise.reject(error);
      }

      const refreshToken = getRefreshToken();
      if (!refreshToken) {
        onSessionExpired();
        return Promise.reject(error);
      }

      originalRequest._retry = true;

      try {
        if (!refreshPromise) {
          refreshPromise = refreshAccessTokenDirect(refreshToken).finally(() => {
            refreshPromise = null;
          });
        }

        const newAccessToken = await refreshPromise;
        setAccessToken(newAccessToken);
        setAuthToken(newAccessToken);
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return client(originalRequest);
      } catch {
        clearTokens();
        setAuthToken(null);
        onSessionExpired();
        return Promise.reject(error);
      }
    }
  );
}

attachResponseInterceptor(apiClient);
attachResponseInterceptor(chatApiClient);
