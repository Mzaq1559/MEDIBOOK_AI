import axios from 'axios';
import type { ApiErrorBody } from '../types/auth';

const AUTH_ERROR_MESSAGES: Record<string, string> = {
  EMAIL_DUPLICATE: 'An account with this email address already exists. Please sign in instead.',
  INVALID_EMAIL: 'Please enter a valid email address.',
  WEAK_PASSWORD:
    'Password must be at least 8 characters with 1 uppercase, 1 lowercase, 1 number, and 1 special character.',
  PHONE_DUPLICATE: 'This phone number is already registered to another account.',
  INVALID_CREDENTIALS: 'Invalid email or password. Please check your credentials and try again.',
  USER_NOT_FOUND: 'No account found with this email address. Please register first.',
  INVALID_REFRESH_TOKEN: 'Your session has expired. Please sign in again.',
  UNAUTHORIZED: 'Your session has expired. Please sign in again.',
  EXPIRED_TOKEN: 'Your session has expired. Please sign in again.',
  FORBIDDEN: 'Your account does not have permission to perform this action.',
  INVALID_INPUT: 'Please check your input and try again.',
  RATE_LIMIT_EXCEEDED: 'Too many attempts. Please wait a moment and try again.',
};

export function getAuthErrorMessage(errorCode?: string, fallback?: string): string {
  if (errorCode && AUTH_ERROR_MESSAGES[errorCode]) {
    return AUTH_ERROR_MESSAGES[errorCode];
  }
  return fallback || 'Something went wrong. Please try again.';
}

export function parseApiError(error: unknown): { message: string; errorCode?: string } {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as ApiErrorBody | undefined;
    const errorCode = data?.error_code;
    const serverMessage = data?.message;
    return {
      message: getAuthErrorMessage(errorCode, serverMessage || error.message),
      errorCode,
    };
  }

  if (error instanceof Error) {
    return { message: error.message };
  }

  return { message: 'Something went wrong. Please try again.' };
}
