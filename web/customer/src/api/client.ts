import {
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
  clearAllTokens,
} from '@/auth/token';
import { refreshTokens } from './auth';

let onAuthFailure: (() => void) | null = null;

export function registerAuthFailureHandler(handler: () => void): void {
  onAuthFailure = handler;
}

let refreshPromise: Promise<string> | null = null;

function doRefresh(): Promise<string> {
  if (refreshPromise) return refreshPromise;

  const rt = getRefreshToken();
  if (!rt) {
    return Promise.reject(new Error('No refresh token'));
  }

  refreshPromise = refreshTokens(rt)
    .then((tokens) => {
      setAccessToken(tokens.accessToken);
      setRefreshToken(tokens.refreshToken);
      return tokens.accessToken;
    })
    .finally(() => {
      refreshPromise = null;
    });

  return refreshPromise;
}

function handleAuthFailure(): void {
  clearAllTokens();
  if (onAuthFailure) {
    onAuthFailure();
  }
}

/**
 * Выполняет аутентифицированный запрос и десериализует JSON.
 * Бросает Error с HTTP-статусом при ответах не 2xx.
 */
export async function apiRequest<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await authenticatedFetch(url, opts);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${url}`);
  }
  return res.json() as Promise<T>;
}

export async function authenticatedFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const accessToken = getAccessToken();
  const headers = new Headers(init?.headers);
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  const res = await fetch(input, { ...init, headers });

  if (res.status !== 401) return res;

  // Попытка обновить токен и повторить запрос
  let newToken: string;
  try {
    newToken = await doRefresh();
  } catch {
    handleAuthFailure();
    return res;
  }

  headers.set('Authorization', `Bearer ${newToken}`);
  return fetch(input, { ...init, headers });
}
