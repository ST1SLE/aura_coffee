import { render, screen, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthProvider } from './AuthProvider';
import { useAuth } from './useAuth';

vi.mock('@/api/auth', () => ({
  sendCode: vi.fn().mockResolvedValue({ message: 'OTP sent' }),
  verifyCode: vi.fn().mockResolvedValue({
    accessToken: 'test-access',
    refreshToken: 'test-refresh',
    user: { id: 'u1', role: 'customer' },
  }),
  refreshTokens: vi.fn().mockResolvedValue({
    accessToken: 'new-access',
    refreshToken: 'new-refresh',
  }),
  logout: vi.fn().mockResolvedValue(undefined),
}));

import * as authApi from '@/api/auth';

function jwtFor(sub: string): string {
  return `h.${btoa(JSON.stringify({ sub, role: 'customer' }))}.s`;
}

function TestConsumer() {
  const { isAuthenticated, isLoading, user, login, verifyCode, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="authenticated">{String(isAuthenticated)}</span>
      <span data-testid="user">{user ? user.id : 'null'}</span>
      <button onClick={() => login('+79991234567')}>login</button>
      <button onClick={() => verifyCode('+79991234567', '000000')}>verify</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.mocked(authApi.sendCode).mockResolvedValue({ message: 'OTP sent' });
  vi.mocked(authApi.verifyCode).mockResolvedValue({
    accessToken: 'test-access',
    refreshToken: 'test-refresh',
    user: { id: 'u1', role: 'customer' },
  });
  vi.mocked(authApi.refreshTokens).mockRejectedValue(
    new Error('no refresh cookie'),
  );
  vi.mocked(authApi.logout).mockResolvedValue(undefined);
});

describe('AuthProvider', () => {
  it('starts unauthenticated when no refresh token', async () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });
    expect(screen.getByTestId('authenticated').textContent).toBe('false');
    expect(authApi.refreshTokens).toHaveBeenCalledWith();
  });

  it('silent refresh uses cookie-backed session without localStorage token', async () => {
    vi.mocked(authApi.refreshTokens).mockResolvedValueOnce({
      accessToken: jwtFor('u-cookie'),
      refreshToken: 'legacy-response-field',
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });
    expect(screen.getByTestId('authenticated').textContent).toBe('true');
    expect(screen.getByTestId('user').textContent).toBe('u-cookie');
    expect(localStorage.getItem('aura_refresh_token')).toBeNull();
  });

  it('login + verify sets user', async () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });

    await act(async () => {
      screen.getByText('login').click();
    });

    await act(async () => {
      screen.getByText('verify').click();
    });

    expect(screen.getByTestId('authenticated').textContent).toBe('true');
    expect(screen.getByTestId('user').textContent).toBe('u1');
  });

  it('logout clears user', async () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });

    await act(async () => {
      screen.getByText('verify').click();
    });
    expect(screen.getByTestId('authenticated').textContent).toBe('true');

    await act(async () => {
      screen.getByText('logout').click();
    });
    expect(screen.getByTestId('authenticated').textContent).toBe('false');
  });

  // Старый localStorage refresh token больше не используется и очищается.
  it('legacy localStorage refresh token is ignored and cleared on refresh failure', async () => {
    localStorage.setItem('aura_refresh_token', 'legacy-refresh-token');
    vi.mocked(authApi.refreshTokens).mockRejectedValueOnce(new Error('token expired'));

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });
    expect(screen.getByTestId('authenticated').textContent).toBe('false');
    expect(localStorage.getItem('aura_refresh_token')).toBeNull();
    expect(authApi.refreshTokens).toHaveBeenCalledWith();
  });
});
