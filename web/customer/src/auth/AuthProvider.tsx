import { createContext, useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import type { AuthUser } from '@/api/types';
import * as authApi from '@/api/auth';
import {
  setAccessToken,
  clearAllTokens,
} from './token';
import { registerAuthFailureHandler } from '@/api/client';

// START_MODULE_CONTRACT
//   PURPOSE: React context provider for auth state — wires the OTP API client
//            to React state, attempts a silent refresh on mount, and registers
//            a global auth-failure handler so 401-after-refresh-fail also
//            clears the React user state. INV-002: client-side auth state is
//            UX only — the server validates every protected request.
//   SCOPE:   AuthContext (context object), AuthContextValue (interface),
//            AuthProvider (component).
//   DEPENDS: react, @/api/types (AuthUser), @/api/auth (sendCode/verifyCode/
//            refreshTokens/logout), ./token (in-memory access + legacy refresh
//            cleanup), @/api/client (registerAuthFailureHandler).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §6 OTP flow;
//            INV-002 (client-side role check is UX, server enforces).
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   AuthContextValue   - shape of the context (user, isAuthenticated, login, …)
//   AuthContext        - React context object (consumed via useAuth hook)
//   AuthProvider       - top-level provider that owns user state and refresh logic
// END_MODULE_MAP

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

// START_CONTRACT: AuthProvider
//   PURPOSE: Top-level auth context provider. On mount tries one silent refresh
//            using the HttpOnly refresh cookie; exposes login/verifyCode/
//            logout actions that talk to api/auth and update both token storage
//            and React state.
//   INPUTS:  { children: ReactNode } — subtree to render.
//   OUTPUTS: JSX — AuthContext.Provider wrapping children with the live value.
//   SIDE_EFFECTS: registers auth-failure handler on api/client; reads/writes
//                 access (in-memory) and legacy refresh localStorage cleanup; HTTP
//                 calls via api/auth (sendCode, verifyCode, refreshTokens,
//                 logout); decodes JWT client-side for AuthUser hydration
//                 (INV-002 — server is the authority).
//   LINKS:   PDD §6 OTP state machine; consumed by App.tsx.
// END_CONTRACT: AuthProvider
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    registerAuthFailureHandler(() => {
      clearAllTokens();
      setUser(null);
    });
  }, []);

  const refreshAttempted = useRef(false);

  useEffect(() => {
    if (refreshAttempted.current) return;
    refreshAttempted.current = true;

    authApi
      .refreshTokens()
      .then((tokens) => {
        setAccessToken(tokens.accessToken);
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
