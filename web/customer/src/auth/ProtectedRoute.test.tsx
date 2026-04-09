import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ProtectedRoute } from './ProtectedRoute';
import { AuthContext } from './AuthProvider';
import type { AuthContextValue } from './AuthProvider';

// Компонент для захвата location.state при редиректе
function LoginPageWithState() {
  const location = useLocation();
  const state = location.state as { returnUrl?: string } | null;
  return (
    <div>
      Login Page
      <span data-testid="returnUrl">{state?.returnUrl ?? 'none'}</span>
    </div>
  );
}

function renderWithAuth(authValue: AuthContextValue, initialRoute = '/protected') {
  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Routes>
          <Route path="/login" element={<LoginPageWithState />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/protected" element={<div>Protected Content</div>} />
            <Route path="/profile" element={<div>Profile Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

const baseAuth: AuthContextValue = {
  user: null,
  isAuthenticated: false,
  isLoading: false,
  login: vi.fn(),
  verifyCode: vi.fn(),
  logout: vi.fn(),
};

describe('ProtectedRoute', () => {
  it('redirects unauthenticated user to /login', () => {
    renderWithAuth(baseAuth);
    expect(screen.getByText('Login Page')).toBeDefined();
  });

  it('renders content for authenticated user', () => {
    renderWithAuth({
      ...baseAuth,
      user: { id: 'u1', role: 'customer' },
      isAuthenticated: true,
    });
    expect(screen.getByText('Protected Content')).toBeDefined();
  });

  it('shows loading indicator while loading', () => {
    renderWithAuth({ ...baseAuth, isLoading: true });
    expect(screen.queryByText('Login Page')).toBeNull();
    expect(screen.queryByText('Protected Content')).toBeNull();
  });

  // Редирект сохраняет returnUrl в state
  it('preserves returnUrl in redirect state', () => {
    renderWithAuth(baseAuth, '/profile');
    expect(screen.getByText('Login Page')).toBeDefined();
    expect(screen.getByTestId('returnUrl').textContent).toBe('/profile');
  });
});
