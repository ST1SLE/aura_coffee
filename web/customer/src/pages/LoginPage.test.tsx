import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import '@/i18n/config';
import { AuthContext } from '@/auth/AuthProvider';
import type { AuthContextValue } from '@/auth/AuthProvider';
import { LoginPage } from './LoginPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => ({
      state: { returnUrl: '/profile' },
      pathname: '/login',
      search: '',
      hash: '',
      key: 'default',
    }),
  };
});

function renderLoginPage(authOverrides: Partial<AuthContextValue> = {}) {
  const auth: AuthContextValue = {
    user: null,
    isAuthenticated: false,
    isLoading: false,
    login: vi.fn().mockResolvedValue(undefined),
    verifyCode: vi.fn(),
    logout: vi.fn(),
    ...authOverrides,
  };
  render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </AuthContext.Provider>,
  );
  return auth;
}

beforeEach(() => {
  mockNavigate.mockClear();
});

describe('LoginPage', () => {
  it('renders phone input and submit button', () => {
    renderLoginPage();
    expect(screen.getByRole('textbox')).toBeDefined();
    expect(screen.getByRole('button')).toBeDefined();
  });

  it('submit button disabled with incomplete phone', () => {
    renderLoginPage();
    const button = screen.getByRole('button');
    expect(button).toHaveProperty('disabled', true);
  });

  it('calls login and navigates on valid submit', async () => {
    const auth = renderLoginPage();
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '9991234567' } });

    const button = screen.getByRole('button');
    fireEvent.click(button);

    await waitFor(() => {
      expect(auth.login).toHaveBeenCalledWith('+79991234567');
    });
    expect(mockNavigate).toHaveBeenCalledWith('/login/verify', {
      state: { phone: '+79991234567', returnUrl: '/profile' },
    });
  });

  it('shows localized submitting label while send-code is pending', async () => {
    let resolveLogin!: () => void;
    const login = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveLogin = resolve;
        }),
    );
    renderLoginPage({ login });

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: '9991234567' },
    });
    fireEvent.click(screen.getByRole('button'));

    const button = await screen.findByRole('button', {
      name: /sending code|отправляем код/i,
    });
    expect(button).toHaveProperty('disabled', true);

    resolveLogin();

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login/verify', {
        state: { phone: '+79991234567', returnUrl: '/profile' },
      });
    });
  });

  it('shows error on login failure', async () => {
    const login = vi.fn().mockRejectedValue(new Error('fail'));
    renderLoginPage({ login });

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '9991234567' } });
    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByText(/network error|ошибка сети/i)).toBeDefined();
    });
  });
});
