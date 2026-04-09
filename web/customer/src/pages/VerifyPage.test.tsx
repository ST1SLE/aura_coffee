import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import '@/i18n/config';
import { AuthContext } from '@/auth/AuthProvider';
import type { AuthContextValue } from '@/auth/AuthProvider';
import { VerifyPage } from './VerifyPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => ({
      state: { phone: '+79991234567', returnUrl: '/profile' },
      pathname: '/login/verify',
      search: '',
      hash: '',
      key: 'default',
    }),
  };
});

function renderVerifyPage(authOverrides: Partial<AuthContextValue> = {}) {
  const auth: AuthContextValue = {
    user: null,
    isAuthenticated: false,
    isLoading: false,
    login: vi.fn().mockResolvedValue(undefined),
    verifyCode: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn(),
    ...authOverrides,
  };
  render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={['/login/verify']}>
        <VerifyPage />
      </MemoryRouter>
    </AuthContext.Provider>,
  );
  return auth;
}

describe('VerifyPage', () => {
  it('renders OTP inputs and masked phone', () => {
    renderVerifyPage();
    const inputs = screen.getAllByRole('textbox');
    expect(inputs.length).toBe(6);
    expect(screen.getByText(/\+799\*\*\*67/)).toBeDefined();
  });

  it('calls verifyCode on paste of 6 digits', async () => {
    const auth = renderVerifyPage();
    const inputs = screen.getAllByRole('textbox');
    fireEvent.paste(inputs[0], {
      clipboardData: { getData: () => '000000' },
    });

    await waitFor(() => {
      expect(auth.verifyCode).toHaveBeenCalledWith('+79991234567', '000000');
    });
  });

  it('shows error on invalid code', async () => {
    const { AuthError } = await import('@/api/auth');
    const verifyCode = vi.fn().mockRejectedValue(new AuthError('INVALID_CODE', 'bad'));
    renderVerifyPage({ verifyCode });

    const inputs = screen.getAllByRole('textbox');
    fireEvent.paste(inputs[0], {
      clipboardData: { getData: () => '111111' },
    });

    await waitFor(() => {
      expect(screen.getByText(/invalid|неверный/i)).toBeDefined();
    });
  });

  it('redirects on success', async () => {
    renderVerifyPage();
    const inputs = screen.getAllByRole('textbox');
    fireEvent.paste(inputs[0], {
      clipboardData: { getData: () => '000000' },
    });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/profile', { replace: true });
    });
  });

  // Повторная отправка кода через ResendTimer
  it('calls login() with phone when resend button is clicked', async () => {
    vi.useFakeTimers();
    const loginMock = vi.fn().mockResolvedValue(undefined);
    renderVerifyPage({ login: loginMock });

    // Прокручиваем таймер на 60 секунд, чтобы кнопка появилась
    await act(async () => {
      vi.advanceTimersByTime(60_000);
    });

    const resendButton = screen.getByRole('button', { name: /resend|отправить/i });
    await act(async () => {
      fireEvent.click(resendButton);
    });

    expect(loginMock).toHaveBeenCalledWith('+79991234567');
    vi.useRealTimers();
  });

  it('shows error when resend login() call fails', async () => {
    vi.useFakeTimers();
    const loginMock = vi.fn().mockRejectedValue(new Error('network'));
    renderVerifyPage({ login: loginMock });

    await act(async () => {
      vi.advanceTimersByTime(60_000);
    });

    const resendButton = screen.getByRole('button', { name: /resend|отправить/i });
    // act отработает микротаски (rejected promise → catch → setError)
    await act(async () => {
      fireEvent.click(resendButton);
      await loginMock.mock.results[0]?.value?.catch?.(() => {});
    });

    expect(screen.getByText(/error|ошибка/i)).toBeDefined();
    vi.useRealTimers();
  });
});
