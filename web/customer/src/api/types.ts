// START_MODULE_CONTRACT
//   PURPOSE: Shared TypeScript types and the AuthError class for the auth API
//            client; consumed by api/auth.ts, api/client.ts and the AuthProvider.
//   SCOPE:   Auth DTOs (tokens, user, send/verify responses) plus AuthError code
//            enum and class — purely contract surface, no runtime side-effects
//            beyond the AuthError constructor.
//   DEPENDS: none (pure type module + Error subclass).
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §4.4 / §6 OTP flow.
//   ROLE:    TYPES
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   AuthTokens         - access/refresh token pair returned by /auth/refresh
//   AuthUser           - identity payload (id + role) decoded from JWT
//   SendCodeResponse   - server response for POST /auth/send-code
//   VerifyCodeResponse - server response for POST /auth/verify-code (incl. user)
//   AuthErrorCode      - discriminator union of auth failure modes
//   AuthError          - Error subclass carrying AuthErrorCode + retryAfter
// END_MODULE_MAP

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

export interface AuthUser {
  id: string;
  role: 'customer';
}

export interface SendCodeResponse {
  message: string;
}

export interface VerifyCodeResponse {
  accessToken: string;
  refreshToken: string;
  user: AuthUser;
}

export type AuthErrorCode =
  | 'INVALID_CODE'
  | 'CODE_EXPIRED'
  | 'CODE_NOT_DELIVERED'
  | 'RATE_LIMITED'
  | 'NETWORK_ERROR'
  | 'UNKNOWN_ERROR';

// START_CONTRACT: AuthError
//   PURPOSE: Typed Error subclass thrown by api/auth.ts so callers can branch
//            on a stable AuthErrorCode instead of regex-matching messages.
//   INPUTS:  code: AuthErrorCode — failure category
//            message: string    — human-readable description (forwarded to Error)
//            retryAfter?: number — seconds until retry is allowed (RATE_LIMITED only)
//   OUTPUTS: AuthError instance with .code, .retryAfter, .name = 'AuthError'.
//   SIDE_EFFECTS: none.
//   LINKS:   PDD §6 OTP states; consumed by LoginPage / VerifyPage.
// END_CONTRACT: AuthError
export class AuthError extends Error {
  code: AuthErrorCode;
  retryAfter?: number;

  constructor(code: AuthErrorCode, message: string, retryAfter?: number) {
    super(message);
    this.name = 'AuthError';
    this.code = code;
    this.retryAfter = retryAfter;
  }
}
