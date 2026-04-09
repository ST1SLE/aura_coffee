import { render, screen, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthProvider } from './AuthProvider';
import { useAuth } from './useAuth';

vi.mock('@/api/auth', () => ({
  sendCode: vi.fn().mockResolvedValue({ message: 'OTP sent', phone_hash: 'hash' }),
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
  localStorage.clear();
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
});
