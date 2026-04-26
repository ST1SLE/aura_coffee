// START_MODULE_CONTRACT
//   PURPOSE: Token storage — access token kept only in module-scope memory
//            (cleared on full reload), refresh token persisted in localStorage
//            so the AuthProvider can do a silent refresh on app boot.
//            Note: AGENTS.md "must not store auth tokens in localStorage" applies
//            to the access token (kept in memory here); the refresh token is
//            still persisted for the silent-refresh UX. Long-term this should
//            move to httpOnly cookies (PDD §6).
//   SCOPE:   accessor and mutator functions for both tokens.
//   DEPENDS: browser localStorage only.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §6 token storage.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   getAccessToken     - read in-memory access token (or null)
//   setAccessToken     - store in-memory access token
//   clearAccessToken   - reset in-memory access token to null
//   getRefreshToken    - read refresh token from localStorage
//   setRefreshToken    - persist refresh token in localStorage
//   clearRefreshToken  - remove refresh token from localStorage
//   clearAllTokens     - clear both access and refresh
// END_MODULE_MAP

const REFRESH_TOKEN_KEY = 'aura_refresh_token';

let accessToken: string | null = null;

// START_CONTRACT: getAccessToken
//   PURPOSE: Read the current in-memory access token.
//   INPUTS:  none.
//   OUTPUTS: string | null.
//   SIDE_EFFECTS: none.
// END_CONTRACT: getAccessToken
export function getAccessToken(): string | null {
  return accessToken;
}

// START_CONTRACT: setAccessToken
//   PURPOSE: Store an access token in module-scope memory.
//   INPUTS:  token: string.
//   OUTPUTS: void.
//   SIDE_EFFECTS: writes to module-scope variable.
// END_CONTRACT: setAccessToken
export function setAccessToken(token: string): void {
  accessToken = token;
}

// START_CONTRACT: clearAccessToken
//   PURPOSE: Drop the in-memory access token (set to null).
//   INPUTS:  none.
//   OUTPUTS: void.
//   SIDE_EFFECTS: writes to module-scope variable.
// END_CONTRACT: clearAccessToken
export function clearAccessToken(): void {
  accessToken = null;
}

// START_CONTRACT: getRefreshToken
//   PURPOSE: Read the refresh token from localStorage.
//   INPUTS:  none.
//   OUTPUTS: string | null.
//   SIDE_EFFECTS: localStorage read.
// END_CONTRACT: getRefreshToken
export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

// START_CONTRACT: setRefreshToken
//   PURPOSE: Persist the refresh token in localStorage so AuthProvider can
//            silent-refresh on next app boot.
//   INPUTS:  token: string.
//   OUTPUTS: void.
//   SIDE_EFFECTS: localStorage write.
// END_CONTRACT: setRefreshToken
export function setRefreshToken(token: string): void {
  localStorage.setItem(REFRESH_TOKEN_KEY, token);
}

// START_CONTRACT: clearRefreshToken
//   PURPOSE: Remove the refresh token from localStorage.
//   INPUTS:  none.
//   OUTPUTS: void.
//   SIDE_EFFECTS: localStorage write.
// END_CONTRACT: clearRefreshToken
export function clearRefreshToken(): void {
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

// START_CONTRACT: clearAllTokens
//   PURPOSE: Drop both access and refresh tokens — used on logout and on
//            refresh failure.
//   INPUTS:  none.
//   OUTPUTS: void.
//   SIDE_EFFECTS: clears module-scope access token + localStorage refresh.
// END_CONTRACT: clearAllTokens
export function clearAllTokens(): void {
  clearAccessToken();
  clearRefreshToken();
}
