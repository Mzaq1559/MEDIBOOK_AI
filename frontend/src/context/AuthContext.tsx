import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { AuthUser } from '../types/auth';
import {
  loginUser,
  logoutUser,
  registerUser,
  fetchCurrentUser,
  type RegisterPayload,
} from '../services/auth';
import {
  configureAuthHandlers,
  setAuthToken,
} from '../services/api';
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setTokens,
} from '../services/tokenStorage';
import axios from 'axios';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  currentUser: AuthUser | null;
  login: (email: string, password: string) => Promise<AuthUser>;
  register: (payload: RegisterPayload) => Promise<AuthUser>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

async function refreshAccessTokenDirect(refreshToken: string): Promise<string> {
  const baseUrl = import.meta.env.VITE_API_URL || '/api';
  const { data } = await axios.post<{ access_token: string }>(
    `${baseUrl}/auth/refresh`,
    { refresh_token: refreshToken },
    { headers: { 'Content-Type': 'application/json' } }
  );
  return data.access_token;
}

function applySession(user: AuthUser, accessToken: string, refreshToken: string): void {
  setTokens(accessToken, refreshToken);
  setAuthToken(accessToken);
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const clearSession = useCallback(() => {
    clearTokens();
    setAuthToken(null);
    setCurrentUser(null);
  }, []);

  const establishSession = useCallback(
    (user: AuthUser, accessToken: string, refreshToken: string) => {
      applySession(user, accessToken, refreshToken);
      setCurrentUser(user);
    },
    []
  );

  useEffect(() => {
    configureAuthHandlers({
      onSessionExpired: () => {
        clearSession();
        if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
          window.location.replace('/login');
        }
      },
    });
  }, [clearSession]);

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const accessToken = getAccessToken();
      const refreshToken = getRefreshToken();

      if (!accessToken && !refreshToken) {
        if (!cancelled) setIsLoading(false);
        return;
      }

      try {
        if (accessToken) {
          setAuthToken(accessToken);
          const user = await fetchCurrentUser();
          if (!cancelled) {
            setCurrentUser(user);
          }
        } else if (refreshToken) {
          const newAccessToken = await refreshAccessTokenDirect(refreshToken);
          setAccessToken(newAccessToken);
          setAuthToken(newAccessToken);
          const user = await fetchCurrentUser();
          if (!cancelled) {
            setCurrentUser(user);
          }
        }
      } catch {
        if (refreshToken) {
          try {
            const newAccessToken = await refreshAccessTokenDirect(refreshToken);
            setAccessToken(newAccessToken);
            setAuthToken(newAccessToken);
            const user = await fetchCurrentUser();
            if (!cancelled) {
              setCurrentUser(user);
            }
          } catch {
            if (!cancelled) clearSession();
          }
        } else if (!cancelled) {
          clearSession();
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    restoreSession();
    return () => {
      cancelled = true;
    };
  }, [clearSession]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { user, accessToken, refreshToken } = await loginUser({ email, password });
      establishSession(user, accessToken, refreshToken);
      return user;
    },
    [establishSession]
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      const { user, accessToken, refreshToken } = await registerUser(payload);
      establishSession(user, accessToken, refreshToken);
      return user;
    },
    [establishSession]
  );

  const logout = useCallback(async () => {
    try {
      await logoutUser();
    } catch {
      // Best-effort server logout; always clear client session.
    } finally {
      clearSession();
    }
  }, [clearSession]);

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: currentUser !== null,
        isLoading,
        currentUser,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
