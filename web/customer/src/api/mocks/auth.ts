import type { SendCodeResponse, VerifyCodeResponse, AuthTokens } from '../types';
import { AuthError } from '../types';

const MOCK_DELAY = 500;
const VALID_CODE = '000000';

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

let mockRefreshToken = '';

export async function sendCode(_phone: string): Promise<SendCodeResponse> {
  await delay(MOCK_DELAY);
  return { message: 'OTP sent' };
}

export async function verifyCode(
  _phone: string,
  code: string,
): Promise<VerifyCodeResponse> {
  await delay(MOCK_DELAY);

  if (code !== VALID_CODE) {
    throw new AuthError('INVALID_CODE', 'Неверный код');
  }

  mockRefreshToken = crypto.randomUUID();
  return {
    accessToken: `mock-access-${Date.now()}`,
    refreshToken: mockRefreshToken,
    user: { id: crypto.randomUUID(), role: 'customer' },
  };
}

export async function refreshTokens(
  refreshToken?: string | null,
): Promise<AuthTokens> {
  void refreshToken;
  await delay(MOCK_DELAY);

  mockRefreshToken = crypto.randomUUID();
  return {
    accessToken: `mock-access-${Date.now()}`,
    refreshToken: mockRefreshToken,
  };
}

export async function logout(): Promise<void> {
  await delay(MOCK_DELAY);
  mockRefreshToken = '';
}
