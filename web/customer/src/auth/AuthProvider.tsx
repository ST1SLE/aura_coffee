import { createContext, useCallback, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import type { AuthUser } from '@/api/types';
import * as authApi from '@/api/auth';
import {
  setAccessToken,
  setRefreshToken,
  getRefreshToken,
  clearAllTokens,
} from './token';

export interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (phone: string) => Promise<void>;
  verifyCode: (phone: string, code: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

function parseUserFromJwt(token: string): AuthUser {
  try {
    const base64 = token.split('.')[1];
    const payload = JSON.parse(atob(base64));
    return { id: payload.sub, role: payload.role ?? 'customer' };
  } catch {
    return { id: 'unknown', role: 'customer' };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      setIsLoading(false);
      return;
    }

    authApi
      .refreshTokens(refreshToken)
      .then((tokens) => {
        setAccessToken(tokens.accessToken);
        setRefreshToken(tokens.refreshToken);
        setUser(parseUserFromJwt(tokens.accessToken));
      })
      .catch(() => {
        clearAllTokens();
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  const login = useCallback(async (phone: string) => {
    await authApi.sendCode(phone);
  }, []);

  const verifyCode = useCallback(async (phone: string, code: string) => {
    const result = await authApi.verifyCode(phone, code);
    setAccessToken(result.accessToken);
    setRefreshToken(result.refreshToken);
    setUser(result.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      clearAllTokens();
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isLoading,
        login,
        verifyCode,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
