import { clearRole, setRole } from '@/lib/auth';

// START_MODULE_CONTRACT
//   PURPOSE: Thin HTTP client wrapper for the staff SPA — manages staff JWT
//            access/refresh tokens in localStorage, attaches Bearer auth,
//            rotates refresh tokens on 401, revokes refresh on logout, and
//            centralizes typed error wrapping.
//   SCOPE:   All admin/barista/courier API calls go through authenticatedFetch;
//            staffLogin/staffRefresh/logout are the auth surfaces here.
//   DEPENDS: @/lib/auth (clearRole, setRole), browser fetch + localStorage
//            + window.location.
//   LINKS:   docs/development-plan.xml M-WEB-ADMIN, PDD §4.5, PDD §6.5,
//            INV-002, INV-010.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   getAccessToken      - read access token from localStorage
//   setAccessToken      - persist access token to localStorage
//   getRefreshToken     - read refresh token from localStorage
//   setRefreshToken     - persist refresh token to localStorage
//   clearAuthTokens     - remove both staff tokens
//   clearAccessToken    - remove access token from localStorage
//   logout              - revoke refresh token, clear token + role, navigate login
//   ApiError            - error class wrapping HTTP status + parsed body
//   authenticatedFetch  - fetch wrapper that injects Bearer token + refreshes on 401
//   staffLogin          - POST /api/v1/staff/auth/login (unauthenticated)
// END_MODULE_MAP

const ACCESS_STORAGE_KEY = 'accessToken';
const REFRESH_STORAGE_KEY = 'refreshToken';

// START_CONTRACT: StaffAuthTokens
//   PURPOSE: Typed token pair and role returned by staff login/refresh endpoints.
//   INPUTS:  access_token: string — short-lived staff JWT access token
//            refresh_token: string — rotating staff refresh token
//            role: string — canonical staff role from core-api
//   OUTPUTS: TypeScript interface.
//   SIDE_EFFECTS: none.
//   LINKS:   PDD §4.5, INV-002.
// END_CONTRACT: StaffAuthTokens
export interface StaffAuthTokens {
  access_token: string;
  refresh_token: string;
  role: string;
}

// START_CONTRACT: getAccessToken
//   PURPOSE: Read access token previously persisted by login flow.
//   INPUTS:  none
//   OUTPUTS: string | null — token or null if absent.
//   SIDE_EFFECTS: reads localStorage.
// END_CONTRACT: getAccessToken
export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_STORAGE_KEY);
}

// START_CONTRACT: setAccessToken
//   PURPOSE: Persist access token returned from staffLogin.
//   INPUTS:  token: string — JWT access token from /staff/auth/login
//   OUTPUTS: void
//   SIDE_EFFECTS: writes localStorage.
// END_CONTRACT: setAccessToken
export function setAccessToken(token: string): void {
  localStorage.setItem(ACCESS_STORAGE_KEY, token);
}

// START_CONTRACT: getRefreshToken
//   PURPOSE: Read the staff refresh token persisted after login/refresh.
//   INPUTS:  none
//   OUTPUTS: string | null — token or null if absent.
//   SIDE_EFFECTS: reads localStorage.
// END_CONTRACT: getRefreshToken
export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_STORAGE_KEY);
}

// START_CONTRACT: setRefreshToken
//   PURPOSE: Persist refresh token returned by /staff/auth/login or /refresh.
//   INPUTS:  token: string
//   OUTPUTS: void
//   SIDE_EFFECTS: writes localStorage.
// END_CONTRACT: setRefreshToken
export function setRefreshToken(token: string): void {
  localStorage.setItem(REFRESH_STORAGE_KEY, token);
}

// START_CONTRACT: clearAccessToken
//   PURPOSE: Remove access token from localStorage (used on 401 and logout).
//   INPUTS:  none
//   OUTPUTS: void
//   SIDE_EFFECTS: writes localStorage.
// END_CONTRACT: clearAccessToken
export function clearAccessToken(): void {
  localStorage.removeItem(ACCESS_STORAGE_KEY);
}

// START_CONTRACT: clearAuthTokens
//   PURPOSE: Remove both staff JWT tokens from localStorage.
//   INPUTS:  none
//   OUTPUTS: void
//   SIDE_EFFECTS: writes localStorage.
// END_CONTRACT: clearAuthTokens
export function clearAuthTokens(): void {
  clearAccessToken();
  localStorage.removeItem(REFRESH_STORAGE_KEY);
}

function persistStaffAuth(result: StaffAuthTokens): void {
  setAccessToken(result.access_token);
  setRefreshToken(result.refresh_token);
  setRole(result.role as Parameters<typeof setRole>[0]);
}

// START_CONTRACT: logout
//   PURPOSE: Revoke the staff refresh token when present, then clear local token
//            + role hint and navigate to /admin/login (full page reload to drop
//            any in-memory React state). Local cleanup happens even if the
//            network revoke fails.
//   INPUTS:  none
//   OUTPUTS: Promise<void>
//   SIDE_EFFECTS: POST /staff/auth/logout when tokens exist; localStorage writes;
//                 window.location.assign navigation.
//   LINKS:   INV-002 (server enforces auth; client cleanup is UX).
// END_CONTRACT: logout
export async function logout(): Promise<void> {
  const refreshToken = getRefreshToken();
  const accessToken = getAccessToken();

  try {
    if (refreshToken) {
      const tokenPair = accessToken
        ? { access_token: accessToken, refresh_token: refreshToken }
        : await refreshStaffSession();

      if (tokenPair) {
        const response = await revokeStaffRefresh(
          tokenPair.access_token,
          tokenPair.refresh_token,
        );

        if (response.status === 401) {
          const refreshed = await refreshStaffSession();
          if (refreshed !== null) {
            await revokeStaffRefresh(
              refreshed.access_token,
              refreshed.refresh_token,
            );
          }
        }
      }
    }
  } catch {
    // Local logout must proceed even if refresh revocation cannot reach backend.
  } finally {
    clearAuthTokens();
    clearRole();
    // Полная навигация гарантирует сброс состояния React после очистки токена
    window.location.assign('/admin/login');
  }
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

const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';

async function parseErrorResponse(response: Response): Promise<unknown> {
  try {
    return await response.clone().json();
  } catch {
    return null;
  }
}

function redirectToLogin(): void {
  clearAuthTokens();
  clearRole();
  const currentPath = window.location.pathname + window.location.search;
  const returnUrl = encodeURIComponent(
    currentPath.replace(/^\/admin/, '') || '/',
  );
  window.location.assign(`/admin/login?returnUrl=${returnUrl}`);
}

async function revokeStaffRefresh(
  accessToken: string,
  refreshToken: string,
): Promise<Response> {
  return fetch(`${BASE_URL}/api/v1/staff/auth/logout`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

async function refreshStaffSession(): Promise<StaffAuthTokens | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  const response = await fetch(`${BASE_URL}/api/v1/staff/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) return null;

  const result = (await response.json()) as StaffAuthTokens;
  persistStaffAuth(result);
  return result;
}

function mergeAuthHeaders(
  init: RequestInit,
  token: string | null,
): RequestInit {
  const authHeaders: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};

  return {
    ...init,
    headers: {
      ...authHeaders,
      ...(init.headers as Record<string, string> | undefined),
    },
  };
}

// START_CONTRACT: authenticatedFetch
//   PURPOSE: fetch wrapper that injects Bearer token and centralizes 401
//            handling — first tries refresh-token rotation, retries the original
//            request once with the new access token, and only then clears state
//            and redirects to /admin/login with returnUrl.
//   INPUTS:  path: string — absolute API path (e.g. "/api/v1/admin/orders")
//            init: RequestInit — optional fetch init; auth headers merged in.
//   OUTPUTS: Promise<Response> — non-OK responses throw ApiError instead.
//   SIDE_EFFECTS: network request; may POST /staff/auth/refresh, write rotated
//                 tokens/role, or clear local state + redirect on failed refresh.
//   LINKS:   INV-002 (server enforces auth; client refresh is UX continuity);
//            api/client.ts is the only path through which staff API requests should flow.
// END_CONTRACT: authenticatedFetch
export async function authenticatedFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = getAccessToken();
  const merged = mergeAuthHeaders(init, token);

  const response = await fetch(`${BASE_URL}${path}`, merged);

  if (!response.ok) {
    if (
      response.status === 401 &&
      !path.endsWith('/staff/auth/login') &&
      !path.endsWith('/staff/auth/refresh')
    ) {
      let refreshed: StaffAuthTokens | null = null;
      try {
        refreshed = await refreshStaffSession();
      } catch {
        refreshed = null;
      }
      if (refreshed !== null) {
        const retryResponse = await fetch(
          `${BASE_URL}${path}`,
          mergeAuthHeaders(init, refreshed.access_token),
        );
        if (retryResponse.ok) return retryResponse;
        const retryBody = await parseErrorResponse(retryResponse);
        if (retryResponse.status === 401) {
          redirectToLogin();
        }
        throw new ApiError(
          retryResponse.status,
          retryBody,
          `HTTP ${retryResponse.status}: ${path}`,
        );
      }
      redirectToLogin();
    }

    const body = await parseErrorResponse(response);
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
//            (separate from customer SMS-OTP flow) and return rotated staff tokens + role.
//   INPUTS:  login: string, password: string
//   OUTPUTS: Promise<StaffAuthTokens> — access/refresh tokens and canonical role.
//   SIDE_EFFECTS: unauthenticated POST; throws ApiError on non-2xx (401 means bad creds).
//   LINKS:   INV-002 (server is source of truth for role); LoginPage stores both
//            token and role into localStorage for client-side route gating.
// END_CONTRACT: staffLogin
export async function staffLogin(
  login: string,
  password: string,
): Promise<StaffAuthTokens> {
  const response = await fetch(`${BASE_URL}/api/v1/staff/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login, password }),
  });
  if (!response.ok) {
    const body = await parseErrorResponse(response);
    throw new ApiError(
      response.status,
      body,
      `HTTP ${response.status}: /api/v1/staff/auth/login`,
    );
  }
  return response.json() as Promise<StaffAuthTokens>;
}
