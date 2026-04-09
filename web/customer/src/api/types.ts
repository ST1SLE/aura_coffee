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
  phone_hash: string;
}

export interface VerifyCodeResponse {
  accessToken: string;
  refreshToken: string;
  user: AuthUser;
}

export type AuthErrorCode =
  | 'INVALID_CODE'
  | 'CODE_EXPIRED'
  | 'RATE_LIMITED'
  | 'NETWORK_ERROR'
  | 'UNKNOWN_ERROR';

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
