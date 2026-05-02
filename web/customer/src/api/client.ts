import {
  getAccessToken,
  setAccessToken,
  clearAllTokens,
} from '@/auth/token';
import { refreshTokens } from './auth';

// START_MODULE_CONTRACT
//   PURPOSE: Authenticated fetch wrapper for core-api with single-flight refresh
//            on 401 and a registerable global auth-failure callback (used by
//            AuthProvider to clear React state when refresh fails).
//   SCOPE:   apiRequest<T>, authenticatedFetch, ApiError class, and the
//            registerAuthFailureHandler hook. All other M-WEB-CUSTOMER API
//            modules call through here so token refresh logic stays in one place.
//   DEPENDS: M-CORE-API (HTTP), @/auth/token (in-memory access token),
//            ./auth (cookie-backed refreshTokens for 401 retry).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §6 token refresh.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   registerAuthFailureHandler - install a callback fired when refresh fails
//   ApiError                   - Error subclass carrying HTTP status from apiRequest
//   apiRequest                 - typed JSON helper around authenticatedFetch
//   authenticatedFetch         - fetch with Bearer token + 401 single-flight refresh
// END_MODULE_MAP

let onAuthFailure: (() => void) | null = null;

// START_CONTRACT: registerAuthFailureHandler
//   PURPOSE: Install a single global callback invoked when token refresh fails
//            so AuthProvider can clear React user state alongside token storage.
//   INPUTS:  handler: () => void — fired after clearAllTokens() inside this module
//   OUTPUTS: void
//   SIDE_EFFECTS: stores handler in module-level singleton (overwrites previous).
//   LINKS:   AuthProvider.useEffect — registers its setUser(null) handler.
// END_CONTRACT: registerAuthFailureHandler
export function registerAuthFailureHandler(handler: () => void): void {
  onAuthFailure = handler;
}

let refreshPromise: Promise<string> | null = null;

function doRefresh(): Promise<string> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = refreshTokens()
    .then((tokens) => {
      setAccessToken(tokens.accessToken);
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

// START_CONTRACT: ApiError
//   PURPOSE: Carries the HTTP status alongside the message so callers (e.g.
//            CartPage) can branch on 410 EXPIRED without parsing strings.
//   INPUTS:  status: number — HTTP response status
//            message: string — passed to Error
//   OUTPUTS: ApiError instance with .status and .name = 'ApiError'.
//   SIDE_EFFECTS: none.
// END_CONTRACT: ApiError
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

// START_CONTRACT: apiRequest
//   PURPOSE: Generic JSON helper — authenticated fetch + non-2xx -> ApiError +
//            res.json() typed as T. Used by api/cart.ts and api/menu.ts.
//   INPUTS:  url: string — absolute or relative endpoint path
//            opts?: RequestInit — passed through (method, body, headers, …)
//   OUTPUTS: Promise<T> — decoded JSON body cast to caller's T.
//   SIDE_EFFECTS: HTTP request via authenticatedFetch (may trigger token refresh).
//   LINKS:   PDD §6 token refresh; INV-002 — server enforces auth, this only
//            attaches Bearer for UX/network efficiency.
// END_CONTRACT: apiRequest
/**
 * Выполняет аутентифицированный запрос и десериализует JSON.
 * Бросает ApiError с HTTP-статусом при ответах не 2xx.
 */
export async function apiRequest<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await authenticatedFetch(url, opts);
  if (!res.ok) {
    throw new ApiError(res.status, `HTTP ${res.status}: ${url}`);
  }
  return res.json() as Promise<T>;
}

// START_CONTRACT: authenticatedFetch
//   PURPOSE: Like fetch() but injects the in-memory access token as Bearer and,
//            on a single 401, single-flight refreshes via refreshTokens() and
//            retries once. Refresh uses the HttpOnly refresh cookie. On
//            refresh failure clears tokens and fires the
//            registered auth-failure handler.
//   INPUTS:  input: RequestInfo | URL — fetch target
//            init?: RequestInit       — fetch options (headers merged with Bearer)
//   OUTPUTS: Promise<Response> — original response on success, retried response
//            after refresh, or original 401 response if refresh failed.
//   SIDE_EFFECTS: HTTP I/O; may setAccessToken on refresh; may call
//                 clearAllTokens() and the auth-failure handler.
//   LINKS:   PDD §6 token refresh; INV-002 (auth enforcement is server-side).
// END_CONTRACT: authenticatedFetch
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
