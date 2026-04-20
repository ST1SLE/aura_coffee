import { clearRole } from '@/lib/auth';

const STORAGE_KEY = 'accessToken';

export function getAccessToken(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function setAccessToken(token: string): void {
  localStorage.setItem(STORAGE_KEY, token);
}

export function clearAccessToken(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function logout(): void {
  clearAccessToken();
  clearRole();
  // Полная навигация гарантирует сброс состояния React после очистки токена
  window.location.assign('/admin/login');
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';

export async function authenticatedFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = getAccessToken();

  const authHeaders: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};

  const merged: RequestInit = {
    ...init,
    headers: {
      ...authHeaders,
      ...(init.headers as Record<string, string> | undefined),
    },
  };

  const response = await fetch(`${BASE_URL}${path}`, merged);

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.clone().json();
    } catch {
      // тело не JSON — оставляем null
    }

    if (response.status === 401 && !path.endsWith('/staff/auth/login')) {
      clearAccessToken();
      const currentPath = window.location.pathname + window.location.search;
      const returnUrl = encodeURIComponent(
        currentPath.replace(/^\/admin/, '') || '/',
      );
      window.location.assign(`/admin/login?returnUrl=${returnUrl}`);
    }

    throw new ApiError(
      response.status,
      body,
      `HTTP ${response.status}: ${path}`,
    );
  }

  return response;
}

export async function staffLogin(
  login: string,
  password: string,
): Promise<{ access_token: string; role: string }> {
  const response = await fetch(`${BASE_URL}/api/v1/staff/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login, password }),
  });
  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.clone().json();
    } catch {
      // тело не JSON — оставляем null
    }
    throw new ApiError(
      response.status,
      body,
      `HTTP ${response.status}: /api/v1/staff/auth/login`,
    );
  }
  return response.json() as Promise<{ access_token: string; role: string }>;
}
