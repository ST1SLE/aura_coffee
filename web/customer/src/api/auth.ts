import type { SendCodeResponse, VerifyCodeResponse, AuthTokens } from './types';
import { AuthError } from './types';
import { getAccessToken, getRefreshToken } from '@/auth/token';

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

export async function verifyCode(
  phone: string,
  code: string,
): Promise<VerifyCodeResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/verify-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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

export async function refreshTokens(
  refreshToken: string,
): Promise<AuthTokens> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
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

export async function logout(): Promise<void> {
  const accessToken = getAccessToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  try {
    await fetch(`${API_BASE}/logout`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ refresh_token: getRefreshToken() }),
    });
  } catch {
    // Игнорируем ошибки сети при logout — токены очистятся на клиенте
  }
}
