import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import '@/i18n/config';
import { AuthContext } from '@/auth/AuthProvider';
import type { AuthContextValue } from '@/auth/AuthProvider';
import { AuthError } from '@/api/auth';
import { VerifyPage } from './VerifyPage';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useLocation: () => ({
      state: { phone: '+79991234567', returnUrl: '/' },
      pathname: '/login/verify',
      search: '',
      hash: '',
      key: 'default',
    }),
  };
});

function renderWithAuth(verifyCode: AuthContextValue['verifyCode']) {
  const auth: AuthContextValue = {
    user: null,
    isAuthenticated: false,
    isLoading: false,
    login: vi.fn().mockResolvedValue(undefined),
    verifyCode,
    logout: vi.fn(),
  };
  render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={['/login/verify']}>
        <VerifyPage />
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

function pasteCode(code: string) {
  const inputs = screen.getAllByRole('textbox');
  fireEvent.paste(inputs[0], {
    clipboardData: { getData: () => code },
  });
}

describe('VerifyPage — CODE_NOT_DELIVERED (409)', () => {
  it('shows "not delivered" message instead of network error', async () => {
    const verifyCode = vi
      .fn()
      .mockRejectedValue(new AuthError('CODE_NOT_DELIVERED', 'OTP not yet delivered'));
    renderWithAuth(verifyCode);

    pasteCode('123456');

    await waitFor(() => {
      const errorEl = screen.getByText(/on its way|в пути/i);
      expect(errorEl).toBeDefined();
    });
  });

  it('does NOT show network error for CODE_NOT_DELIVERED', async () => {
    const verifyCode = vi
      .fn()
      .mockRejectedValue(new AuthError('CODE_NOT_DELIVERED', 'OTP not yet delivered'));
    renderWithAuth(verifyCode);

    pasteCode('123456');

    await waitFor(() => {
      expect(screen.queryByText(/network error|ошибка сети/i)).toBeNull();
    });
  });

  it('keeps OTP input editable after CODE_NOT_DELIVERED', async () => {
    const verifyCode = vi
      .fn()
      .mockRejectedValue(new AuthError('CODE_NOT_DELIVERED', 'OTP not yet delivered'));
    renderWithAuth(verifyCode);

    pasteCode('123456');

    await waitFor(() => {
      screen.getByText(/on its way|в пути/i);
    });

    const inputs = screen.getAllByRole('textbox');
    inputs.forEach((input) => {
      expect((input as HTMLInputElement).disabled).toBe(false);
    });
  });
});
