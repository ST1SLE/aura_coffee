import { clearRole } from '@/lib/auth';

// START_MODULE_CONTRACT
//   PURPOSE: Thin HTTP client wrapper for the staff SPA — manages access token
//            in localStorage, attaches Bearer auth header, and centralizes
//            401 redirect to /admin/login plus typed error wrapping.
//   SCOPE:   All admin/barista/courier API calls go through authenticatedFetch;
//            staffLogin is the only unauthenticated endpoint here.
//   DEPENDS: @/lib/auth (clearRole), browser fetch + localStorage + window.location.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §4.5.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   getAccessToken      - read access token from localStorage
//   setAccessToken      - persist access token to localStorage
//   clearAccessToken    - remove access token from localStorage
//   logout              - clear token + role and hard-navigate to /admin/login
//   ApiError            - error class wrapping HTTP status + parsed body
//   authenticatedFetch  - fetch wrapper that injects Bearer token + handles 401
//   staffLogin          - POST /api/v1/staff/auth/login (unauthenticated)
// END_MODULE_MAP

const STORAGE_KEY = 'accessToken';

// START_CONTRACT: getAccessToken
//   PURPOSE: Read access token previously persisted by login flow.
//   INPUTS:  none
//   OUTPUTS: string | null — token or null if absent.
//   SIDE_EFFECTS: reads localStorage.
// END_CONTRACT: getAccessToken
export function getAccessToken(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

// START_CONTRACT: setAccessToken
//   PURPOSE: Persist access token returned from staffLogin.
//   INPUTS:  token: string — JWT access token from /staff/auth/login
//   OUTPUTS: void
//   SIDE_EFFECTS: writes localStorage.
// END_CONTRACT: setAccessToken
export function setAccessToken(token: string): void {
  localStorage.setItem(STORAGE_KEY, token);
}

// START_CONTRACT: clearAccessToken
//   PURPOSE: Remove access token from localStorage (used on 401 and logout).
//   INPUTS:  none
//   OUTPUTS: void
//   SIDE_EFFECTS: writes localStorage.
// END_CONTRACT: clearAccessToken
export function clearAccessToken(): void {
  localStorage.removeItem(STORAGE_KEY);
}

// START_CONTRACT: logout
//   PURPOSE: Clear token + role hint and navigate to /admin/login (full page
//            reload to drop any in-memory React state).
//   INPUTS:  none
//   OUTPUTS: void
//   SIDE_EFFECTS: localStorage writes; window.location.assign navigation.
//   LINKS:   INV-002 (server enforces auth; client cleanup is UX).
// END_CONTRACT: logout
export function logout(): void {
  clearAccessToken();
  clearRole();
  // Полная навигация гарантирует сброс состояния React после очистки токена
  window.location.assign('/admin/login');
}

// START_CONTRACT: ApiError
//   PURPOSE: Strongly-typed error thrown by authenticatedFetch/staffLogin when
//            an HTTP response is not ok; preserves status code and parsed body
//            so callers can branch on 401/403/404/409/422.
//   INPUTS:  status: number, body: unknown (parsed JSON or null), message: string
//   OUTPUTS: Error subclass instance.
//   SIDE_EFFECTS: none on construction.
//   LINKS:   PDD error-handling, INV-002 (status 401/403 distinguish unauth vs role).
// END_CONTRACT: ApiError
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

// START_CONTRACT: authenticatedFetch
//   PURPOSE: fetch wrapper that injects Bearer token and centralizes 401
//            handling — clears the token and hard-redirects to /admin/login
//            with returnUrl, preserving deep-link UX after re-auth.
//   INPUTS:  path: string — absolute API path (e.g. "/api/v1/admin/orders")
//            init: RequestInit — optional fetch init; auth headers merged in.
//   OUTPUTS: Promise<Response> — non-OK responses throw ApiError instead.
//   SIDE_EFFECTS: network request; localStorage clear + window.location.assign on 401.
//   LINKS:   INV-002 (server enforces auth; this client treats 401 as session expired);
//            api/client.ts is the only path through which staff API requests should flow.
// END_CONTRACT: authenticatedFetch
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

// START_CONTRACT: staffLogin
//   PURPOSE: Authenticate staff credentials against the core-api login endpoint
//            (separate from customer SMS-OTP flow) and return access_token + role.
//   INPUTS:  login: string, password: string
//   OUTPUTS: Promise<{access_token, role}> — token to be persisted by caller;
//            role is the canonical server-issued role string (admin/barista/courier).
//   SIDE_EFFECTS: unauthenticated POST; throws ApiError on non-2xx (401 means bad creds).
//   LINKS:   INV-002 (server is source of truth for role); LoginPage stores both
//            token and role into localStorage for client-side route gating.
// END_CONTRACT: staffLogin
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
