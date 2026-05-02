// START_MODULE_CONTRACT
//   PURPOSE: Token storage — access token kept only in module-scope memory
//            (cleared on full reload). Refresh tokens are server-set HttpOnly
//            cookies; this module only clears the legacy localStorage key left
//            by older builds.
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
//   getRefreshToken    - legacy API, always returns null for browser safety
//   setRefreshToken    - legacy API, clears any old localStorage value
//   clearRefreshToken  - remove old refresh token from localStorage
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
//   PURPOSE: Legacy compatibility hook; refresh tokens now live in HttpOnly
//            cookies and are intentionally unreadable to JavaScript.
//   INPUTS:  none.
//   OUTPUTS: null.
//   SIDE_EFFECTS: none.
// END_CONTRACT: getRefreshToken
export function getRefreshToken(): string | null {
  return null;
}

// START_CONTRACT: setRefreshToken
//   PURPOSE: Legacy compatibility hook; never persists refresh tokens and
//            removes any old localStorage token if called by stale paths.
//   INPUTS:  token: string.
//   OUTPUTS: void.
//   SIDE_EFFECTS: localStorage write (deletes legacy key).
// END_CONTRACT: setRefreshToken
export function setRefreshToken(token: string): void {
  void token;
  clearRefreshToken();
}

// START_CONTRACT: clearRefreshToken
//   PURPOSE: Remove the legacy refresh token from localStorage.
//   INPUTS:  none.
//   OUTPUTS: void.
//   SIDE_EFFECTS: localStorage write.
// END_CONTRACT: clearRefreshToken
export function clearRefreshToken(): void {
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

// START_CONTRACT: clearAllTokens
//   PURPOSE: Drop the access token and clear any legacy refresh token — used on
//            logout and on refresh failure.
//   INPUTS:  none.
//   OUTPUTS: void.
//   SIDE_EFFECTS: clears module-scope access token + legacy localStorage refresh.
// END_CONTRACT: clearAllTokens
export function clearAllTokens(): void {
  clearAccessToken();
  clearRefreshToken();
}
