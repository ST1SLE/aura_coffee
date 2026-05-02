import type { SendCodeResponse, VerifyCodeResponse, AuthTokens } from './types';
import { AuthError } from './types';
import { getAccessToken, setAccessToken } from '@/auth/token';

// START_MODULE_CONTRACT
//   PURPOSE: Customer-facing OTP auth API client — talks to /api/v1/auth/*
//            (send-code, verify-code, refresh, logout) and normalises HTTP
//            errors into typed AuthError codes for the UI.
//   SCOPE:   sendCode, verifyCode, refreshTokens, logout. Re-exports AuthError
//            and the auth DTO types so consumers import a single module.
//   DEPENDS: M-CORE-API (HTTP /api/v1/auth/*), ./types (AuthError, DTOs),
//            @/auth/token (in-memory access token for logout auth header).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §6 OTP state machine.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   sendCode       - POST /auth/send-code, returns confirmation message
//   verifyCode     - POST /auth/verify-code, returns tokens + parsed AuthUser
//   refreshTokens  - POST /auth/refresh using HttpOnly refresh cookie
//   logout         - POST /auth/logout using HttpOnly refresh cookie
//   AuthError      - re-export of ./types AuthError
// END_MODULE_MAP

export { AuthError } from './types';
export type {
  AuthTokens,
  AuthUser,
  SendCodeResponse,
  VerifyCodeResponse,
  AuthErrorCode,
} from './types';

const API_BASE = '/api/v1/auth';

function parseJwtPayload(token: string): { sub: string; role: string } {
  const base64 = token.split('.')[1];
  const json = atob(base64);
  return JSON.parse(json);
}

async function handleErrorResponse(res: Response): Promise<never> {
  const body = await res.json().catch(() => ({ detail: 'Unknown error' }));

  if (res.status === 429) {
    throw new AuthError('RATE_LIMITED', body.detail, body.retry_after);
  }
  if (res.status === 409) {
    throw new AuthError('CODE_NOT_DELIVERED', body.detail);
  }
  if (res.status === 410) {
    throw new AuthError('CODE_EXPIRED', body.detail);
  }
  if (res.status === 401) {
    const detail: string = body.detail ?? '';
    if (detail.includes('Wrong code') || detail.includes('Too many failed')) {
      throw new AuthError('INVALID_CODE', detail);
    }
    throw new AuthError('UNKNOWN_ERROR', detail);
  }
  throw new AuthError('UNKNOWN_ERROR', body.detail ?? `HTTP ${res.status}`);
}

// START_CONTRACT: sendCode
//   PURPOSE: Request the server to send an OTP SMS to the given phone number.
//   INPUTS:  phone: string — E.164 form (e.g. '+79991234567'). INV-013 — server
//            stores hashed phone; client passes plain to API only.
//   OUTPUTS: Promise<SendCodeResponse> — { message }.
//   SIDE_EFFECTS: HTTP POST /api/v1/auth/send-code; may throw AuthError for
//                 RATE_LIMITED (429), CODE_NOT_DELIVERED (409), NETWORK_ERROR.
//   LINKS:   PDD §6.1 send-code state.
// END_CONTRACT: sendCode
export async function sendCode(phone: string): Promise<SendCodeResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/send-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone }),
    });
  } catch {
    throw new AuthError('NETWORK_ERROR', 'Network error');
  }

  if (!res.ok) await handleErrorResponse(res);
  return res.json();
}

// START_CONTRACT: verifyCode
//   PURPOSE: Submit OTP code, receive access/refresh tokens and parsed user.
//   INPUTS:  phone: string — same E.164 phone used in sendCode (INV-013)
//            code: string  — 6-digit OTP from SMS
//   OUTPUTS: Promise<VerifyCodeResponse> — access token, optional legacy
//            refreshToken field, and parsed user.
//   SIDE_EFFECTS: HTTP POST /api/v1/auth/verify-code; throws AuthError for
//                 INVALID_CODE (401), CODE_EXPIRED (410), CODE_NOT_DELIVERED (409),
//                 RATE_LIMITED (429), NETWORK_ERROR. Server also sets an
//                 HttpOnly SameSite refresh cookie. Decodes the JWT payload
//                 client-side to extract user.id/role (INV-002 — server is
//                 authoritative; this is convenience only).
//   LINKS:   PDD §6.2 verify-code state.
// END_CONTRACT: verifyCode
export async function verifyCode(
  phone: string,
  code: string,
): Promise<VerifyCodeResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/verify-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ phone, code }),
    });
  } catch {
    throw new AuthError('NETWORK_ERROR', 'Network error');
  }

  if (!res.ok) await handleErrorResponse(res);

  const data = await res.json();
  const payload = parseJwtPayload(data.access_token);

  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    user: { id: payload.sub, role: payload.role as 'customer' },
  };
}

// START_CONTRACT: refreshTokens
//   PURPOSE: Exchange the HttpOnly refresh cookie for a fresh access token and
//            rotated refresh cookie; optional argument is a legacy fallback for
//            non-browser callers.
//   INPUTS:  refreshToken?: string — optional legacy refresh token fallback.
//   OUTPUTS: Promise<AuthTokens> — new accessToken + legacy refreshToken field.
//   SIDE_EFFECTS: HTTP POST /api/v1/auth/refresh with credentials; throws
//                 AuthError on non-2xx (NETWORK_ERROR for fetch failure,
//                 UNKNOWN_ERROR for 4xx/5xx).
//   LINKS:   PDD §6 token refresh; called both by api/client.ts (single-flight
//            on 401) and AuthProvider mount-time silent refresh.
// END_CONTRACT: refreshTokens
export async function refreshTokens(
  refreshToken?: string | null,
): Promise<AuthTokens> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(
        refreshToken ? { refresh_token: refreshToken } : {},
      ),
    });
  } catch {
    throw new AuthError('NETWORK_ERROR', 'Network error');
  }

  if (!res.ok) await handleErrorResponse(res);

  const data = await res.json();
  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
  };
}

// START_CONTRACT: logout
//   PURPOSE: Tell the server to invalidate the current refresh cookie. Best-effort:
//            network errors are swallowed because the client also clears its
//            local state regardless (see AuthProvider.logout).
//   INPUTS:  none (reads access token from @/auth/token).
//   OUTPUTS: Promise<void> — always resolves.
//   SIDE_EFFECTS: HTTP POST /api/v1/auth/logout (best-effort); if access is
//                 expired, may POST /api/v1/auth/refresh once and retry logout.
//                 Never throws.
//   LINKS:   PDD §6 sign-out.
// END_CONTRACT: logout
export async function logout(): Promise<void> {
  let accessToken = getAccessToken();

  async function revokeCurrentCookie(token: string | null): Promise<Response> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return fetch(`${API_BASE}/logout`, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify({}),
    });
  }

  try {
    const first = await revokeCurrentCookie(accessToken);
    if (first.status !== 401) {
      return;
    }

    const tokens = await refreshTokens();
    accessToken = tokens.accessToken;
    setAccessToken(accessToken);
    await revokeCurrentCookie(accessToken);
  } catch {
    // Игнорируем ошибки сети при logout — токены очистятся на клиенте
  }
}
