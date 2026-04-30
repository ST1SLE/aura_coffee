import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import '@/i18n/config';
import { AuthContext } from '@/auth/AuthProvider';
import type { AuthContextValue } from '@/auth/AuthProvider';
import { ProtectedRoute } from '@/auth/ProtectedRoute';
import { Layout } from '@/components/Layout';
import { LoginPage } from '@/pages/LoginPage';
import { VerifyPage } from '@/pages/VerifyPage';
import { HomePage } from '@/pages/HomePage';
import { NotFoundPage } from '@/pages/NotFoundPage';

// Мок для api/auth, чтобы AuthProvider не ходил в сеть
vi.mock('@/api/auth', () => ({
  sendCode: vi.fn(),
  verifyCode: vi.fn(),
  refreshTokens: vi.fn(),
  logout: vi.fn(),
  AuthError: class AuthError extends Error {
    code: string;
    constructor(code: string, message: string) {
      super(message);
      this.code = code;
    }
  },
}));

vi.mock('@/api/client', () => ({
  registerAuthFailureHandler: vi.fn(),
  authenticatedFetch: vi.fn(),
}));

const unauthValue: AuthContextValue = {
  user: null,
  isAuthenticated: false,
  isLoading: false,
  login: vi.fn(),
  verifyCode: vi.fn(),
  logout: vi.fn(),
};

const authValue: AuthContextValue = {
  ...unauthValue,
  user: { id: 'u1', role: 'customer' },
  isAuthenticated: true,
};

// Маршруты из App.tsx, но с MemoryRouter вместо BrowserRouter
function AppRoutes({ initialRoute = '/' }: { initialRoute?: string }) {
  return (
    <MemoryRouter initialEntries={[initialRoute]}>
      <Routes>
        <Route path="login" element={<LoginPage />} />
        <Route path="login/verify" element={<VerifyPage />} />
        <Route element={<Layout />}>
          <Route element={<ProtectedRoute />}>
            <Route index element={<HomePage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe('App routes', () => {
  it('renders without crashing', () => {
    render(
      <AuthContext.Provider value={authValue}>
        <AppRoutes />
      </AuthContext.Provider>,
    );
    // Authenticated user at / sees HomePage
    expect(screen.getByText(/Aura Coffee/i)).toBeDefined();
  });

  it('renders LoginPage on /login without auth', () => {
    render(
      <AuthContext.Provider value={unauthValue}>
        <AppRoutes initialRoute="/login" />
      </AuthContext.Provider>,
    );
    // LoginPage содержит поле ввода телефона
    expect(screen.getByRole('textbox')).toBeDefined();
  });

  it('redirects unauthenticated user from / to /login', () => {
    render(
      <AuthContext.Provider value={unauthValue}>
        <AppRoutes initialRoute="/" />
      </AuthContext.Provider>,
    );
    // ProtectedRoute редиректит на /login — LoginPage рендерится
    expect(screen.getByRole('textbox')).toBeDefined();
  });

  it('renders NotFoundPage on unknown route', () => {
    render(
      <AuthContext.Provider value={unauthValue}>
        <AppRoutes initialRoute="/nonexistent" />
      </AuthContext.Provider>,
    );
    expect(screen.getByText(/404|not found|не найдена/i)).toBeDefined();
  });
});
